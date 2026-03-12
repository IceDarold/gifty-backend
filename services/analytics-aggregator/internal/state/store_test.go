package state

import (
	"testing"
	"time"

	"analytics-aggregator/internal/schema"
)

func TestStoreApplyAndSnapshot(t *testing.T) {
	s := NewStore()
	ev := &schema.EventEnvelope{
		EventID:    "e1",
		EventType:  "kpi.quiz_started",
		OccurredAt: time.Now().UTC().Format(time.RFC3339),
		Dims:       map[string]interface{}{},
		Metrics:    map[string]float64{"value": 1},
	}
	updates := s.Apply(ev)
	if len(updates) == 0 {
		t.Fatal("expected updates")
	}
	sn := s.Snapshot([]string{"global.kpi"})
	if len(sn) != 1 {
		t.Fatalf("expected one snapshot, got %d", len(sn))
	}
}
