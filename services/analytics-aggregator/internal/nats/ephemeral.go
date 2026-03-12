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

type EphemeralConsumer struct {
	nc        *nats.Conn
	sub       *nats.Subscription
	validator *schema.Validator
	store     *state.Store
	dedup     *dedup.Cache
	hub       *ws.Hub
}

func NewEphemeral(url, subject string, validator *schema.Validator, store *state.Store, dedupCache *dedup.Cache, hub *ws.Hub) (*EphemeralConsumer, error) {
	nc, err := nats.Connect(url)
	if err != nil {
		return nil, err
	}
	sub, err := nc.SubscribeSync(subject)
	if err != nil {
		return nil, err
	}
	return &EphemeralConsumer{nc: nc, sub: sub, validator: validator, store: store, dedup: dedupCache, hub: hub}, nil
}

func (c *EphemeralConsumer) Run(ctx context.Context) error {
	for {
		select {
		case <-ctx.Done():
			return nil
		default:
		}
		msg, err := c.sub.NextMsg(2 * time.Second)
		if err != nil && err != nats.ErrTimeout {
			log.Printf("nats ephemeral error: %v", err)
			continue
		}
		if msg == nil {
			continue
		}
		ev, err := c.validator.Validate(msg.Data)
		if err != nil {
			continue
		}
		now := time.Now().UTC()
		if c.dedup.IsDuplicate(ev.EventID, now) {
			continue
		}
		updates := c.store.Apply(ev)
		c.hub.Publish(updates)
		c.dedup.Cleanup(now)
	}
}
