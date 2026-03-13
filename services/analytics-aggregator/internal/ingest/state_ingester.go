package ingest

import (
	"context"
	"encoding/json"
	"log"
	"strconv"
	"time"

	"analytics-aggregator/internal/dedup"
	"analytics-aggregator/internal/flush"
	"analytics-aggregator/internal/stateevent"

	"github.com/nats-io/nats.go"
)

type StateIngester struct {
	sub     *nats.Subscription
	dedup   *dedup.Cache
	writer  *flush.Writer
	pending []*nats.Msg
	events  []flush.StateEventRow
}

func NewState(url, stream, subject, durable string, dedupCache *dedup.Cache, writer *flush.Writer) (*StateIngester, error) {
	nc, err := nats.Connect(url)
	if err != nil {
		return nil, err
	}
	js, err := nc.JetStream()
	if err != nil {
		return nil, err
	}
	if _, err := js.AddStream(&nats.StreamConfig{Name: stream, Subjects: []string{subject}}); err != nil && err != nats.ErrStreamNameAlreadyInUse {
		return nil, err
	}
	sub, err := js.PullSubscribe(subject, durable, nats.BindStream(stream))
	if err != nil {
		return nil, err
	}
	return &StateIngester{sub: sub, dedup: dedupCache, writer: writer}, nil
}

func (i *StateIngester) Run(ctx context.Context, flushInterval time.Duration) error {
	ticker := time.NewTicker(flushInterval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return nil
		default:
		}
		msgs, err := i.sub.Fetch(200, nats.MaxWait(2*time.Second))
		if err != nil && err != nats.ErrTimeout {
			log.Printf("state nats fetch error: %v", err)
		}
		now := time.Now().UTC()
		for _, m := range msgs {
			ev, err := stateevent.Parse(m.Data)
			if err != nil {
				log.Printf("state validate error: %v", err)
				_ = m.Ack()
				continue
			}
			if i.dedup.IsDuplicate(ev.EventID, now) {
				_ = m.Ack()
				continue
			}
			occ, _ := time.Parse(time.RFC3339, ev.OccurredAt)
			if occ.IsZero() {
				occ = now
			}
			payload, _ := json.Marshal(ev.Payload)
			i.events = append(i.events, flush.StateEventRow{
				EventID: ev.EventID, AggregateType: ev.AggregateType, AggregateID: ev.AggregateID, EventType: ev.EventType,
				PayloadJSON: string(payload), OccurredAt: occ, Version: uint64(now.UnixNano()), Operation: ev.Operation, Source: "outbox",
			})
			i.pending = append(i.pending, m)
		}
		i.dedup.Cleanup(now)
		select {
		case <-ticker.C:
			if err := i.flush(ctx); err != nil {
				log.Printf("state flush error: %v", err)
			}
		default:
		}
	}
}

func (i *StateIngester) flush(ctx context.Context) error {
	if len(i.pending) == 0 {
		return nil
	}
	if err := i.writer.InsertStateEvents(ctx, i.events); err != nil {
		return err
	}
	if err := i.applyLatest(ctx); err != nil {
		return err
	}
	for _, m := range i.pending {
		_ = m.Ack()
	}
	i.pending = nil
	i.events = nil
	return nil
}

func (i *StateIngester) applyLatest(ctx context.Context) error {
	buckets := map[string]*struct {
		table string
		cols  []string
		rows  [][]interface{}
	}{}
	for _, ev := range i.events {
		var payload map[string]interface{}
		_ = json.Unmarshal([]byte(ev.PayloadJSON), &payload)
		deleted := uint8(0)
		if ev.Operation == "deleted" {
			deleted = 1
		}
		version := ev.Version
		switch ev.AggregateType {
		case "frontend_app":
			id := toInt(payload["id"])
			key := toString(payload["key"])
			addBucket(buckets, "frontend_apps_latest", []string{"app_id", "app_key", "payload_json", "version", "deleted"}, []interface{}{id, key, ev.PayloadJSON, version, deleted})
		case "frontend_release":
			id := toInt(payload["id"])
			appID := toInt(payload["app_id"])
			addBucket(buckets, "frontend_releases_latest", []string{"release_id", "app_id", "payload_json", "version", "deleted"}, []interface{}{id, appID, ev.PayloadJSON, version, deleted})
		case "frontend_profile":
			id := toInt(payload["id"])
			key := toString(payload["key"])
			addBucket(buckets, "frontend_profiles_latest", []string{"profile_id", "profile_key", "payload_json", "version", "deleted"}, []interface{}{id, key, ev.PayloadJSON, version, deleted})
		case "frontend_rule":
			id := toInt(payload["id"])
			profileID := toInt(payload["profile_id"])
			addBucket(buckets, "frontend_rules_latest", []string{"rule_id", "profile_id", "payload_json", "version", "deleted"}, []interface{}{id, profileID, ev.PayloadJSON, version, deleted})
		case "frontend_allowed_host":
			id := toInt(payload["id"])
			host := toString(payload["host"])
			addBucket(buckets, "frontend_allowed_hosts_latest", []string{"host_id", "host", "payload_json", "version", "deleted"}, []interface{}{id, host, ev.PayloadJSON, version, deleted})
		case "subscriber":
			id := toInt(payload["id"])
			chatID := toInt(payload["chat_id"])
			addBucket(buckets, "subscribers_latest", []string{"subscriber_id", "chat_id", "payload_json", "version", "deleted"}, []interface{}{id, chatID, ev.PayloadJSON, version, deleted})
		case "source":
			id := toInt(payload["id"])
			siteKey := toString(payload["site_key"])
			addBucket(buckets, "sources_latest", []string{"source_id", "site_key", "payload_json", "version", "deleted"}, []interface{}{id, siteKey, ev.PayloadJSON, version, deleted})
		case "settings_runtime":
			key := toString(payload["setting_key"])
			if key == "" {
				key = "runtime_settings"
			}
			addBucket(buckets, "settings_runtime_latest", []string{"setting_key", "payload_json", "version", "deleted"}, []interface{}{key, ev.PayloadJSON, version, deleted})
		case "frontend_runtime_state":
			addBucket(buckets, "settings_runtime_latest", []string{"setting_key", "payload_json", "version", "deleted"}, []interface{}{"frontend_runtime_state", ev.PayloadJSON, version, deleted})
		case "frontend_audit_log":
			id := toInt(payload["id"])
			addBucket(buckets, "frontend_audit_log_latest", []string{"log_id", "payload_json", "version", "deleted"}, []interface{}{id, ev.PayloadJSON, version, deleted})
		case "ops_run":
			id := toInt(payload["id"])
			sourceID := toInt(payload["source_id"])
			addBucket(buckets, "ops_runs_latest", []string{"run_id", "source_id", "payload_json", "version", "deleted"}, []interface{}{id, sourceID, ev.PayloadJSON, version, deleted})
		}
	}
	for _, b := range buckets {
		if err := i.writer.UpsertLatestState(ctx, b.table, b.cols, b.rows); err != nil {
			return err
		}
	}
	return nil
}

func addBucket(buckets map[string]*struct {
	table string
	cols  []string
	rows  [][]interface{}
}, table string, cols []string, row []interface{}) {
	b, ok := buckets[table]
	if !ok {
		b = &struct {
			table string
			cols  []string
			rows  [][]interface{}
		}{table: table, cols: cols}
		buckets[table] = b
	}
	b.rows = append(b.rows, row)
}

func toInt(v interface{}) int64 {
	switch x := v.(type) {
	case float64:
		return int64(x)
	case int:
		return int64(x)
	case int64:
		return x
	case string:
		n, _ := strconv.ParseInt(x, 10, 64)
		return n
	default:
		return 0
	}
}

func toString(v interface{}) string {
	if v == nil {
		return ""
	}
	switch x := v.(type) {
	case string:
		return x
	default:
		return ""
	}
}
