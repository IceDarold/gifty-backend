package ws

import (
	"encoding/json"
	"sync"
	"time"

	"analytics-aggregator/internal/state"
)

type outbound struct {
	Type    string      `json:"type"`
	Channel string      `json:"channel"`
	Seq     uint64      `json:"seq"`
	Data    interface{} `json:"data"`
	TS      string      `json:"ts"`
}

type Client interface {
	Send([]byte) error
	Close(code int, text string) error
}

type subscription struct {
	channels map[string]bool
}

type Hub struct {
	mu      sync.RWMutex
	clients map[Client]*subscription
}

func NewHub() *Hub {
	return &Hub{clients: make(map[Client]*subscription)}
}

func (h *Hub) Register(c Client) {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.clients[c] = &subscription{channels: make(map[string]bool)}
}

func (h *Hub) Unregister(c Client) {
	h.mu.Lock()
	defer h.mu.Unlock()
	delete(h.clients, c)
}

func (h *Hub) Subscribe(c Client, channels []string) {
	h.mu.Lock()
	defer h.mu.Unlock()
	s, ok := h.clients[c]
	if !ok {
		return
	}
	for _, ch := range channels {
		s.channels[ch] = true
	}
}

func (h *Hub) Unsubscribe(c Client, channels []string) {
	h.mu.Lock()
	defer h.mu.Unlock()
	s, ok := h.clients[c]
	if !ok {
		return
	}
	for _, ch := range channels {
		delete(s.channels, ch)
	}
}

func (h *Hub) Publish(updates []state.ChannelSnapshot) {
	h.mu.RLock()
	defer h.mu.RUnlock()
	for c, s := range h.clients {
		for _, u := range updates {
			if !s.channels[u.Channel] {
				continue
			}
			msg, _ := json.Marshal(outbound{
				Type:    "update",
				Channel: u.Channel,
				Seq:     u.Seq,
				Data:    u.Data,
				TS:      time.Now().UTC().Format(time.RFC3339),
			})
			if err := c.Send(msg); err != nil {
				_ = c.Close(4008, "slow consumer")
			}
		}
	}
}
