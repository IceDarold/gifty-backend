package state

import "analytics-aggregator/internal/schema"

func ApplyLLM(store *Store, ev *schema.EventEnvelope) []ChannelSnapshot {
	return store.Apply(ev)
}
