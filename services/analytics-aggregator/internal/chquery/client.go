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
			sum(total) AS total,
			sum(errors) AS errors,
			sum(total_cost) AS total_cost,
			sum(total_latency) AS total_latency,
			sum(latency_count) AS latency_count,
			quantileTimingMerge(0.5)(p50_latency_state) AS p50_latency,
			quantileTimingMerge(0.95)(p95_latency_state) AS p95_latency,
			sum(total_tokens) AS total_tokens,
			sum(token_count) AS token_count,
			quantileTimingMerge(0.5)(p50_tokens_state) AS p50_tokens,
			quantileTimingMerge(0.95)(p95_tokens_state) AS p95_tokens
		FROM llm_calls_agg_1m
		WHERE bucket_minute >= now() - INTERVAL ? DAY
	`
	var (
		total, errors, latencyCount, tokenCount uint64
		totalCost, totalLatency, totalTokens    float64
		p50Latency32, p95Latency32              float32
		p50Tokens32, p95Tokens32                float32
	)
	if err := c.conn.QueryRow(ctx, q, days).Scan(
		&total,
		&errors,
		&totalCost,
		&totalLatency,
		&latencyCount,
		&p50Latency32,
		&p95Latency32,
		&totalTokens,
		&tokenCount,
		&p50Tokens32,
		&p95Tokens32,
	); err != nil {
		return LLMStats{}, err
	}
	p50Latency := float64(p50Latency32)
	p95Latency := float64(p95Latency32)
	p50Tokens := float64(p50Tokens32)
	p95Tokens := float64(p95Tokens32)
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
			sum(total) AS total
		FROM llm_calls_agg_1m
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
	where := "created_at >= now() - INTERVAL ? DAY"
	args := []interface{}{days}
	if v := filters["provider"]; v != "" {
		where += " AND provider = ?"
		args = append(args, v)
	}
	if v := filters["model"]; v != "" {
		where += " AND model = ?"
		args = append(args, v)
	}
	if v := filters["status"]; v != "" {
		where += " AND status = ?"
		args = append(args, v)
	}
	if v := filters["call_type"]; v != "" {
		where += " AND call_type = ?"
		args = append(args, v)
	}
	if v := filters["session_id"]; v != "" {
		where += " AND session_id = ?"
		args = append(args, v)
	}
	if v := filters["experiment_id"]; v != "" {
		where += " AND JSONExtractString(payload_json,'experiment_id') = ?"
		args = append(args, v)
	}
	if v := filters["variant_id"]; v != "" {
		where += " AND JSONExtractString(payload_json,'variant_id') = ?"
		args = append(args, v)
	}
	q := `
		SELECT
			payload_json,
			created_at
		FROM llm_calls_search
		WHERE deleted = 0 AND ` + where + `
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
		var payload string
		var created time.Time
		if err := rows.Scan(&payload, &created); err != nil {
			return nil, 0, err
		}
		var item map[string]interface{}
		if err := json.Unmarshal([]byte(payload), &item); err != nil {
			return nil, 0, err
		}
		if _, ok := item["created_at"]; !ok {
			item["created_at"] = created.Format(time.RFC3339)
		}
		out = append(out, item)
	}
	countQuery := `
		SELECT count()
		FROM llm_calls_search
		WHERE deleted = 0 AND ` + where + `
	`
	var total uint64
	if err := c.conn.QueryRow(ctx, countQuery, args[:len(args)-2]...).Scan(&total); err != nil {
		return out, len(out), nil
	}
	return out, int(total), nil
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
			` + field + ` AS key,
			sum(total) AS requests,
			sum(total_cost) AS total_cost_usd,
			sum(total_tokens) AS total_tokens,
			if(sum(latency_count)=0, 0, sum(total_latency)/sum(latency_count)) AS avg_latency_ms
		FROM llm_calls_agg_1m
		WHERE bucket_minute >= now() - INTERVAL ? DAY
		GROUP BY key
		ORDER BY requests DESC
	`
	rows, err := c.conn.Query(ctx, q, days)
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
			maxIf(max_value, metric='ops.queue_updated.messages_total') AS messages_total,
			maxIf(max_value, metric='ops.queue_updated.messages_ready') AS messages_ready,
			maxIf(max_value, metric='ops.queue_updated.messages_unack') AS messages_unack,
			maxIf(max_value, metric='ops.runs.running') AS runs_running,
			maxIf(max_value, metric='ops.runs.completed') AS runs_completed,
			maxIf(max_value, metric='ops.runs.error') AS runs_error
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

func (c *Client) OpsItemsTrend(ctx context.Context, days int, bucket string) (map[string]interface{}, error) {
	if days <= 0 {
		days = 7
	}
	bucketExpr := "toDate(occurred_at)"
	switch bucket {
	case "minute":
		bucketExpr = "toStartOfMinute(occurred_at)"
	case "hour":
		bucketExpr = "toStartOfHour(occurred_at)"
	case "week":
		bucketExpr = "toStartOfWeek(occurred_at)"
	case "day":
		bucketExpr = "toDate(occurred_at)"
	}
	q := `
		SELECT
			` + bucketExpr + ` AS b,
			sum(JSONExtractInt(payload_json, 'items_new')) AS items_new,
			sum(JSONExtractInt(payload_json, 'categories_new')) AS categories_new
		FROM state_events_raw
		WHERE event_type IN ('ops.run.updated', 'ops.run.created')
		  AND occurred_at >= now() - INTERVAL ? DAY
		GROUP BY b
		ORDER BY b
	`
	rows, err := c.conn.Query(ctx, q, days)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	items := []map[string]interface{}{}
	var totalItems, totalCategories float64
	for rows.Next() {
		var b time.Time
		var itemsNew, categoriesNew float64
		if err := rows.Scan(&b, &itemsNew, &categoriesNew); err != nil {
			return nil, err
		}
		totalItems += itemsNew
		totalCategories += categoriesNew
		items = append(items, map[string]interface{}{
			"date":           b.Format(time.RFC3339),
			"items_new":      itemsNew,
			"categories_new": categoriesNew,
		})
	}
	return map[string]interface{}{
		"items": items,
		"totals": map[string]interface{}{
			"items_new":      totalItems,
			"categories_new": totalCategories,
		},
	}, nil
}

func (c *Client) OpsTasksTrend(ctx context.Context, days int, bucket string) (map[string]interface{}, error) {
	if days <= 0 {
		days = 7
	}
	bucketExpr := "toDate(occurred_at)"
	switch bucket {
	case "minute":
		bucketExpr = "toStartOfMinute(occurred_at)"
	case "hour":
		bucketExpr = "toStartOfHour(occurred_at)"
	case "week":
		bucketExpr = "toStartOfWeek(occurred_at)"
	case "day":
		bucketExpr = "toDate(occurred_at)"
	}
	q := `
		SELECT
			` + bucketExpr + ` AS b,
			sumIf(1, status IN ('queued', 'pending')) AS queued,
			sumIf(1, status IN ('processing', 'running')) AS running,
			sumIf(1, status = 'completed') AS success,
			sumIf(1, status = 'error') AS error
		FROM (
			SELECT
				occurred_at,
				JSONExtractString(payload_json, 'status') AS status
			FROM state_events_raw
			WHERE event_type IN ('ops.run.updated', 'ops.run.created')
			  AND occurred_at >= now() - INTERVAL ? DAY
		)
		GROUP BY b
		ORDER BY b
	`
	rows, err := c.conn.Query(ctx, q, days)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	items := []map[string]interface{}{}
	var totalSuccess, totalError float64
	var maxQueue, maxRunning float64
	for rows.Next() {
		var b time.Time
		var queued, running, success, errCount float64
		if err := rows.Scan(&b, &queued, &running, &success, &errCount); err != nil {
			return nil, err
		}
		if queued > maxQueue {
			maxQueue = queued
		}
		if running > maxRunning {
			maxRunning = running
		}
		totalSuccess += success
		totalError += errCount
		items = append(items, map[string]interface{}{
			"date":    b.Format(time.RFC3339),
			"queue":   queued,
			"running": running,
			"success": success,
			"error":   errCount,
		})
	}
	return map[string]interface{}{
		"items": items,
		"totals": map[string]interface{}{
			"queue_max":   maxQueue,
			"running_max": maxRunning,
			"success":     totalSuccess,
			"error":       totalError,
		},
	}, nil
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

func (c *Client) SourcesLatestByType(ctx context.Context, sourceType string) ([]map[string]interface{}, error) {
	q := "SELECT payload_json FROM sources_latest FINAL WHERE deleted = 0 AND JSONExtractString(payload_json,'type') = ? ORDER BY version DESC"
	rows, err := c.conn.Query(ctx, q, sourceType)
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

func (c *Client) SourcesLatestBySiteAndType(ctx context.Context, siteKey string, sourceType string) ([]map[string]interface{}, error) {
	q := "SELECT payload_json FROM sources_latest FINAL WHERE deleted = 0 AND JSONExtractString(payload_json,'site_key') = ? AND JSONExtractString(payload_json,'type') = ? ORDER BY version DESC"
	rows, err := c.conn.Query(ctx, q, siteKey, sourceType)
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

func (c *Client) SourceLatest(ctx context.Context, id int) (map[string]interface{}, error) {
	return c.latestStateOne(ctx, "sources_latest", "source_id = ?", id)
}

func (c *Client) SubscribersLatest(ctx context.Context) ([]map[string]interface{}, error) {
	return c.latestStateList(ctx, "subscribers_latest")
}

func (c *Client) SubscriberLatest(ctx context.Context, id int) (map[string]interface{}, error) {
	return c.latestStateOne(ctx, "subscribers_latest", "subscriber_id = ?", id)
}

func (c *Client) SubscriberLatestByChatID(ctx context.Context, chatID int) (map[string]interface{}, error) {
	return c.latestStateOne(ctx, "subscribers_latest", "chat_id = ?", chatID)
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

func (c *Client) OpsDiscoveryBacklog(ctx context.Context, limit int) ([]map[string]interface{}, error) {
	if limit <= 0 {
		limit = 200
	}
	q := `
		SELECT payload_json
		FROM ops_discovery_latest FINAL
		WHERE deleted = 0
		  AND JSONExtractString(payload_json, 'state') = 'new'
		ORDER BY version DESC
		LIMIT ?
	`
	rows, err := c.conn.Query(ctx, q, limit)
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

func (c *Client) CategoriesLatest(ctx context.Context, limit, offset int, search string, siteKey string) (items []map[string]interface{}, total int, err error) {
	q := "SELECT payload_json FROM categories_latest FINAL WHERE deleted = 0"
	args := []interface{}{}
	if siteKey != "" {
		q += " AND site_key = ?"
		args = append(args, siteKey)
	}
	if search != "" {
		q += " AND positionCaseInsensitiveUTF8(name, ?) > 0"
		args = append(args, search)
	}
	countQ := "SELECT count() FROM categories_latest FINAL WHERE deleted = 0"
	countArgs := []interface{}{}
	if siteKey != "" {
		countQ += " AND site_key = ?"
		countArgs = append(countArgs, siteKey)
	}
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
