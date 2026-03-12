package state

import "analytics-aggregator/internal/schema"

func ApplyOps(store *Store, ev *schema.EventEnvelope) []ChannelSnapshot {
	return store.Apply(ev)
}
