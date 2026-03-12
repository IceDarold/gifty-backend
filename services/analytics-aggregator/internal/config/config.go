package config

import (
	"os"
	"strconv"
	"strings"
	"time"
)

type Config struct {
	ListenAddr       string
	NATSURL          string
	NATSStream       string
	NATSSubject      string
	NATSDurable      string
	ClickHouseDSN    string
	SchemaPath       string
	FlushInterval    time.Duration
	DedupTTL         time.Duration
	RehydrateMinutes int
	WSAuthToken      string
	AdminAPIBase     string
	AdminToken       string
	PollDashboard    time.Duration
	PollOps          time.Duration
	PollCatalog      time.Duration
	PollSettings     time.Duration
	PollLogs         time.Duration
	LogsTailEnabled  bool
}

func Load() Config {
	flushSec := envInt("ANALYTICS_FLUSH_SECONDS", 60)
	dedupSec := envInt("ANALYTICS_DEDUP_TTL_SECONDS", 900)
	return Config{
		ListenAddr:       env("LISTEN_ADDR", ":8095"),
		NATSURL:          env("NATS_URL", "nats://nats:4222"),
		NATSStream:       env("NATS_STREAM", "AN_EVENTS"),
		NATSSubject:      env("NATS_SUBJECT", "analytics.events.v1.>"),
		NATSDurable:      env("NATS_DURABLE", "AGG_WRITER_V1"),
		ClickHouseDSN:    env("CLICKHOUSE_DSN", "clickhouse://default:@clickhouse:9000/default"),
		SchemaPath:       env("ANALYTICS_SCHEMA_PATH", "/app/contracts/analytics/event-envelope.v1.json"),
		FlushInterval:    time.Duration(flushSec) * time.Second,
		DedupTTL:         time.Duration(dedupSec) * time.Second,
		RehydrateMinutes: envInt("ANALYTICS_REHYDRATE_MINUTES", 180),
		WSAuthToken:      env("LIVE_ANALYTICS_WS_TOKEN", ""),
		AdminAPIBase:     env("ADMIN_WS_API_BASE", "http://api:8000"),
		AdminToken:       env("INTERNAL_API_TOKEN", ""),
		PollDashboard:    time.Duration(envInt("ADMIN_WS_POLL_DASHBOARD_SECONDS", 30)) * time.Second,
		PollOps:          time.Duration(envInt("ADMIN_WS_POLL_OPS_SECONDS", 30)) * time.Second,
		PollCatalog:      time.Duration(envInt("ADMIN_WS_POLL_CATALOG_SECONDS", 60)) * time.Second,
		PollSettings:     time.Duration(envInt("ADMIN_WS_POLL_SETTINGS_SECONDS", 60)) * time.Second,
		PollLogs:         time.Duration(envInt("ADMIN_WS_POLL_LOGS_SECONDS", 5)) * time.Second,
		LogsTailEnabled:  envBool("ADMIN_WS_LOGS_TAIL", true),
	}
}

func env(key, fallback string) string {
	v := os.Getenv(key)
	if v == "" {
		return fallback
	}
	return v
}

func envInt(key string, fallback int) int {
	v := os.Getenv(key)
	if v == "" {
		return fallback
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		return fallback
	}
	return n
}

func envBool(key string, fallback bool) bool {
	v := os.Getenv(key)
	if v == "" {
		return fallback
	}
	switch strings.ToLower(v) {
	case "1", "true", "yes", "on":
		return true
	case "0", "false", "no", "off":
		return false
	default:
		return fallback
	}
}
