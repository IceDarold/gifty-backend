package stateevent

import (
	"encoding/json"
	"fmt"
	"time"
)

type Envelope struct {
	EventID       string                 `json:"event_id"`
	AggregateType string                 `json:"aggregate_type"`
	AggregateID   string                 `json:"aggregate_id"`
	EventType     string                 `json:"event_type"`
	Operation     string                 `json:"operation"`
	Version       int                    `json:"version"`
	OccurredAt    string                 `json:"occurred_at"`
	Payload       map[string]interface{} `json:"payload"`
	Headers       map[string]interface{} `json:"headers"`
}

func Parse(data []byte) (*Envelope, error) {
	var ev Envelope
	if err := json.Unmarshal(data, &ev); err != nil {
		return nil, err
	}
	if ev.EventID == "" || ev.AggregateType == "" || ev.AggregateID == "" || ev.EventType == "" || ev.Operation == "" || ev.OccurredAt == "" {
		return nil, fmt.Errorf("invalid state event envelope")
	}
	if _, err := time.Parse(time.RFC3339, ev.OccurredAt); err != nil {
		return nil, fmt.Errorf("invalid occurred_at: %w", err)
	}
	if ev.Payload == nil {
		ev.Payload = map[string]interface{}{}
	}
	if ev.Headers == nil {
		ev.Headers = map[string]interface{}{}
	}
	return &ev, nil
}
