package main

import (
	"context"
	"log"
	"net/http"
	"os/signal"
	"syscall"
	"time"

	"analytics-aggregator/internal/adminpoll"
	"analytics-aggregator/internal/adminresolver"
	"analytics-aggregator/internal/bootstrap"
	"analytics-aggregator/internal/config"
	"analytics-aggregator/internal/dedup"
	"analytics-aggregator/internal/flush"
	httpapi "analytics-aggregator/internal/http"
	"analytics-aggregator/internal/nats"
	"analytics-aggregator/internal/schema"
	"analytics-aggregator/internal/state"
	"analytics-aggregator/internal/ws"
)

func main() {
	cfg := config.Load()
	validator, err := schema.NewValidator(cfg.SchemaPath)
	if err != nil {
		log.Fatalf("schema validator init failed: %v", err)
	}
	store := state.NewStore()
	hub := ws.NewHub()
	resolver := adminresolver.New(cfg)
	wsHandler := ws.NewHandler(hub, store, cfg.WSAuthToken, resolver)

	writer, err := flush.NewWriter(cfg.ClickHouseDSN)
	if err != nil {
		log.Fatalf("clickhouse writer init failed: %v", err)
	}

	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	if err := bootstrap.Rehydrate(ctx, writer, store, cfg.RehydrateMinutes); err != nil {
		log.Printf("rehydrate failed: %v", err)
	}

	consumer, err := nats.NewEphemeral(cfg.NATSURL, cfg.NATSSubject, validator, store, dedup.New(cfg.DedupTTL), hub)
	if err != nil {
		log.Fatalf("ephemeral consumer init failed: %v", err)
	}
	stateConsumer, err := nats.NewStateEphemeral(cfg.NATSURL, cfg.NATSStateSubject, resolver, store, dedup.New(cfg.DedupTTL), hub)
	if err != nil {
		log.Fatalf("state ephemeral consumer init failed: %v", err)
	}
	go func() {
		if err := consumer.Run(ctx); err != nil {
			log.Printf("ephemeral consumer stopped: %v", err)
		}
	}()
	go func() {
		if err := stateConsumer.Run(ctx); err != nil {
			log.Printf("state ephemeral consumer stopped: %v", err)
		}
	}()

	poller := adminpoll.New(cfg, store, hub)
	poller.Run(ctx)

	srv := &http.Server{Addr: cfg.ListenAddr, Handler: httpapi.Router(store, wsHandler)}
	go func() {
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("http server error: %v", err)
		}
	}()
	log.Printf("analytics-realtime listening on %s", cfg.ListenAddr)

	<-ctx.Done()
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer shutdownCancel()
	_ = srv.Shutdown(shutdownCtx)
}
