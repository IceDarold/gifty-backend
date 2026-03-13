package nats

import (
	"context"
	"log"
	"time"

	"analytics-aggregator/internal/dedup"
	"analytics-aggregator/internal/state"
	"analytics-aggregator/internal/stateevent"
	"analytics-aggregator/internal/ws"

	"github.com/nats-io/nats.go"
)

type StateResolver interface {
	Resolve(ctx context.Context, channel string, params map[string]interface{}) (interface{}, bool, error)
}

type StateEphemeralConsumer struct {
	nc       *nats.Conn
	sub      *nats.Subscription
	store    *state.Store
	dedup    *dedup.Cache
	hub      *ws.Hub
	resolver StateResolver
}

func NewStateEphemeral(url, subject string, resolver StateResolver, store *state.Store, dedupCache *dedup.Cache, hub *ws.Hub) (*StateEphemeralConsumer, error) {
	nc, err := nats.Connect(url)
	if err != nil {
		return nil, err
	}
	sub, err := nc.SubscribeSync(subject)
	if err != nil {
		return nil, err
	}
	return &StateEphemeralConsumer{nc: nc, sub: sub, resolver: resolver, store: store, dedup: dedupCache, hub: hub}, nil
}

func (c *StateEphemeralConsumer) Run(ctx context.Context) error {
	for {
		select {
		case <-ctx.Done():
			return nil
		default:
		}
		msg, err := c.sub.NextMsg(2 * time.Second)
		if err != nil && err != nats.ErrTimeout {
			log.Printf("nats state ephemeral error: %v", err)
			continue
		}
		if msg == nil {
			continue
		}
		ev, err := stateevent.Parse(msg.Data)
		if err != nil {
			continue
		}
		now := time.Now().UTC()
		if c.dedup.IsDuplicate(ev.EventID, now) {
			continue
		}
		for _, ch := range channelsForAggregate(ev.AggregateType) {
			data, ok, err := c.resolver.Resolve(ctx, ch, nil)
			if err != nil || !ok {
				continue
			}
			snap := c.store.SetChannel(ch, data)
			c.hub.Publish([]state.ChannelSnapshot{snap})
		}
		c.dedup.Cleanup(now)
	}
}

func channelsForAggregate(aggregate string) []string {
	switch aggregate {
	case "source":
		return []string{"dashboard.sources"}
	case "subscriber":
		return []string{"settings.subscribers"}
	case "settings_runtime":
		return []string{"settings.runtime"}
	case "frontend_runtime_state":
		return []string{"frontend.runtime_state"}
	case "frontend_app":
		return []string{"frontend.apps"}
	case "frontend_release":
		return []string{"frontend.releases"}
	case "frontend_profile":
		return []string{"frontend.profiles"}
	case "frontend_rule":
		return []string{"frontend.rules"}
	case "frontend_allowed_host":
		return []string{"frontend.allowed_hosts"}
	case "frontend_audit_log":
		return []string{"frontend.audit_log"}
	case "ops_run":
		return []string{"ops.runs.active", "ops.runs.queued", "ops.runs.completed", "ops.runs.error", "ops.run_details"}
	default:
		return nil
	}
}
