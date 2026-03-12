package ws

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"analytics-aggregator/internal/state"
	"github.com/gorilla/websocket"
)

type SnapshotProvider interface {
	Snapshot(channels []string) []state.ChannelSnapshot
}

type Handler struct {
	hub      *Hub
	store    SnapshotProvider
	wsToken  string
	upgrader websocket.Upgrader
	resolver ChannelResolver
}

type wsClient struct {
	conn *websocket.Conn
}

type ChannelResolver interface {
	Resolve(ctx context.Context, channel string, params map[string]interface{}) (interface{}, bool, error)
}

func (c *wsClient) Send(msg []byte) error {
	_ = c.conn.SetWriteDeadline(time.Now().Add(5 * time.Second))
	return c.conn.WriteMessage(websocket.TextMessage, msg)
}

func (c *wsClient) Close(code int, text string) error {
	_ = c.conn.WriteControl(websocket.CloseMessage, websocket.FormatCloseMessage(code, text), time.Now().Add(time.Second))
	return c.conn.Close()
}

func NewHandler(hub *Hub, store SnapshotProvider, token string, resolver ChannelResolver) *Handler {
	return &Handler{
		hub:      hub,
		store:    store,
		wsToken:  token,
		resolver: resolver,
		upgrader: websocket.Upgrader{
			CheckOrigin: func(r *http.Request) bool { return true },
		},
	}
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
	client := &wsClient{conn: conn}
	h.hub.Register(client)
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
					if snapData, ok := h.store.(*state.Store); ok {
						if _, _, has := snapData.GetChannel(ch); has {
							continue
						}
					}
					data, ok, _ := h.resolver.Resolve(r.Context(), ch, nil)
					if ok {
						if store, ok := h.store.(*state.Store); ok {
							snap := store.SetChannel(ch, data)
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
