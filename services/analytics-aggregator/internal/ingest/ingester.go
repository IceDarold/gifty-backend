package ingest

import (
	"context"
	"encoding/json"
	"log"
	"sort"
	"strings"
	"time"

	"analytics-aggregator/internal/dedup"
	"analytics-aggregator/internal/flush"
	"analytics-aggregator/internal/schema"

	"github.com/nats-io/nats.go"
)

type Ingester struct {
	js        nats.JetStreamContext
	sub       *nats.Subscription
	validator *schema.Validator
	dedup     *dedup.Cache
	writer    *flush.Writer

	pending []*nats.Msg
	events  []flush.EventRow
}

func New(url, stream, subject, durable string, validator *schema.Validator, dedupCache *dedup.Cache, writer *flush.Writer) (*Ingester, error) {
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
	return &Ingester{
		js:        js,
		sub:       sub,
		validator: validator,
		dedup:     dedupCache,
		writer:    writer,
	}, nil
}

func (i *Ingester) Run(ctx context.Context, flushInterval time.Duration) error {
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
			log.Printf("nats fetch error: %v", err)
		}
		now := time.Now().UTC()
		for _, m := range msgs {
			ev, err := i.validator.Validate(m.Data)
			if err != nil {
				log.Printf("nats validate error: %v", err)
				_ = m.Ack()
				continue
			}
			if i.dedup.IsDuplicate(ev.EventID, now) {
				_ = m.Ack()
				continue
			}
			i.events = append(i.events, expandEvent(ev)...)
			i.pending = append(i.pending, m)
		}
		i.dedup.Cleanup(now)

		select {
		case <-ticker.C:
			if err := i.flush(ctx); err != nil {
				log.Printf("flush error: %v", err)
			}
		default:
		}
	}
}

func (i *Ingester) flush(ctx context.Context) error {
	if len(i.pending) == 0 {
		return nil
	}
	if err := i.writer.InsertEvents(ctx, i.events); err != nil {
		return err
	}
	for _, m := range i.pending {
		_ = m.Ack()
	}
	i.pending = nil
	i.events = nil
	return nil
}

func expandEvent(ev *schema.EventEnvelope) []flush.EventRow {
	occurred, _ := time.Parse(time.RFC3339, ev.OccurredAt)
	if occurred.IsZero() {
		occurred = time.Now().UTC()
	}
	scope, scopeKey := scopeFor(ev)
	dims := dimsJSON(ev.Dims)
	payload := payloadJSON(ev.Payload)
	version := uint64(time.Now().UTC().UnixNano())

	baseValue := 1.0
	if v, ok := ev.Metrics["value"]; ok {
		baseValue = v
	}
	rows := []flush.EventRow{
		{
			EventID:     ev.EventID,
			OccurredAt:  occurred,
			EventType:   ev.EventType,
			Metric:      ev.EventType,
			Scope:       scope,
			ScopeKey:    scopeKey,
			DimsJSON:    dims,
			PayloadJSON: payload,
			Value:       baseValue,
			Version:     version,
		},
	}
	for k, v := range ev.Metrics {
		if k == "value" {
			continue
		}
		rows = append(rows, flush.EventRow{
			EventID:     ev.EventID,
			OccurredAt:  occurred,
			EventType:   ev.EventType,
			Metric:      ev.EventType + "." + k,
			Scope:       scope,
			ScopeKey:    scopeKey,
			DimsJSON:    dims,
			PayloadJSON: payload,
			Value:       v,
			Version:     version,
		})
	}
	return rows
}

func scopeFor(ev *schema.EventEnvelope) (string, string) {
	if strings.HasPrefix(ev.EventType, "llm.") {
		if p, ok := ev.Dims["provider"].(string); ok && p != "" {
			return "provider", p
		}
		return "provider", "unknown"
	}
	if strings.HasPrefix(ev.EventType, "ops.") {
		if s, ok := ev.Dims["site_key"].(string); ok && s != "" {
			return "site", s
		}
		return "global", "ops"
	}
	return "global", "kpi"
}

func dimsJSON(dims map[string]interface{}) string {
	if len(dims) == 0 {
		return "{}"
	}
	keys := make([]string, 0, len(dims))
	for k := range dims {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	norm := make(map[string]interface{}, len(dims))
	for _, k := range keys {
		norm[k] = dims[k]
	}
	b, _ := json.Marshal(norm)
	return string(b)
}

func payloadJSON(payload map[string]interface{}) string {
	if len(payload) == 0 {
		return "{}"
	}
	b, _ := json.Marshal(payload)
	return string(b)
}
