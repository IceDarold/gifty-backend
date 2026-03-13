package flush

import (
	"context"
	"net/url"
	"strings"
	"time"

	"analytics-aggregator/internal/state"
	"github.com/ClickHouse/clickhouse-go/v2"
)

type Writer struct {
	conn clickhouse.Conn
}

func NewWriter(dsn string) (*Writer, error) {
	cfg := parseDSN(dsn)
	conn, err := clickhouse.Open(&clickhouse.Options{
		Addr: []string{cfg.Addr},
		Auth: clickhouse.Auth{
			Database: cfg.Database,
			Username: cfg.Username,
			Password: cfg.Password,
		},
	})
	if err != nil {
		return nil, err
	}
	return &Writer{conn: conn}, nil
}

type dsnConfig struct {
	Addr     string
	Database string
	Username string
	Password string
}

func parseDSN(dsn string) dsnConfig {
	cfg := dsnConfig{
		Addr:     "clickhouse:9000",
		Database: "default",
		Username: "default",
		Password: "",
	}

	dsn = strings.TrimSpace(dsn)
	if dsn == "" {
		return cfg
	}
	if !strings.HasPrefix(dsn, "clickhouse://") {
		cfg.Addr = dsn
		return cfg
	}

	parsed, err := url.Parse(dsn)
	if err != nil {
		return cfg
	}
	if parsed.Host != "" {
		cfg.Addr = parsed.Host
	}
	if parsed.User != nil {
		if user := parsed.User.Username(); user != "" {
			cfg.Username = user
		}
		if pass, ok := parsed.User.Password(); ok {
			cfg.Password = pass
		}
	}
	if db := strings.Trim(parsed.Path, "/"); db != "" {
		cfg.Database = db
	}
	return cfg
}

func (w *Writer) FlushBuckets(ctx context.Context, buckets map[state.BucketKey]state.BucketValue) error {
	if len(buckets) == 0 {
		return nil
	}
	batch, err := w.conn.PrepareBatch(ctx, `
		INSERT INTO analytics_agg_1m
		(bucket_minute, metric, scope, scope_key, dims_json, cnt, sum_value, min_value, max_value, p50_value, p95_value, updated_at, version)
		VALUES
	`)
	if err != nil {
		return err
	}
	for k, v := range buckets {
		avg := 0.0
		if v.Count > 0 {
			avg = v.Sum / float64(v.Count)
		}
		if err := batch.Append(
			k.BucketMinute,
			k.Metric,
			k.Scope,
			k.ScopeKey,
			k.DimsJSON,
			v.Count,
			v.Sum,
			v.Min,
			v.Max,
			avg,
			v.Max,
			time.Now().UTC(),
			v.Version,
		); err != nil {
			return err
		}
	}
	return batch.Send()
}

type StateEventRow struct {
	EventID       string
	AggregateType string
	AggregateID   string
	EventType     string
	PayloadJSON   string
	OccurredAt    time.Time
	Version       uint64
	Operation     string
	Source        string
}

func (w *Writer) InsertStateEvents(ctx context.Context, rows []StateEventRow) error {
	if len(rows) == 0 {
		return nil
	}
	batch, err := w.conn.PrepareBatch(ctx, `
		INSERT INTO state_events_raw
		(event_id, aggregate_type, aggregate_id, event_type, payload_json, occurred_at, version, op, source)
		VALUES
	`)
	if err != nil {
		return err
	}
	for _, r := range rows {
		if err := batch.Append(r.EventID, r.AggregateType, r.AggregateID, r.EventType, r.PayloadJSON, r.OccurredAt, r.Version, r.Operation, r.Source); err != nil {
			return err
		}
	}
	return batch.Send()
}

func (w *Writer) UpsertLatestState(ctx context.Context, table string, keyCols []string, rows [][]interface{}) error {
	if len(rows) == 0 {
		return nil
	}
	query := "INSERT INTO " + table + " (" + strings.Join(keyCols, ", ") + ") VALUES"
	batch, err := w.conn.PrepareBatch(ctx, query)
	if err != nil {
		return err
	}
	for _, row := range rows {
		if err := batch.Append(row...); err != nil {
			return err
		}
	}
	return batch.Send()
}

type EventRow struct {
	EventID     string
	OccurredAt  time.Time
	EventType   string
	Metric      string
	Scope       string
	ScopeKey    string
	DimsJSON    string
	PayloadJSON string
	Value       float64
	Version     uint64
}

type LLMCallRow struct {
	EventID          string
	CreatedAt        time.Time
	Provider         string
	Model            string
	CallType         string
	Status           string
	LatencyMS        float64
	TotalTokens      uint64
	PromptTokens     uint64
	CompletionTokens uint64
	CostUSD          float64
	SessionID        string
	PromptHash       string
	PayloadJSON      string
	Version          uint64
}

func (w *Writer) InsertEvents(ctx context.Context, rows []EventRow) error {
	if len(rows) == 0 {
		return nil
	}
	maxOccurred := rows[0].OccurredAt
	maxEventID := rows[0].EventID
	for _, r := range rows[1:] {
		if r.OccurredAt.After(maxOccurred) {
			maxOccurred = r.OccurredAt
			maxEventID = r.EventID
		}
	}
	batch, err := w.conn.PrepareBatch(ctx, `
		INSERT INTO analytics_events
		(event_id, occurred_at, event_type, metric, scope, scope_key, dims_json, payload_json, value, version)
		VALUES
	`)
	if err != nil {
		return err
	}
	for _, r := range rows {
		if err := batch.Append(
			r.EventID,
			r.OccurredAt,
			r.EventType,
			r.Metric,
			r.Scope,
			r.ScopeKey,
			r.DimsJSON,
			r.PayloadJSON,
			r.Value,
			r.Version,
		); err != nil {
			return err
		}
	}
	if err := batch.Send(); err != nil {
		return err
	}
	return w.UpdateSyncStateEvent(ctx, "analytics-events", maxOccurred, maxEventID)
}

func (w *Writer) InsertLLMCalls(ctx context.Context, rows []LLMCallRow) error {
	if len(rows) == 0 {
		return nil
	}
	batch, err := w.conn.PrepareBatch(ctx, `
		INSERT INTO llm_calls
		(event_id, created_at, provider, model, call_type, status, latency_ms, total_tokens, prompt_tokens, completion_tokens, cost_usd, session_id, prompt_hash, payload_json, version)
		VALUES
	`)
	if err != nil {
		return err
	}
	for _, r := range rows {
		if err := batch.Append(
			r.EventID,
			r.CreatedAt,
			r.Provider,
			r.Model,
			r.CallType,
			r.Status,
			r.LatencyMS,
			r.TotalTokens,
			r.PromptTokens,
			r.CompletionTokens,
			r.CostUSD,
			r.SessionID,
			r.PromptHash,
			r.PayloadJSON,
			r.Version,
		); err != nil {
			return err
		}
	}
	return batch.Send()
}

func (w *Writer) UpdateSyncStateEvent(ctx context.Context, syncName string, occurredAt time.Time, eventID string) error {
	now := time.Now().UTC()
	lag := now.Sub(occurredAt).Seconds()
	err := w.conn.Exec(ctx, `
		INSERT INTO sync_state
		(sync_name, last_bootstrap_at, last_backfill_at, last_bootstrap_version, last_event_applied_at, last_event_id, lag_seconds)
		VALUES (?, ?, ?, ?, ?, ?, ?)
	`, syncName, now, nil, uint64(now.UnixNano()), occurredAt, eventID, lag)
	return err
}

func (w *Writer) Rehydrate(ctx context.Context, since time.Time) (map[state.BucketKey]state.BucketValue, error) {
	q := `
		SELECT bucket_minute, metric, scope, scope_key, dims_json, cnt, sum_value, min_value, max_value, updated_at, version
		FROM analytics_agg_1m
		WHERE bucket_minute >= ?
	`
	rows, err := w.conn.Query(ctx, q, since)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := map[state.BucketKey]state.BucketValue{}
	for rows.Next() {
		var (
			bucket                        time.Time
			metric, scope, scopeKey, dims string
			cnt                           uint64
			sum, min, max                 float64
			updated                       time.Time
			version                       uint64
		)
		if err := rows.Scan(&bucket, &metric, &scope, &scopeKey, &dims, &cnt, &sum, &min, &max, &updated, &version); err != nil {
			return nil, err
		}
		out[state.BucketKey{BucketMinute: bucket, Metric: metric, Scope: scope, ScopeKey: scopeKey, DimsJSON: dims}] = state.BucketValue{
			Count: cnt, Sum: sum, Min: min, Max: max, UpdatedAt: updated, Version: version,
		}
	}
	return out, nil
}
