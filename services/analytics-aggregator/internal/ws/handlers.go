package ws

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"analytics-aggregator/internal/state"
	"github.com/gorilla/websocket"
)

type SnapshotProvider interface {
	Snapshot(channels []string) []state.ChannelSnapshot
}

type Handler struct {
	hub        *Hub
	store      SnapshotProvider
	wsToken    string
	upgrader   websocket.Upgrader
	resolver   ChannelResolver
	defaultTTL time.Duration
	ttlMap     map[string]time.Duration
	forceMap   map[string]bool
}

type wsClient struct {
	conn      *websocket.Conn
	send      chan []byte
	mu        sync.Mutex
	closeOnce sync.Once
	closed    atomic.Bool
}

type ChannelResolver interface {
	Resolve(ctx context.Context, channel string, params map[string]interface{}) (interface{}, bool, error)
}

func (c *wsClient) Send(msg []byte) (err error) {
	if c.closed.Load() {
		return fmt.Errorf("client closed")
	}
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("client closed")
		}
	}()
	select {
	case c.send <- msg:
		return nil
	default:
		return fmt.Errorf("send buffer full")
	}
}

func (c *wsClient) Close(code int, text string) error {
	var err error
	c.closeOnce.Do(func() {
		c.mu.Lock()
		defer c.mu.Unlock()
		c.closed.Store(true)
		_ = c.conn.WriteControl(websocket.CloseMessage, websocket.FormatCloseMessage(code, text), time.Now().Add(time.Second))
		err = c.conn.Close()
		close(c.send)
	})
	return err
}

func (c *wsClient) runWriter() {
	for msg := range c.send {
		c.mu.Lock()
		_ = c.conn.SetWriteDeadline(time.Now().Add(5 * time.Second))
		err := c.conn.WriteMessage(websocket.TextMessage, msg)
		c.mu.Unlock()
		if err != nil {
			_ = c.Close(4008, "slow consumer")
			return
		}
	}
}

type HandlerOptions struct {
	DefaultTTL time.Duration
	TTLMap     map[string]time.Duration
	ForceMap   map[string]bool
}

func NewHandler(hub *Hub, store SnapshotProvider, token string, resolver ChannelResolver, opts HandlerOptions) *Handler {
	return &Handler{
		hub:        hub,
		store:      store,
		wsToken:    token,
		resolver:   resolver,
		defaultTTL: opts.DefaultTTL,
		ttlMap:     opts.TTLMap,
		forceMap:   opts.ForceMap,
		upgrader: websocket.Upgrader{
			CheckOrigin: func(r *http.Request) bool { return true },
		},
	}
}

func (h *Handler) resolveTTLFor(channel string) time.Duration {
	if h.forceMap != nil && h.forceMap[channel] {
		return 0
	}
	if h.ttlMap != nil {
		if ttl, ok := h.ttlMap[channel]; ok {
			return ttl
		}
		for key, ttl := range h.ttlMap {
			if strings.HasSuffix(key, "*") {
				prefix := strings.TrimSuffix(key, "*")
				if prefix != "" && strings.HasPrefix(channel, prefix) {
					return ttl
				}
			}
		}
	}
	return h.defaultTTL
}

func (h *Handler) ServeWS(w http.ResponseWriter, r *http.Request) {
	if h.wsToken != "" {
		auth := r.Header.Get("Authorization")
		queryToken := strings.TrimSpace(r.URL.Query().Get("access_token"))
		if queryToken == "" {
			queryToken = strings.TrimSpace(r.URL.Query().Get("token"))
		}
		if queryToken == "" && strings.HasPrefix(auth, "Bearer ") {
			queryToken = strings.TrimSpace(strings.TrimPrefix(auth, "Bearer "))
		}
		if queryToken != h.wsToken {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
	}
	conn, err := h.upgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}
	client := &wsClient{conn: conn, send: make(chan []byte, 256)}
	h.hub.Register(client)
	go client.runWriter()
	defer h.hub.Unregister(client)
	defer conn.Close()

	for {
		_, data, err := conn.ReadMessage()
		if err != nil {
			return
		}
		var msg map[string]interface{}
		if err := json.Unmarshal(data, &msg); err != nil {
			continue
		}
		t, _ := msg["type"].(string)
		switch t {
		case "ping":
			_ = client.Send([]byte(`{"type":"heartbeat"}`))
		case "subscribe":
			var channels []string
			if arr, ok := msg["channels"].([]interface{}); ok {
				for _, v := range arr {
					if s, ok := v.(string); ok {
						channels = append(channels, s)
					}
				}
			}
			h.hub.Subscribe(client, channels)
			for _, snap := range h.store.Snapshot(channels) {
				out, _ := json.Marshal(map[string]interface{}{
					"type":    "snapshot",
					"channel": snap.Channel,
					"seq":     snap.Seq,
					"data":    snap.Data,
				})
				_ = client.Send(out)
			}
			if h.resolver != nil {
				for _, ch := range channels {
					shouldResolve := true
					if snapData, ok := h.store.(*state.Store); ok {
						_, _, updatedAt, has := snapData.GetChannelInfo(ch)
						if has {
							ttl := h.resolveTTLFor(ch)
							if ttl > 0 && !updatedAt.IsZero() && time.Since(updatedAt) <= ttl {
								shouldResolve = false
							}
						}
					}
					if !shouldResolve {
						continue
					}
					go func(channel string) {
						data, ok, _ := h.resolver.Resolve(r.Context(), channel, nil)
						if ok {
							if store, ok := h.store.(*state.Store); ok {
								snap := store.SetChannel(channel, data)
								h.hub.Publish([]state.ChannelSnapshot{snap})
								out, _ := json.Marshal(map[string]interface{}{
									"type":    "snapshot",
									"channel": snap.Channel,
									"seq":     snap.Seq,
									"data":    snap.Data,
								})
								_ = client.Send(out)
							}
						}
					}(ch)
				}
			}
		case "request":
			reqID, _ := msg["req_id"].(string)
			channel, _ := msg["channel"].(string)
			params := map[string]interface{}{}
			if raw, ok := msg["params"].(map[string]interface{}); ok {
				params = raw
			}
			if channel == "" || h.resolver == nil {
				_ = client.Send([]byte(`{"type":"error","code":"INVALID_REQUEST","message":"missing channel"}`))
				continue
			}
			data, ok, err := h.resolver.Resolve(r.Context(), channel, params)
			if err != nil || !ok {
				out, _ := json.Marshal(map[string]interface{}{
					"type":   "error",
					"req_id": reqID,
					"code":   "RESOLVE_FAILED",
					"message": func() string {
						if err != nil {
							return err.Error()
						}
						return "not found"
					}(),
				})
				_ = client.Send(out)
				continue
			}
			out, _ := json.Marshal(map[string]interface{}{
				"type":    "snapshot",
				"channel": channel,
				"seq":     0,
				"data":    data,
				"req_id":  reqID,
			})
			_ = client.Send(out)
		case "unsubscribe":
			var channels []string
			if arr, ok := msg["channels"].([]interface{}); ok {
				for _, v := range arr {
					if s, ok := v.(string); ok {
						channels = append(channels, s)
					}
				}
			}
			h.hub.Unsubscribe(client, channels)
		}
	}
}
