package state

import (
	"encoding/json"
	"math"
	"sort"
	"strings"
	"sync"
	"time"

	"analytics-aggregator/internal/schema"
)

type BucketKey struct {
	BucketMinute time.Time
	Metric       string
	Scope        string
	ScopeKey     string
	DimsJSON     string
}

type BucketValue struct {
	Count     uint64
	Sum       float64
	Min       float64
	Max       float64
	UpdatedAt time.Time
	Version   uint64
}

type ChannelSnapshot struct {
	Channel string      `json:"channel"`
	Seq     uint64      `json:"seq"`
	Data    interface{} `json:"data"`
}

type Store struct {
	mu       sync.RWMutex
	buckets  map[BucketKey]*BucketValue
	channels map[string]interface{}
	seq      map[string]uint64
	updated  map[string]time.Time
}

func NewStore() *Store {
	return &Store{
		buckets:  make(map[BucketKey]*BucketValue),
		channels: make(map[string]interface{}),
		seq:      make(map[string]uint64),
		updated:  make(map[string]time.Time),
	}
}

func minute(ts time.Time) time.Time {
	return ts.UTC().Truncate(time.Minute)
}

func dimsJSON(dims map[string]interface{}) string {
	if len(dims) == 0 {
		return "{}"
	}
	keys := make([]string, 0, len(dims))
	for k := range dims {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	norm := make(map[string]interface{}, len(dims))
	for _, k := range keys {
		norm[k] = dims[k]
	}
	b, _ := json.Marshal(norm)
	return string(b)
}

func scopeFor(ev *schema.EventEnvelope) (string, string) {
	if strings.HasPrefix(ev.EventType, "llm.") {
		if p, ok := ev.Dims["provider"].(string); ok && p != "" {
			return "provider", p
		}
		return "provider", "unknown"
	}
	if strings.HasPrefix(ev.EventType, "ops.") {
		if s, ok := ev.Dims["site_key"].(string); ok && s != "" {
			return "site", s
		}
		return "global", "ops"
	}
	return "global", "kpi"
}

func channelFor(ev *schema.EventEnvelope) []string {
	if strings.HasPrefix(ev.EventType, "kpi.") {
		channels := []string{"global.kpi"}
		if ev.EventType == "kpi.quiz_started" || ev.EventType == "kpi.quiz_completed" {
			channels = append(channels, "global.funnel")
		}
		if ev.EventType == "kpi.results_shown" || ev.EventType == "kpi.gift_clicked" {
			channels = append(channels, "global.trends")
		}
		return channels
	}
	if strings.HasPrefix(ev.EventType, "llm.") {
		provider := "unknown"
		if p, ok := ev.Dims["provider"].(string); ok && p != "" {
			provider = p
		}
		return []string{"llm.summary", "llm.breakdown." + provider}
	}
	if strings.HasPrefix(ev.EventType, "ops.") {
		if s, ok := ev.Dims["site_key"].(string); ok && s != "" {
			return []string{"ops.metrics", "ops.site." + s}
		}
		return []string{"ops.metrics"}
	}
	return []string{"global.kpi"}
}

func (s *Store) Apply(ev *schema.EventEnvelope) []ChannelSnapshot {
	occurred, _ := time.Parse(time.RFC3339, ev.OccurredAt)
	if occurred.IsZero() {
		occurred = time.Now().UTC()
	}
	scope, scopeKey := scopeFor(ev)

	s.mu.Lock()
	defer s.mu.Unlock()

	bucketAt := minute(occurred)
	dims := dimsJSON(ev.Dims)

	// Base metric (event count/value)
	baseValue := 1.0
	if v, ok := ev.Metrics["value"]; ok {
		baseValue = v
	}
	if math.IsNaN(baseValue) || math.IsInf(baseValue, 0) {
		baseValue = 0
	}
	s.applyMetric(bucketAt, ev.EventType, scope, scopeKey, dims, baseValue)

	// Additional metrics per event
	for k, v := range ev.Metrics {
		if k == "value" {
			continue
		}
		val := v
		if math.IsNaN(val) || math.IsInf(val, 0) {
			val = 0
		}
		metric := ev.EventType + "." + k
		s.applyMetric(bucketAt, metric, scope, scopeKey, dims, val)
	}

	channels := channelFor(ev)
	bk := BucketKey{
		BucketMinute: bucketAt,
		Metric:       ev.EventType,
		Scope:        scope,
		ScopeKey:     scopeKey,
		DimsJSON:     dims,
	}
	cur := s.buckets[bk]
	out := make([]ChannelSnapshot, 0, len(channels))
	for _, ch := range channels {
		s.seq[ch]++
		data := map[string]interface{}{
			"event_type":    ev.EventType,
			"scope":         scope,
			"scope_key":     scopeKey,
			"count":         cur.Count,
			"sum":           cur.Sum,
			"min":           cur.Min,
			"max":           cur.Max,
			"bucket_minute": bk.BucketMinute.Format(time.RFC3339),
		}
		s.channels[ch] = data
		s.updated[ch] = time.Now().UTC()
		out = append(out, ChannelSnapshot{Channel: ch, Seq: s.seq[ch], Data: data})
	}
	return out
}

func (s *Store) applyMetric(bucketAt time.Time, metric, scope, scopeKey, dims string, value float64) {
	bk := BucketKey{
		BucketMinute: bucketAt,
		Metric:       metric,
		Scope:        scope,
		ScopeKey:     scopeKey,
		DimsJSON:     dims,
	}
	cur := s.buckets[bk]
	if cur == nil {
		cur = &BucketValue{Min: value, Max: value}
		s.buckets[bk] = cur
	}
	cur.Count++
	cur.Sum += value
	if value < cur.Min {
		cur.Min = value
	}
	if value > cur.Max {
		cur.Max = value
	}
	cur.UpdatedAt = time.Now().UTC()
	cur.Version++
}

func (s *Store) Snapshot(channels []string) []ChannelSnapshot {
	s.mu.RLock()
	defer s.mu.RUnlock()
	if len(channels) == 0 {
		channels = make([]string, 0, len(s.channels))
		for ch := range s.channels {
			channels = append(channels, ch)
		}
		sort.Strings(channels)
	}
	out := make([]ChannelSnapshot, 0, len(channels))
	for _, ch := range channels {
		data, ok := s.channels[ch]
		if !ok {
			continue
		}
		out = append(out, ChannelSnapshot{Channel: ch, Seq: s.seq[ch], Data: data})
	}
	return out
}

func (s *Store) SetChannel(channel string, data interface{}) ChannelSnapshot {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.seq[channel]++
	s.channels[channel] = data
	s.updated[channel] = time.Now().UTC()
	return ChannelSnapshot{Channel: channel, Seq: s.seq[channel], Data: data}
}

func (s *Store) GetChannel(channel string) (interface{}, uint64, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	data, ok := s.channels[channel]
	if !ok {
		return nil, 0, false
	}
	return data, s.seq[channel], true
}

func (s *Store) GetChannelInfo(channel string) (interface{}, uint64, time.Time, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	data, ok := s.channels[channel]
	if !ok {
		return nil, 0, time.Time{}, false
	}
	return data, s.seq[channel], s.updated[channel], true
}

func (s *Store) Buckets() map[BucketKey]BucketValue {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make(map[BucketKey]BucketValue, len(s.buckets))
	for k, v := range s.buckets {
		out[k] = *v
	}
	return out
}

func (s *Store) LoadBuckets(data map[BucketKey]BucketValue) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.buckets = make(map[BucketKey]*BucketValue, len(data))
	for k, v := range data {
		vv := v
		s.buckets[k] = &vv
	}
}

func (s *Store) ResetBuckets() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.buckets = make(map[BucketKey]*BucketValue)
}
