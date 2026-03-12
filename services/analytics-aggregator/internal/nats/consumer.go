package nats

import (
	"context"
	"log"
	"time"

	"analytics-aggregator/internal/dedup"
	"analytics-aggregator/internal/schema"
	"analytics-aggregator/internal/state"
	"analytics-aggregator/internal/ws"

	"github.com/nats-io/nats.go"
)

type Consumer struct {
	js        nats.JetStreamContext
	sub       *nats.Subscription
	validator *schema.Validator
	store     *state.Store
	dedup     *dedup.Cache
	hub       *ws.Hub
}

func New(url, stream, subject, durable string, validator *schema.Validator, store *state.Store, dedupCache *dedup.Cache, hub *ws.Hub) (*Consumer, error) {
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
	return &Consumer{js: js, sub: sub, validator: validator, store: store, dedup: dedupCache, hub: hub}, nil
}

func (c *Consumer) Run(ctx context.Context) error {
	for {
		select {
		case <-ctx.Done():
			return nil
		default:
		}
		msgs, err := c.sub.Fetch(100, nats.MaxWait(2*time.Second))
		if err != nil && err != nats.ErrTimeout {
			log.Printf("nats fetch error: %v", err)
			continue
		}
		now := time.Now().UTC()
		for _, m := range msgs {
			ev, err := c.validator.Validate(m.Data)
			if err != nil {
				log.Printf("nats validate error: %v", err)
				_ = m.Ack()
				continue
			}
			if c.dedup.IsDuplicate(ev.EventID, now) {
				_ = m.Ack()
				continue
			}
			updates := c.store.Apply(ev)
			log.Printf("nats event applied type=%s updates=%d", ev.EventType, len(updates))
			c.hub.Publish(updates)
			_ = m.Ack()
		}
		c.dedup.Cleanup(now)
	}
}
