package adminresolver

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"

	"analytics-aggregator/internal/chquery"
	"analytics-aggregator/internal/config"
)

type Resolver struct {
	cfg    config.Config
	client *http.Client
	ch     *chquery.Client
}

func New(cfg config.Config) *Resolver {
	chClient, _ := chquery.New(cfg.ClickHouseDSN)
	return &Resolver{
		cfg: cfg,
		client: &http.Client{
			Timeout: 10 * time.Second,
		},
		ch: chClient,
	}
}

func (r *Resolver) Resolve(ctx context.Context, channel string, params map[string]interface{}) (interface{}, bool, error) {
	switch {
	case strings.HasPrefix(channel, "dashboard.source_detail:"):
		id := strings.TrimPrefix(channel, "dashboard.source_detail:")
		if id == "" {
			return nil, false, nil
		}
		sources, err := r.snapshotData(ctx, "dashboard.sources")
		if err != nil {
			return nil, false, err
		}
		item := findByID(sources, id)
		return item, true, nil
	case strings.HasPrefix(channel, "dashboard.source_products:"):
		id := strings.TrimPrefix(channel, "dashboard.source_products:")
		if id == "" {
			return nil, false, nil
		}
		payload, err := r.snapshotData(ctx, "dashboard.source_products:"+id)
		if err != nil {
			return nil, false, err
		}
		return payload, true, nil
	case strings.HasPrefix(channel, "settings.subscriber:"):
		id := strings.TrimPrefix(channel, "settings.subscriber:")
		if id == "" {
			return nil, false, nil
		}
		subscribers, err := r.snapshotData(ctx, "settings.subscribers")
		if err != nil {
			return nil, false, err
		}
		item := findByID(subscribers, id)
		if item == nil {
			return nil, true, nil
		}
		return item, true, nil
	case strings.HasPrefix(channel, "ops.run_detail:"):
		id := strings.TrimPrefix(channel, "ops.run_detail:")
		if id == "" {
			return nil, false, nil
		}
		details, err := r.snapshotData(ctx, "ops.run_details")
		if err != nil {
			return nil, false, err
		}
		return findInMap(details, id), true, nil
	case channel == "ops.sites":
		out, err := r.snapshotData(ctx, "ops.sites")
		if err != nil {
			return nil, false, err
		}
		return out, true, nil
	case channel == "ops.discovery_detail":
		id, ok := toInt(params["id"])
		if !ok || id <= 0 {
			return nil, false, nil
		}
		items, err := r.snapshotData(ctx, "ops.discovery")
		if err != nil {
			return nil, false, err
		}
		item := findByID(items, strconv.Itoa(id))
		return item, true, nil
	case channel == "ops.source_items_trend":
		sourceID, ok := toInt(params["source_id"])
		if !ok || sourceID <= 0 {
			return nil, false, nil
		}
		granularity := "day"
		if v, ok := params["granularity"]; ok {
			granularity = fmt.Sprintf("%v", v)
		}
		buckets := 30
		if v, ok := toInt(params["buckets"]); ok && v > 0 {
			buckets = v
		}
		data, err := r.snapshotData(ctx, "ops.source_items_trend")
		if err != nil {
			return nil, false, err
		}
		out := extractSourceTrend(data, sourceID, granularity, buckets)
		return out, true, nil
	case channel == "llm.logs":
		if r.ch == nil {
			return nil, false, fmt.Errorf("clickhouse not configured")
		}
		limit, offset, filters := parseLLMFilters(params)
		days := parseDays(params, 7)
		items, total, err := r.ch.LLMLogs(ctx, days, limit, offset, filters)
		if err != nil {
			return nil, false, err
		}
		return map[string]interface{}{"items": items, "total": total}, true, nil
	case channel == "llm.throughput":
		if r.ch == nil {
			return nil, false, fmt.Errorf("clickhouse not configured")
		}
		days := parseDays(params, 7)
		bucket := "hour"
		if v, ok := params["bucket"]; ok {
			bucket = fmt.Sprintf("%v", v)
		}
		items, err := r.ch.LLMThroughput(ctx, days, bucket)
		if err != nil {
			return nil, false, err
		}
		return map[string]interface{}{"items": items}, true, nil
	case channel == "llm.stats":
		if r.ch == nil {
			return nil, false, fmt.Errorf("clickhouse not configured")
		}
		days := parseDays(params, 7)
		out, err := r.ch.LLMStats(ctx, days)
		if err != nil {
			return nil, false, err
		}
		return out, true, nil
	case channel == "llm.outliers":
		if r.ch == nil {
			return nil, false, fmt.Errorf("clickhouse not configured")
		}
		limit, _, filters := parseLLMFilters(params)
		days := parseDays(params, 7)
		items, err := r.ch.LLMOutliers(ctx, days, limit, filters)
		if err != nil {
			return nil, false, err
		}
		return map[string]interface{}{"items": items}, true, nil
	case strings.HasPrefix(channel, "llm.breakdown."):
		group := strings.TrimPrefix(channel, "llm.breakdown.")
		if group == "" {
			return nil, false, nil
		}
		if r.ch == nil {
			return nil, false, fmt.Errorf("clickhouse not configured")
		}
		days := parseDays(params, 7)
		items, err := r.ch.LLMBreakdown(ctx, days, group)
		if err != nil {
			return nil, false, err
		}
		return map[string]interface{}{"items": items}, true, nil
	case channel == "catalog.categories":
		limit, offset, search := parsePaging(params)
		sources, err := r.snapshotData(ctx, "dashboard.sources")
		if err != nil {
			return nil, false, err
		}
		filtered := filterCategories(normalizeList(sources), search)
		paged := slicePage(filtered, offset, limit)
		return map[string]interface{}{
			"items": paged,
			"total": len(filtered),
		}, true, nil
	case channel == "catalog.products":
		limit, offset, search := parsePaging(params)
		merchant := ""
		if v, ok := params["merchant"]; ok {
			merchant = fmt.Sprintf("%v", v)
		}
		itemsRaw, err := r.snapshotData(ctx, "catalog.products")
		if err != nil {
			return nil, false, err
		}
		items := normalizeList(itemsRaw)
		filtered := filterProducts(items, search, merchant)
		paged := slicePage(filtered, offset, limit)
		return map[string]interface{}{
			"items": paged,
			"total": len(filtered),
		}, true, nil
	default:
		return nil, false, nil
	}
}

func parsePaging(params map[string]interface{}) (limit int, offset int, search string) {
	limit = 200
	offset = 0
	search = ""
	if v, ok := params["limit"]; ok {
		if i, ok := toInt(v); ok {
			limit = i
		}
	}
	if v, ok := params["offset"]; ok {
		if i, ok := toInt(v); ok {
			offset = i
		}
	}
	if v, ok := params["search"]; ok {
		search = fmt.Sprintf("%v", v)
	}
	return
}

func (r *Resolver) snapshotData(ctx context.Context, channel string) (interface{}, error) {
	if r.ch == nil {
		return nil, fmt.Errorf("clickhouse not configured")
	}
	return r.ch.SnapshotData(ctx, channel)
}

func normalizeList(data interface{}) []map[string]interface{} {
	items := make([]map[string]interface{}, 0)
	switch v := data.(type) {
	case []interface{}:
		for _, it := range v {
			if row, ok := it.(map[string]interface{}); ok {
				items = append(items, row)
			}
		}
	case []map[string]interface{}:
		items = append(items, v...)
	case map[string]interface{}:
		if raw, ok := v["items"]; ok {
			items = normalizeList(raw)
		}
	}
	return items
}

func findByID(data interface{}, id string) map[string]interface{} {
	if id == "" {
		return nil
	}
	for _, item := range normalizeList(data) {
		if fmt.Sprintf("%v", item["id"]) == id {
			return item
		}
		if fmt.Sprintf("%v", item["chat_id"]) == id {
			return item
		}
	}
	return nil
}

func findInMap(data interface{}, id string) interface{} {
	if id == "" {
		return nil
	}
	if m, ok := data.(map[string]interface{}); ok {
		if v, ok := m[id]; ok {
			return v
		}
		if v, ok := m[strings.TrimSpace(id)]; ok {
			return v
		}
	}
	return nil
}

func extractSourceTrend(data interface{}, sourceID int, granularity string, buckets int) interface{} {
	if sourceID <= 0 {
		return nil
	}
	if m, ok := data.(map[string]interface{}); ok {
		key := fmt.Sprintf("%d", sourceID)
		raw := m[key]
		if mm, ok := raw.(map[string]interface{}); ok {
			if g, ok := mm[granularity]; ok {
				return g
			}
			if g, ok := mm["day"]; ok {
				return g
			}
		}
		if raw != nil {
			return raw
		}
	}
	_ = buckets
	return nil
}

func filterProducts(items []map[string]interface{}, search string, merchant string) []map[string]interface{} {
	query := strings.TrimSpace(strings.ToLower(search))
	merchantNorm := strings.TrimSpace(strings.ToLower(merchant))
	out := make([]map[string]interface{}, 0, len(items))
	for _, item := range items {
		if item == nil {
			continue
		}
		if merchantNorm != "" {
			m := strings.ToLower(fmt.Sprintf("%v", item["merchant"]))
			if m != merchantNorm {
				continue
			}
		}
		if query == "" {
			out = append(out, item)
			continue
		}
		hay := strings.ToLower(fmt.Sprintf("%v %v %v", item["title"], item["product_id"], item["site_key"]))
		if strings.Contains(hay, query) {
			out = append(out, item)
		}
	}
	return out
}

func parseDays(params map[string]interface{}, def int) int {
	days := def
	if v, ok := params["days"]; ok {
		if i, ok := toInt(v); ok && i > 0 {
			days = i
		}
	}
	return days
}

func parseLLMFilters(params map[string]interface{}) (limit int, offset int, filters map[string]string) {
	limit = 200
	offset = 0
	filters = map[string]string{}
	if v, ok := params["limit"]; ok {
		if i, ok := toInt(v); ok && i > 0 {
			limit = i
		}
	}
	if v, ok := params["offset"]; ok {
		if i, ok := toInt(v); ok && i >= 0 {
			offset = i
		}
	}
	setFilterIfNotEmpty(filters, "provider", params["provider"])
	setFilterIfNotEmpty(filters, "model", params["model"])
	setFilterIfNotEmpty(filters, "call_type", params["call_type"])
	setFilterIfNotEmpty(filters, "status", params["status"])
	setFilterIfNotEmpty(filters, "session_id", params["session_id"])
	setFilterIfNotEmpty(filters, "experiment_id", params["experiment_id"])
	setFilterIfNotEmpty(filters, "variant_id", params["variant_id"])
	return
}

func setFilterIfNotEmpty(filters map[string]string, key string, v interface{}) {
	if v == nil {
		return
	}
	s := strings.TrimSpace(fmt.Sprintf("%v", v))
	if s != "" {
		filters[key] = s
	}
}

func toInt(v interface{}) (int, bool) {
	switch n := v.(type) {
	case int:
		return n, true
	case int64:
		return int(n), true
	case float64:
		return int(n), true
	case string:
		if i, err := strconv.Atoi(n); err == nil {
			return i, true
		}
	}
	return 0, false
}

func filterCategories(items []map[string]interface{}, search string) []map[string]interface{} {
	normalized := strings.TrimSpace(strings.ToLower(search))
	out := make([]map[string]interface{}, 0, len(items))
	for _, s := range items {
		if s == nil {
			continue
		}
		t, _ := s["type"].(string)
		if t != "list" {
			continue
		}
		if normalized == "" {
			out = append(out, s)
			continue
		}
		key := strings.ToLower(fmt.Sprintf("%v", s["site_key"]))
		urls := strings.ToLower(fmt.Sprintf("%v", s["url"]))
		name := ""
		if cfg, ok := s["config"].(map[string]interface{}); ok {
			name = strings.ToLower(fmt.Sprintf("%v", cfg["discovery_name"]))
		}
		if strings.Contains(key, normalized) || strings.Contains(urls, normalized) || strings.Contains(name, normalized) {
			out = append(out, s)
		}
	}
	return out
}

func buildLLMQuery(params map[string]interface{}) url.Values {
	q := url.Values{}
	if v, ok := params["days"]; ok {
		if i, ok := toInt(v); ok && i > 0 {
			q.Set("days", strconv.Itoa(i))
		}
	}
	if v, ok := params["limit"]; ok {
		if i, ok := toInt(v); ok && i > 0 {
			q.Set("limit", strconv.Itoa(i))
		}
	}
	if v, ok := params["offset"]; ok {
		if i, ok := toInt(v); ok && i >= 0 {
			q.Set("offset", strconv.Itoa(i))
		}
	}
	setStringIfNotEmpty(q, "provider", params["provider"])
	setStringIfNotEmpty(q, "model", params["model"])
	setStringIfNotEmpty(q, "call_type", params["call_type"])
	setStringIfNotEmpty(q, "status", params["status"])
	setStringIfNotEmpty(q, "session_id", params["session_id"])
	setStringIfNotEmpty(q, "experiment_id", params["experiment_id"])
	setStringIfNotEmpty(q, "variant_id", params["variant_id"])
	return q
}

func setStringIfNotEmpty(q url.Values, key string, v interface{}) {
	if v == nil {
		return
	}
	s := strings.TrimSpace(fmt.Sprintf("%v", v))
	if s != "" {
		q.Set(key, s)
	}
}

func slicePage(items []map[string]interface{}, offset int, limit int) []map[string]interface{} {
	if offset < 0 {
		offset = 0
	}
	if limit <= 0 {
		limit = 200
	}
	if offset >= len(items) {
		return []map[string]interface{}{}
	}
	end := offset + limit
	if end > len(items) {
		end = len(items)
	}
	return items[offset:end]
}

type httpStatusError struct {
	status int
	msg    string
}

func (e httpStatusError) Error() string {
	return e.msg
}

func (r *Resolver) getJSON(ctx context.Context, path string, out interface{}) error {
	base := strings.TrimRight(r.cfg.AdminAPIBase, "/")
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, base+path, nil)
	if err != nil {
		return err
	}
	if r.cfg.AdminToken != "" {
		req.Header.Set("x-internal-token", r.cfg.AdminToken)
	}
	resp, err := r.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return httpStatusError{status: resp.StatusCode, msg: fmt.Sprintf("%s -> %d", path, resp.StatusCode)}
	}
	return json.NewDecoder(resp.Body).Decode(out)
}
