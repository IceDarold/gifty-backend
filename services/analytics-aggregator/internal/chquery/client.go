package chquery

import (
	"context"
	"database/sql"
	"encoding/json"
	"net/url"
	"strings"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2"
)

type Client struct {
	conn clickhouse.Conn
}

func New(dsn string) (*Client, error) {
	conn, err := clickhouse.Open(&clickhouse.Options{
		Addr: []string{parseAddr(dsn)},
		Auth: parseAuth(dsn),
	})
	if err != nil {
		return nil, err
	}
	return &Client{conn: conn}, nil
}

func parseAddr(dsn string) string {
	cfg := parseDSN(dsn)
	return cfg.Addr
}

func parseAuth(dsn string) clickhouse.Auth {
	cfg := parseDSN(dsn)
	return clickhouse.Auth{Database: cfg.Database, Username: cfg.Username, Password: cfg.Password}
}

type dsnConfig struct {
	Addr     string
	Database string
	Username string
	Password string
}

func parseDSN(dsn string) dsnConfig {
	cfg := dsnConfig{
		Addr:     "clickhouse:9000",
		Database: "default",
		Username: "default",
		Password: "",
	}

	dsn = strings.TrimSpace(dsn)
	if dsn == "" {
		return cfg
	}
	if !strings.HasPrefix(dsn, "clickhouse://") {
		cfg.Addr = dsn
		return cfg
	}

	parsed, err := url.Parse(dsn)
	if err != nil {
		return cfg
	}
	if parsed.Host != "" {
		cfg.Addr = parsed.Host
	}
	if parsed.User != nil {
		if user := parsed.User.Username(); user != "" {
			cfg.Username = user
		}
		if pass, ok := parsed.User.Password(); ok {
			cfg.Password = pass
		}
	}
	if db := strings.Trim(parsed.Path, "/"); db != "" {
		cfg.Database = db
	}
	return cfg
}

type DashboardStats struct {
	QuizStarted24h   uint64  `json:"quiz_started_24h"`
	QuizCompleted24h uint64  `json:"quiz_completed_24h"`
	QuizRate         float64 `json:"quiz_completion_rate"`
}

type TrendPoint struct {
	Name      string `json:"name"`
	Dau       uint64 `json:"dau"`
	Completed uint64 `json:"completed"`
}

func (c *Client) DashboardStats(ctx context.Context) (DashboardStats, error) {
	q := `
		SELECT
			sumIf(cnt, metric='kpi.quiz_started') AS started,
			sumIf(cnt, metric='kpi.quiz_completed') AS completed
		FROM analytics_agg_1m
		WHERE bucket_minute >= now() - INTERVAL 24 HOUR
	`
	var started, completed uint64
	if err := c.conn.QueryRow(ctx, q).Scan(&started, &completed); err != nil {
		return DashboardStats{}, err
	}
	rate := 0.0
	if started > 0 {
		rate = float64(completed) / float64(started) * 100.0
	}
	return DashboardStats{
		QuizStarted24h:   started,
		QuizCompleted24h: completed,
		QuizRate:         rate,
	}, nil
}

func (c *Client) DashboardTrends(ctx context.Context, days int) ([]TrendPoint, error) {
	if days <= 0 {
		days = 7
	}
	q := `
		SELECT
			toDate(bucket_minute) AS d,
			sumIf(cnt, metric='kpi.quiz_started') AS started,
			sumIf(cnt, metric='kpi.quiz_completed') AS completed
		FROM analytics_agg_1m
		WHERE bucket_minute >= now() - INTERVAL ? DAY
		GROUP BY d
		ORDER BY d
	`
	rows, err := c.conn.Query(ctx, q, days)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]TrendPoint, 0)
	for rows.Next() {
		var day time.Time
		var started, completed uint64
		if err := rows.Scan(&day, &started, &completed); err != nil {
			return nil, err
		}
		out = append(out, TrendPoint{
			Name:      day.Format("2006-01-02"),
			Dau:       started,
			Completed: completed,
		})
	}
	return out, nil
}

type LLMStats struct {
	Total                         uint64  `json:"total"`
	Errors                        uint64  `json:"errors"`
	ErrorRate                     float64 `json:"error_rate"`
	TotalCostUSD                  float64 `json:"total_cost_usd"`
	AvgCostUSD                    float64 `json:"avg_cost_usd"`
	P50LatencyMS                  float64 `json:"p50_latency_ms"`
	P95LatencyMS                  float64 `json:"p95_latency_ms"`
	AvgLatencyMS                  float64 `json:"avg_latency_ms"`
	P50TotalTokens                float64 `json:"p50_total_tokens"`
	P95TotalTokens                float64 `json:"p95_total_tokens"`
	AvgTotalTokens                float64 `json:"avg_total_tokens"`
	MissingUsageCount             uint64  `json:"missing_usage_count"`
	MissingProviderRequestIDCount uint64  `json:"missing_provider_request_id_count"`
}

func (c *Client) LLMStats(ctx context.Context, days int) (LLMStats, error) {
	if days <= 0 {
		days = 7
	}
	q := `
		SELECT
			sumIf(cnt, metric='llm.call_completed') AS total,
			sumIf(cnt, metric='llm.call_completed' AND JSONExtractString(dims_json, 'status') NOT IN ('ok','success','completed','')) AS errors,
			sumIf(sum_value, metric='llm.call_completed.cost_usd') AS total_cost,
			sumIf(sum_value, metric='llm.call_completed.latency_ms') AS total_latency,
			sumIf(cnt, metric='llm.call_completed.latency_ms') AS latency_count,
			maxIf(p50_value, metric='llm.call_completed.latency_ms') AS p50_latency,
			maxIf(p95_value, metric='llm.call_completed.latency_ms') AS p95_latency,
			sumIf(sum_value, metric='llm.call_completed.total_tokens') AS total_tokens,
			sumIf(cnt, metric='llm.call_completed.total_tokens') AS token_count,
			maxIf(p50_value, metric='llm.call_completed.total_tokens') AS p50_tokens,
			maxIf(p95_value, metric='llm.call_completed.total_tokens') AS p95_tokens
		FROM analytics_agg_1m
		WHERE bucket_minute >= now() - INTERVAL ? DAY
	`
	var (
		total, errors, latencyCount, tokenCount uint64
		totalCost, totalLatency, totalTokens    float64
		p50Latency, p95Latency                  float64
		p50Tokens, p95Tokens                    float64
	)
	if err := c.conn.QueryRow(ctx, q, days).Scan(
		&total,
		&errors,
		&totalCost,
		&totalLatency,
		&latencyCount,
		&p50Latency,
		&p95Latency,
		&totalTokens,
		&tokenCount,
		&p50Tokens,
		&p95Tokens,
	); err != nil {
		return LLMStats{}, err
	}
	errorRate := 0.0
	if total > 0 {
		errorRate = float64(errors) / float64(total)
	}
	avgCost := 0.0
	if total > 0 {
		avgCost = totalCost / float64(total)
	}
	avgLatency := 0.0
	if latencyCount > 0 {
		avgLatency = totalLatency / float64(latencyCount)
	}
	avgTokens := 0.0
	if tokenCount > 0 {
		avgTokens = totalTokens / float64(tokenCount)
	}
	return LLMStats{
		Total:                         total,
		Errors:                        errors,
		ErrorRate:                     errorRate,
		TotalCostUSD:                  totalCost,
		AvgCostUSD:                    avgCost,
		P50LatencyMS:                  p50Latency,
		P95LatencyMS:                  p95Latency,
		AvgLatencyMS:                  avgLatency,
		P50TotalTokens:                p50Tokens,
		P95TotalTokens:                p95Tokens,
		AvgTotalTokens:                avgTokens,
		MissingUsageCount:             0,
		MissingProviderRequestIDCount: 0,
	}, nil
}

type IntelligenceSummary struct {
	Metrics        map[string]float64       `json:"metrics"`
	Providers      []map[string]interface{} `json:"providers"`
	LatencyHeatmap []map[string]interface{} `json:"latency_heatmap"`
}

func (c *Client) IntelligenceSummary(ctx context.Context, days int) (map[string]interface{}, error) {
	if days <= 0 {
		days = 7
	}
	stats, err := c.LLMStats(ctx, days)
	if err != nil {
		return nil, err
	}
	out := map[string]interface{}{
		"metrics": map[string]interface{}{
			"total_cost":     stats.TotalCostUSD,
			"total_tokens":   stats.AvgTotalTokens * float64(stats.Total),
			"total_requests": stats.Total,
		},
		"providers":       []map[string]interface{}{},
		"latency_heatmap": []map[string]interface{}{},
	}
	return out, nil
}

type ThroughputPoint struct {
	Bucket string `json:"bucket"`
	Count  uint64 `json:"count"`
}

func (c *Client) LLMThroughput(ctx context.Context, days int, bucket string) ([]ThroughputPoint, error) {
	if days <= 0 {
		days = 7
	}
	interval := "toStartOfMinute"
	switch bucket {
	case "hour":
		interval = "toStartOfHour"
	case "day":
		interval = "toDate"
	case "minute":
		interval = "toStartOfMinute"
	}
	q := `
		SELECT
			` + interval + `(bucket_minute) AS ts,
			sumIf(cnt, metric='llm.call_completed') AS total
		FROM analytics_agg_1m
		WHERE bucket_minute >= now() - INTERVAL ? DAY
		GROUP BY ts
		ORDER BY ts
	`
	rows, err := c.conn.Query(ctx, q, days)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []ThroughputPoint{}
	for rows.Next() {
		var ts time.Time
		var total uint64
		if err := rows.Scan(&ts, &total); err != nil {
			return nil, err
		}
		out = append(out, ThroughputPoint{Bucket: ts.Format(time.RFC3339), Count: total})
	}
	return out, nil
}

func (c *Client) LLMLogs(ctx context.Context, days, limit, offset int, filters map[string]string) ([]map[string]interface{}, int, error) {
	if days <= 0 {
		days = 7
	}
	if limit <= 0 {
		limit = 50
	}
	where := "metric LIKE 'llm.call_completed%' AND occurred_at >= now() - INTERVAL ? DAY"
	args := []interface{}{days}
	if v := filters["provider"]; v != "" {
		where += " AND JSONExtractString(dims_json,'provider') = ?"
		args = append(args, v)
	}
	if v := filters["model"]; v != "" {
		where += " AND JSONExtractString(dims_json,'model') = ?"
		args = append(args, v)
	}
	if v := filters["status"]; v != "" {
		where += " AND JSONExtractString(dims_json,'status') = ?"
		args = append(args, v)
	}
	q := `
		SELECT
			event_id,
			max(occurred_at) AS created_at,
			any(JSONExtractString(dims_json,'provider')) AS provider,
			any(JSONExtractString(dims_json,'model')) AS model,
			any(JSONExtractString(dims_json,'call_type')) AS call_type,
			any(JSONExtractString(dims_json,'status')) AS status,
			maxIf(value, metric='llm.call_completed.latency_ms') AS latency_ms,
			maxIf(value, metric='llm.call_completed.total_tokens') AS total_tokens,
			maxIf(value, metric='llm.call_completed.cost_usd') AS cost_usd
		FROM analytics_events
		WHERE ` + where + `
		GROUP BY event_id
		ORDER BY created_at DESC
		LIMIT ? OFFSET ?
	`
	args = append(args, limit, offset)
	rows, err := c.conn.Query(ctx, q, args...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()
	out := []map[string]interface{}{}
	for rows.Next() {
		var (
			id                                string
			created                           time.Time
			provider, model, callType, status string
			latency, tokens, cost             float64
		)
		if err := rows.Scan(&id, &created, &provider, &model, &callType, &status, &latency, &tokens, &cost); err != nil {
			return nil, 0, err
		}
		out = append(out, map[string]interface{}{
			"id":           id,
			"created_at":   created.Format(time.RFC3339),
			"provider":     provider,
			"model":        model,
			"call_type":    callType,
			"status":       status,
			"latency_ms":   latency,
			"total_tokens": tokens,
			"cost_usd":     cost,
		})
	}
	countQuery := `
		SELECT countDistinct(event_id)
		FROM analytics_events
		WHERE ` + where + `
	`
	var total int
	if err := c.conn.QueryRow(ctx, countQuery, args[:len(args)-2]...).Scan(&total); err != nil {
		total = len(out)
	}
	return out, total, nil
}

func (c *Client) LLMOutliers(ctx context.Context, days, limit int, filters map[string]string) ([]map[string]interface{}, error) {
	items, _, err := c.LLMLogs(ctx, days, limit, 0, filters)
	if err != nil {
		return nil, err
	}
	return items, nil
}

func (c *Client) LLMBreakdown(ctx context.Context, days int, group string) ([]map[string]interface{}, error) {
	if days <= 0 {
		days = 7
	}
	field := "provider"
	switch group {
	case "model":
		field = "model"
	case "status":
		field = "status"
	case "call_type":
		field = "call_type"
	}
	q := `
		SELECT
			JSONExtractString(dims_json, ?) AS key,
			count() AS requests,
			sumIf(value, metric='llm.call_completed.cost_usd') AS total_cost_usd,
			sumIf(value, metric='llm.call_completed.total_tokens') AS total_tokens,
			maxIf(value, metric='llm.call_completed.latency_ms') AS avg_latency_ms
		FROM analytics_events
		WHERE metric LIKE 'llm.call_completed%' AND occurred_at >= now() - INTERVAL ? DAY
		GROUP BY key
		ORDER BY requests DESC
	`
	rows, err := c.conn.Query(ctx, q, field, days)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []map[string]interface{}{}
	for rows.Next() {
		var key string
		var requests uint64
		var totalCost, totalTokens, avgLatency float64
		if err := rows.Scan(&key, &requests, &totalCost, &totalTokens, &avgLatency); err != nil {
			return nil, err
		}
		out = append(out, map[string]interface{}{
			"key":            key,
			"requests":       requests,
			"total_cost_usd": totalCost,
			"total_tokens":   totalTokens,
			"avg_latency_ms": avgLatency,
		})
	}
	return out, nil
}

func (c *Client) OpsOverview(ctx context.Context) (map[string]interface{}, error) {
	// Placeholder aggregate from analytics_agg_1m. Metrics must be produced upstream.
	q := `
		SELECT
			sumIf(cnt, metric='ops.queue.messages_total') AS messages_total,
			sumIf(cnt, metric='ops.queue.messages_ready') AS messages_ready,
			sumIf(cnt, metric='ops.queue.messages_unack') AS messages_unack,
			sumIf(cnt, metric='ops.runs.running') AS runs_running,
			sumIf(cnt, metric='ops.runs.completed') AS runs_completed,
			sumIf(cnt, metric='ops.runs.error') AS runs_error
		FROM analytics_agg_1m
		WHERE bucket_minute >= now() - INTERVAL 24 HOUR
	`
	var total, ready, unack, running, completed, errored uint64
	if err := c.conn.QueryRow(ctx, q).Scan(&total, &ready, &unack, &running, &completed, &errored); err != nil {
		return nil, err
	}
	return map[string]interface{}{
		"queue": map[string]interface{}{
			"messages_total":          total,
			"messages_ready":          ready,
			"messages_unacknowledged": unack,
		},
		"runs": map[string]interface{}{
			"running":   running,
			"completed": completed,
			"error":     errored,
		},
	}, nil
}

func (c *Client) OpsTrend(ctx context.Context, metric string, days int) ([]map[string]interface{}, error) {
	if days <= 0 {
		days = 7
	}
	q := `
		SELECT
			toDate(bucket_minute) AS d,
			sumIf(sum_value, metric=?) AS value
		FROM analytics_agg_1m
		WHERE bucket_minute >= now() - INTERVAL ? DAY
		GROUP BY d
		ORDER BY d
	`
	rows, err := c.conn.Query(ctx, q, metric, days)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []map[string]interface{}{}
	for rows.Next() {
		var d time.Time
		var v float64
		if err := rows.Scan(&d, &v); err != nil {
			return nil, err
		}
		out = append(out, map[string]interface{}{
			"date":  d.Format("2006-01-02"),
			"value": v,
		})
	}
	return out, nil
}

func (c *Client) LatestSnapshot(ctx context.Context, eventType string) (map[string]interface{}, error) {
	q := `
		SELECT payload_json
		FROM analytics_events
		WHERE event_type = ?
		ORDER BY occurred_at DESC, version DESC
		LIMIT 1
	`
	var payload string
	if err := c.conn.QueryRow(ctx, q, eventType).Scan(&payload); err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, err
	}
	if strings.TrimSpace(payload) == "" {
		return nil, nil
	}
	var out map[string]interface{}
	if err := json.Unmarshal([]byte(payload), &out); err != nil {
		return nil, err
	}
	return out, nil
}

func (c *Client) SnapshotData(ctx context.Context, channel string) (interface{}, error) {
	eventType := "admin.snapshot." + channel
	payload, err := c.LatestSnapshot(ctx, eventType)
	if err != nil {
		return nil, err
	}
	if payload == nil {
		return nil, nil
	}
	if v, ok := payload["data"]; ok {
		return v, nil
	}
	return payload, nil
}

// removed duplicate breakdown/throughput helpers

type latestRow struct {
	payload string
}

func (c *Client) latestStateList(ctx context.Context, table string) ([]map[string]interface{}, error) {
	q := "SELECT payload_json FROM " + table + " FINAL WHERE deleted = 0 ORDER BY version DESC"
	rows, err := c.conn.Query(ctx, q)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]map[string]interface{}, 0)
	for rows.Next() {
		var payload string
		if err := rows.Scan(&payload); err != nil {
			return nil, err
		}
		var item map[string]interface{}
		if err := json.Unmarshal([]byte(payload), &item); err != nil {
			return nil, err
		}
		out = append(out, item)
	}
	return out, nil
}

func (c *Client) latestStateOne(ctx context.Context, table string, where string, arg interface{}) (map[string]interface{}, error) {
	q := "SELECT payload_json FROM " + table + " FINAL WHERE deleted = 0 AND " + where + " ORDER BY version DESC LIMIT 1"
	var payload string
	if err := c.conn.QueryRow(ctx, q, arg).Scan(&payload); err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, err
	}
	var item map[string]interface{}
	if err := json.Unmarshal([]byte(payload), &item); err != nil {
		return nil, err
	}
	return item, nil
}

func (c *Client) SourcesLatest(ctx context.Context) ([]map[string]interface{}, error) {
	return c.latestStateList(ctx, "sources_latest")
}

func (c *Client) SourceLatest(ctx context.Context, id int) (map[string]interface{}, error) {
	return c.latestStateOne(ctx, "sources_latest", "source_id = ?", id)
}

func (c *Client) SubscribersLatest(ctx context.Context) ([]map[string]interface{}, error) {
	return c.latestStateList(ctx, "subscribers_latest")
}

func (c *Client) SubscriberLatest(ctx context.Context, id int) (map[string]interface{}, error) {
	return c.latestStateOne(ctx, "subscribers_latest", "subscriber_id = ?", id)
}

func (c *Client) SettingsRuntimeLatest(ctx context.Context) ([]map[string]interface{}, error) {
	return c.latestStateList(ctx, "settings_runtime_latest")
}

func (c *Client) FrontendAppsLatest(ctx context.Context) ([]map[string]interface{}, error) {
	return c.latestStateList(ctx, "frontend_apps_latest")
}

func (c *Client) FrontendReleasesLatest(ctx context.Context) ([]map[string]interface{}, error) {
	return c.latestStateList(ctx, "frontend_releases_latest")
}

func (c *Client) FrontendProfilesLatest(ctx context.Context) ([]map[string]interface{}, error) {
	return c.latestStateList(ctx, "frontend_profiles_latest")
}

func (c *Client) FrontendRulesLatest(ctx context.Context) ([]map[string]interface{}, error) {
	return c.latestStateList(ctx, "frontend_rules_latest")
}

func (c *Client) FrontendAllowedHostsLatest(ctx context.Context) ([]map[string]interface{}, error) {
	return c.latestStateList(ctx, "frontend_allowed_hosts_latest")
}

func (c *Client) SettingsRuntimeEntryLatest(ctx context.Context, key string) (map[string]interface{}, error) {
	return c.latestStateOne(ctx, "settings_runtime_latest", "setting_key = ?", key)
}

func (c *Client) FrontendAuditLogLatest(ctx context.Context) ([]map[string]interface{}, error) {
	return c.latestStateList(ctx, "frontend_audit_log_latest")
}

func (c *Client) OpsSitesLatest(ctx context.Context) ([]map[string]interface{}, error) {
	return c.latestStateList(ctx, "sources_latest")
}

func (c *Client) OpsDiscoveryLatest(ctx context.Context) ([]map[string]interface{}, error) {
	return c.latestStateList(ctx, "ops_discovery_latest")
}

func (c *Client) OpsRunsLatest(ctx context.Context) ([]map[string]interface{}, error) {
	return c.latestStateList(ctx, "ops_runs_latest")
}

func (c *Client) OpsDiscoveryCountsBySite(ctx context.Context) (map[string]map[string]uint64, error) {
	q := `
		SELECT
			site_key,
			JSONExtractString(payload_json, 'state') AS state,
			count() AS cnt
		FROM ops_discovery_latest FINAL
		WHERE deleted = 0
		GROUP BY site_key, state
	`
	rows, err := c.conn.Query(ctx, q)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := map[string]map[string]uint64{}
	for rows.Next() {
		var siteKey, state string
		var cnt uint64
		if err := rows.Scan(&siteKey, &state, &cnt); err != nil {
			return nil, err
		}
		if siteKey == "" {
			continue
		}
		if _, ok := out[siteKey]; !ok {
			out[siteKey] = map[string]uint64{}
		}
		out[siteKey][state] = cnt
	}
	return out, nil
}

func (c *Client) ProductsCountBySite(ctx context.Context) (map[string]uint64, error) {
	q := `
		SELECT
			site_key,
			anyLast(cnt) AS cnt
		FROM products_count_by_site
		GROUP BY site_key
	`
	rows, err := c.conn.Query(ctx, q)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := map[string]uint64{}
	for rows.Next() {
		var siteKey string
		var cnt uint64
		if err := rows.Scan(&siteKey, &cnt); err != nil {
			return nil, err
		}
		if siteKey == "" {
			continue
		}
		out[siteKey] = cnt
	}
	return out, nil
}

func (c *Client) ProductsTotalAll(ctx context.Context) (uint64, error) {
	q := `
		SELECT
			sum(cnt) AS total
		FROM products_count_by_site
	`
	var total uint64
	if err := c.conn.QueryRow(ctx, q).Scan(&total); err != nil {
		return 0, err
	}
	return total, nil
}

func (c *Client) OpsRunCountsBySource(ctx context.Context) (map[int]map[string]uint64, error) {
	q := `
		SELECT
			source_id,
			JSONExtractString(payload_json, 'status') AS status,
			count() AS cnt
		FROM ops_runs_latest FINAL
		WHERE deleted = 0
		GROUP BY source_id, status
	`
	rows, err := c.conn.Query(ctx, q)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := map[int]map[string]uint64{}
	for rows.Next() {
		var sourceID int
		var status string
		var cnt uint64
		if err := rows.Scan(&sourceID, &status, &cnt); err != nil {
			return nil, err
		}
		if sourceID == 0 {
			continue
		}
		if _, ok := out[sourceID]; !ok {
			out[sourceID] = map[string]uint64{}
		}
		out[sourceID][status] = cnt
	}
	return out, nil
}

func (c *Client) ProductsLatest(ctx context.Context, limit, offset int, search, merchant string) (items []map[string]interface{}, total int, err error) {
	q := "SELECT payload_json FROM products_latest FINAL WHERE deleted = 0"
	args := []interface{}{}
	if search != "" {
		q += " AND positionCaseInsensitiveUTF8(title, ?) > 0"
		args = append(args, search)
	}
	if merchant != "" {
		q += " AND merchant = ?"
		args = append(args, merchant)
	}
	countQ := "SELECT count() FROM products_latest FINAL WHERE deleted = 0"
	countArgs := []interface{}{}
	if search != "" {
		countQ += " AND positionCaseInsensitiveUTF8(title, ?) > 0"
		countArgs = append(countArgs, search)
	}
	if merchant != "" {
		countQ += " AND merchant = ?"
		countArgs = append(countArgs, merchant)
	}
	var totalUint uint64
	if err = c.conn.QueryRow(ctx, countQ, countArgs...).Scan(&totalUint); err != nil {
		return nil, 0, err
	}
	total = int(totalUint)
	q += " ORDER BY merchant, category, product_id LIMIT ? OFFSET ?"
	args = append(args, limit, offset)
	rows, err := c.conn.Query(ctx, q, args...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()
	for rows.Next() {
		var payload string
		if err := rows.Scan(&payload); err != nil {
			return nil, 0, err
		}
		var item map[string]interface{}
		if err := json.Unmarshal([]byte(payload), &item); err != nil {
			return nil, 0, err
		}
		items = append(items, item)
	}
	return items, total, nil
}

func (c *Client) CategoriesLatest(ctx context.Context, limit, offset int, search string) (items []map[string]interface{}, total int, err error) {
	q := "SELECT payload_json FROM categories_latest FINAL WHERE deleted = 0"
	args := []interface{}{}
	if search != "" {
		q += " AND positionCaseInsensitiveUTF8(name, ?) > 0"
		args = append(args, search)
	}
	countQ := "SELECT count() FROM categories_latest FINAL WHERE deleted = 0"
	countArgs := []interface{}{}
	if search != "" {
		countQ += " AND positionCaseInsensitiveUTF8(name, ?) > 0"
		countArgs = append(countArgs, search)
	}
	var totalUint uint64
	if err = c.conn.QueryRow(ctx, countQ, countArgs...).Scan(&totalUint); err != nil {
		return nil, 0, err
	}
	total = int(totalUint)
	q += " ORDER BY site_key, category_id LIMIT ? OFFSET ?"
	args = append(args, limit, offset)
	rows, err := c.conn.Query(ctx, q, args...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()
	for rows.Next() {
		var payload string
		if err := rows.Scan(&payload); err != nil {
			return nil, 0, err
		}
		var item map[string]interface{}
		if err := json.Unmarshal([]byte(payload), &item); err != nil {
			return nil, 0, err
		}
		items = append(items, item)
	}
	return items, total, nil
}
