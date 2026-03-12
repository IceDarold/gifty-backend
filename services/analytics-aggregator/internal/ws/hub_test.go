package ws

import (
	"errors"
	"testing"

	"analytics-aggregator/internal/state"
)

type fakeClient struct {
	messages [][]byte
	fail     bool
}

func (f *fakeClient) Send(b []byte) error {
	if f.fail {
		return errors.New("fail")
	}
	f.messages = append(f.messages, b)
	return nil
}

func (f *fakeClient) Close(code int, text string) error { return nil }

func TestHubPublish(t *testing.T) {
	h := NewHub()
	c := &fakeClient{}
	h.Register(c)
	h.Subscribe(c, []string{"global.kpi"})
	h.Publish([]state.ChannelSnapshot{{Channel: "global.kpi", Seq: 1, Data: map[string]interface{}{"x": 1}}})
	if len(c.messages) != 1 {
		t.Fatalf("expected 1 message, got %d", len(c.messages))
	}
}
