package http

import (
	"encoding/json"
	"net/http"
	"strings"

	"analytics-aggregator/internal/state"
	"analytics-aggregator/internal/ws"
	"github.com/go-chi/chi/v5"
)

func Router(store *state.Store, wsHandler *ws.Handler) http.Handler {
	r := chi.NewRouter()
	r.Use(func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.Header().Set("Access-Control-Allow-Origin", "*")
			w.Header().Set("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers", "Authorization,Content-Type")
			if r.Method == http.MethodOptions {
				w.WriteHeader(http.StatusNoContent)
				return
			}
			next.ServeHTTP(w, r)
		})
	})

	r.Get("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"status":"ok"}`))
	})

	r.Get("/api/v1/live-analytics/snapshot", func(w http.ResponseWriter, r *http.Request) {
		channelsParam := strings.TrimSpace(r.URL.Query().Get("channels"))
		var channels []string
		if channelsParam != "" {
			for _, c := range strings.Split(channelsParam, ",") {
				c = strings.TrimSpace(c)
				if c != "" {
					channels = append(channels, c)
				}
			}
		}
		out := map[string]interface{}{"items": store.Snapshot(channels)}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(out)
	})

	r.Get("/api/v1/live-analytics/ws", wsHandler.ServeWS)
	return r
}
