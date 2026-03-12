package state

import "analytics-aggregator/internal/schema"

func ApplyKPI(store *Store, ev *schema.EventEnvelope) []ChannelSnapshot {
	return store.Apply(ev)
}
