package ws

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"analytics-aggregator/internal/state"
)

type snapshotStub struct{}

func (snapshotStub) Snapshot(channels []string) []state.ChannelSnapshot { return nil }

func TestServeWSRejectsUnauthorizedRequest(t *testing.T) {
	hub := NewHub()
	handler := NewHandler(hub, snapshotStub{}, "secret-token", nil, HandlerOptions{})
	req := httptest.NewRequest(http.MethodGet, "/api/v1/live-analytics/ws", nil)
	rr := httptest.NewRecorder()

	handler.ServeWS(rr, req)

	if rr.Code != http.StatusUnauthorized {
		t.Fatalf("expected status %d, got %d", http.StatusUnauthorized, rr.Code)
	}
}

func TestServeWSAcceptsQueryToken(t *testing.T) {
	hub := NewHub()
	handler := NewHandler(hub, snapshotStub{}, "secret-token", nil, HandlerOptions{})
	req := httptest.NewRequest(http.MethodGet, "/api/v1/live-analytics/ws?access_token=secret-token", nil)
	rr := httptest.NewRecorder()

	handler.ServeWS(rr, req)

	if rr.Code == http.StatusUnauthorized {
		t.Fatalf("expected non-401 status, got %d", rr.Code)
	}
}
