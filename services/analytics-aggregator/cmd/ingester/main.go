package main

import (
	"context"
	"log"
	"os/signal"
	"syscall"

	"analytics-aggregator/internal/config"
	"analytics-aggregator/internal/dedup"
	"analytics-aggregator/internal/flush"
	"analytics-aggregator/internal/ingest"
	"analytics-aggregator/internal/schema"
)

func main() {
	cfg := config.Load()
	validator, err := schema.NewValidator(cfg.SchemaPath)
	if err != nil {
		log.Fatalf("schema validator init failed: %v", err)
	}
	writer, err := flush.NewWriter(cfg.ClickHouseDSN)
	if err != nil {
		log.Fatalf("clickhouse writer init failed: %v", err)
	}
	ingester, err := ingest.New(cfg.NATSURL, cfg.NATSStream, cfg.NATSSubject, cfg.NATSDurable, validator, dedup.New(cfg.DedupTTL), writer)
	if err != nil {
		log.Fatalf("ingester init failed: %v", err)
	}
	stateIngester, err := ingest.NewState(cfg.NATSURL, cfg.NATSStateStream, cfg.NATSStateSubject, cfg.NATSStateDurable, dedup.New(cfg.DedupTTL), writer)
	if err != nil {
		log.Fatalf("state ingester init failed: %v", err)
	}
	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()
	log.Println("analytics-ingester started")
	go func() {
		if err := stateIngester.Run(ctx, cfg.FlushInterval); err != nil {
			log.Printf("state ingester stopped: %v", err)
		}
	}()
	if err := ingester.Run(ctx, cfg.FlushInterval); err != nil {
		log.Printf("ingester stopped: %v", err)
	}
}
