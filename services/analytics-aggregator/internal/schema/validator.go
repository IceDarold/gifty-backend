package schema

import (
	"encoding/json"
	"fmt"
	"os"
	"time"

	jsonschema "github.com/santhosh-tekuri/jsonschema/v5"
)

type EventEnvelope struct {
	EventID    string                 `json:"event_id"`
	EventType  string                 `json:"event_type"`
	Version    int                    `json:"version"`
	OccurredAt string                 `json:"occurred_at"`
	Source     string                 `json:"source"`
	TenantID   string                 `json:"tenant_id"`
	SessionID  *string                `json:"session_id"`
	UserID     *string                `json:"user_id"`
	Dims       map[string]interface{} `json:"dims"`
	Metrics    map[string]float64     `json:"metrics"`
	Payload    map[string]interface{} `json:"payload"`
}

type Validator struct {
	schema *jsonschema.Schema
}

func NewValidator(schemaPath string) (*Validator, error) {
	compiler := jsonschema.NewCompiler()
	f, err := os.Open(schemaPath)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	if err := compiler.AddResource("schema.json", f); err != nil {
		return nil, err
	}
	s, err := compiler.Compile("schema.json")
	if err != nil {
		return nil, err
	}
	return &Validator{schema: s}, nil
}

func (v *Validator) Validate(data []byte) (*EventEnvelope, error) {
	var raw interface{}
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, err
	}
	if err := v.schema.Validate(raw); err != nil {
		return nil, err
	}

	var ev EventEnvelope
	if err := json.Unmarshal(data, &ev); err != nil {
		return nil, err
	}
	if _, err := time.Parse(time.RFC3339, ev.OccurredAt); err != nil {
		return nil, fmt.Errorf("invalid occurred_at: %w", err)
	}
	return &ev, nil
}
