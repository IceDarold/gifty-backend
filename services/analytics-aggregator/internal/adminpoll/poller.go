package adminpoll

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"

	"analytics-aggregator/internal/chquery"
	"analytics-aggregator/internal/config"
	"analytics-aggregator/internal/state"
	"analytics-aggregator/internal/ws"
)

type Poller struct {
	cfg    config.Config
	store  *state.Store
	hub    *ws.Hub
	client *http.Client
	ch     *chquery.Client

	lastLogTS int64
}

func New(cfg config.Config, store *state.Store, hub *ws.Hub) *Poller {
	chClient, _ := chquery.New(cfg.ClickHouseDSN)
	return &Poller{
		cfg:   cfg,
		store: store,
		hub:   hub,
		client: &http.Client{
			Timeout: 10 * time.Second,
		},
		ch: chClient,
	}
}

func (p *Poller) Run(ctx context.Context) {
	p.startTicker(ctx, p.cfg.PollDashboard, p.pollDashboard)
	p.startTicker(ctx, p.cfg.PollOps, p.pollOps)
	p.startTicker(ctx, p.cfg.PollCatalog, p.pollCatalog)
	p.startTicker(ctx, p.cfg.PollSettings, p.pollSettings)
	p.startTicker(ctx, p.cfg.PollLogs, p.pollLogs)
}

func (p *Poller) startTicker(ctx context.Context, interval time.Duration, fn func(context.Context)) {
	if interval <= 0 {
		return
	}
	go func() {
		ticker := time.NewTicker(interval)
		defer ticker.Stop()
		fn(ctx)
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				fn(ctx)
			}
		}
	}()
}

func (p *Poller) publish(channel string, data interface{}) {
	if data == nil {
		return
	}
	snap := p.store.SetChannel(channel, data)
	p.hub.Publish([]state.ChannelSnapshot{snap})
}

func (p *Poller) getJSON(ctx context.Context, path string, out interface{}) error {
	base := strings.TrimRight(p.cfg.AdminAPIBase, "/")
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, base+path, nil)
	if err != nil {
		return err
	}
	if p.cfg.AdminToken != "" {
		req.Header.Set("x-internal-token", p.cfg.AdminToken)
	}
	resp, err := p.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("%s -> %d", path, resp.StatusCode)
	}
	return json.NewDecoder(resp.Body).Decode(out)
}

func (p *Poller) pollDashboard(ctx context.Context) {
	if p.ch != nil {
		if chStats, err := p.ch.DashboardStats(ctx); err == nil {
			p.publish("dashboard.stats", map[string]interface{}{
				"quiz_completion_rate": chStats.QuizRate,
				"quiz_started_24h":     chStats.QuizStarted24h,
				"quiz_completed_24h":   chStats.QuizCompleted24h,
			})
		}
		if sources, err := p.ch.SourcesLatest(ctx); err == nil {
			p.publish("dashboard.sources", sources)
		}
		if backlog, err := p.ch.OpsDiscoveryBacklog(ctx, 200); err == nil {
			p.publish("dashboard.discovered_categories", backlog)
		}
	}
	if p.cfg.AdminAPIBase != "" {
		var health map[string]interface{}
		if err := p.getJSON(ctx, "/api/v1/internal/health", &health); err == nil && health != nil {
			p.publish("dashboard.health", health)
			p.publish("health.status", health)
		}
		var scraping map[string]interface{}
		if err := p.getJSON(ctx, "/api/v1/analytics/scraping", &scraping); err == nil && scraping != nil {
			p.publish("dashboard.scraping", scraping)
		}
		var workers []map[string]interface{}
		if err := p.getJSON(ctx, "/api/v1/internal/workers", &workers); err == nil && workers != nil {
			p.publish("dashboard.workers", workers)
		}
		var queue map[string]interface{}
		if err := p.getJSON(ctx, "/api/v1/internal/queues/stats", &queue); err == nil && queue != nil {
			p.publish("dashboard.queue", queue)
		}
		var backlog []map[string]interface{}
		if err := p.getJSON(ctx, "/api/v1/internal/sources/backlog?limit=200", &backlog); err == nil && backlog != nil {
			p.publish("dashboard.discovered_categories", backlog)
		}
	}
	if p.ch != nil {
		if chTrends, err := p.ch.DashboardTrends(ctx, 7); err == nil {
			p.publish("dashboard.trends", chTrends)
		}
	}
}

func (p *Poller) pollOps(ctx context.Context) {
	siteKeys := make([]string, 0)
	if p.cfg.AdminAPIBase != "" {
		var scheduler map[string]interface{}
		if err := p.getJSON(ctx, "/api/v1/internal/ops/scheduler/stats", &scheduler); err == nil && scheduler != nil {
			p.publish("ops.scheduler_stats", scheduler)
		} else if err != nil {
			log.Printf("pollOps scheduler stats failed: %v", err)
		}
		var overviewResp map[string]interface{}
		if err := p.getJSON(ctx, "/api/v1/internal/ops/overview", &overviewResp); err == nil && overviewResp != nil {
			p.publish("ops.overview", overviewResp)
			if queue, ok := overviewResp["queue"]; ok && queue != nil {
				p.publish("dashboard.queue", queue)
			}
		} else if err != nil {
			log.Printf("pollOps overview failed: %v", err)
		}
		var queuedResp map[string]interface{}
		if err := p.getJSON(ctx, "/api/v1/internal/ops/runs/queued?limit=200", &queuedResp); err == nil && queuedResp != nil {
			p.publish("ops.runs.queued", queuedResp)
		} else if err != nil {
			log.Printf("pollOps runs queued failed: %v", err)
		}
		var activeResp map[string]interface{}
		if err := p.getJSON(ctx, "/api/v1/internal/ops/runs/active?limit=200", &activeResp); err == nil && activeResp != nil {
			p.publish("ops.runs.active", activeResp)
		} else if err != nil {
			log.Printf("pollOps runs active failed: %v", err)
		}
		if len(siteKeys) > 0 {
			limit := p.cfg.PipelineSiteLimit
			if limit <= 0 || limit > len(siteKeys) {
				limit = len(siteKeys)
			}
			pipelineMap := map[string]interface{}{}
			for _, key := range siteKeys[:limit] {
				var pipeline interface{}
				path := fmt.Sprintf(
					"/api/v1/internal/ops/sites/%s/pipeline?lane_limit=120&lane_offset=0",
					url.PathEscape(key),
				)
				if err := p.getJSON(ctx, path, &pipeline); err == nil && pipeline != nil {
					pipelineMap[key] = pipeline
				}
			}
			if len(pipelineMap) > 0 {
				p.publish("ops.pipeline", pipelineMap)
			}
		}
	}

	if p.ch != nil {
		chCtx, cancel := context.WithTimeout(ctx, 3*time.Second)
		defer cancel()
		if overview, err := p.ch.OpsOverview(chCtx); err == nil {
			p.publish("ops.overview", overview)
		}
		var (
			discoveryCounts map[string]map[string]uint64
			productCounts   map[string]uint64
			runCounts       map[int]map[string]uint64
		)
		discoveryCounts, _ = p.ch.OpsDiscoveryCountsBySite(chCtx)
		productCounts, _ = p.ch.ProductsCountBySite(chCtx)
		runCounts, _ = p.ch.OpsRunCountsBySource(chCtx)
		var sourcesAll []map[string]interface{}
		if sites, err := p.ch.OpsSitesLatest(chCtx); err == nil {
			sourcesAll = sites
			sites = dedupeSitesByKey(sites)
			enrichOpsSiteCounters(sites, discoveryCounts, productCounts, runCounts)
			publishOpsSites(p, sites)
			seenKeys := map[string]bool{}
			for _, site := range sites {
				if site == nil {
					continue
				}
				key := fmt.Sprintf("%v", site["site_key"])
				if key == "" || seenKeys[key] {
					continue
				}
				seenKeys[key] = true
				siteKeys = append(siteKeys, key)
			}
		}
		if listSources, err := p.ch.SourcesLatestByType(chCtx, "list"); err == nil {
			normalizeSourceTimes(listSources, "last_synced_at", "next_sync_at")
			p.publish("ops.discovery", map[string]interface{}{"items": listSources})
		}
		if runs, err := p.ch.OpsRunsLatest(chCtx); err == nil {
			sourceByID := map[string]map[string]interface{}{}
			for _, src := range sourcesAll {
				if src == nil {
					continue
				}
				id := fmt.Sprintf("%v", src["id"])
				if id == "" {
					id = fmt.Sprintf("%v", src["source_id"])
				}
				if id == "" {
					continue
				}
				sourceByID[id] = src
			}
			details := map[string]interface{}{}
			enriched := make([]map[string]interface{}, 0, len(runs))
			for _, run := range runs {
				if run == nil {
					continue
				}
				if srcID := fmt.Sprintf("%v", run["source_id"]); srcID != "" {
					if src, ok := sourceByID[srcID]; ok {
						if run["site_key"] == nil || run["site_key"] == "" {
							run["site_key"] = src["site_key"]
						}
						if run["source_url"] == nil || run["source_url"] == "" {
							run["source_url"] = src["url"]
						}
						if run["source_name"] == nil || run["source_name"] == "" {
							if cfg, ok := src["config"].(map[string]interface{}); ok {
								if name := fmt.Sprintf("%v", cfg["discovery_name"]); name != "" {
									run["source_name"] = name
								}
							}
							if run["source_name"] == nil || run["source_name"] == "" {
								run["source_name"] = src["name"]
							}
						}
						if run["category_name"] == nil || run["category_name"] == "" {
							if cfg, ok := src["config"].(map[string]interface{}); ok {
								if name := fmt.Sprintf("%v", cfg["discovery_name"]); name != "" {
									run["category_name"] = name
								}
							}
						}
					}
				}
				id := fmt.Sprintf("%v", run["id"])
				if id == "" {
					id = fmt.Sprintf("%v", run["run_id"])
				}
				if id != "" {
					details[id] = run
				}
				enriched = append(enriched, run)
			}
			p.publish("ops.run_details", details)
			// Use CH for completed/error (API endpoints are not available).
			p.publish("ops.runs.completed", map[string]interface{}{"items": filterByStatus(enriched, "completed")})
			p.publish("ops.runs.error", map[string]interface{}{"items": filterByStatus(enriched, "error")})
			// Only fallback to CH for active/queued if API didn't populate them yet.
			if p.cfg.AdminAPIBase == "" {
				p.publish("ops.runs.active", map[string]interface{}{"items": filterByStatus(enriched, "processing")})
				p.publish("ops.runs.queued", map[string]interface{}{"items": filterByStatus(enriched, "queued", "pending")})
			}
		}
	}

	if p.ch != nil {
		itemsTrend := map[string]interface{}{}
		for _, bucket := range []string{"week", "day", "hour", "minute"} {
			if out, err := p.ch.OpsItemsTrend(ctx, 30, bucket); err == nil && out != nil {
				itemsTrend[bucket] = out
			} else if err != nil {
				log.Printf("pollOps items trend failed (%s): %v", bucket, err)
			}
		}
		if len(itemsTrend) > 0 {
			p.publish("ops.items_trend", itemsTrend)
		}
		tasksTrend := map[string]interface{}{}
		for _, bucket := range []string{"week", "day", "hour", "minute"} {
			if out, err := p.ch.OpsTasksTrend(ctx, 30, bucket); err == nil && out != nil {
				tasksTrend[bucket] = out
			} else if err != nil {
				log.Printf("pollOps tasks trend failed (%s): %v", bucket, err)
			}
		}
		if len(tasksTrend) > 0 {
			p.publish("ops.tasks_trend", tasksTrend)
		}
	}
}

func normalizeSourceTimes(items []map[string]interface{}, keys ...string) {
	if len(items) == 0 || len(keys) == 0 {
		return
	}
	for _, item := range items {
		if item == nil {
			continue
		}
		for _, key := range keys {
			val, ok := item[key]
			if !ok || val == nil {
				continue
			}
			switch v := val.(type) {
			case string:
				if strings.Contains(v, "T") {
					continue
				}
				if strings.Contains(v, " ") {
					item[key] = strings.Replace(v, " ", "T", 1)
				}
			}
		}
	}
}

func (p *Poller) pollCatalog(ctx context.Context) {
	if p.ch != nil {
	}
}

func (p *Poller) pollSettings(ctx context.Context) {
	if p.ch != nil {
		if runtime, err := p.ch.SettingsRuntimeLatest(ctx); err == nil {
			p.publish("settings.runtime", runtime)
		}
		if subscribers, err := p.ch.SubscribersLatest(ctx); err == nil {
			p.publish("settings.subscribers", subscribers)
		}
		if apps, err := p.ch.FrontendAppsLatest(ctx); err == nil {
			p.publish("frontend.apps", apps)
		}
		if releases, err := p.ch.FrontendReleasesLatest(ctx); err == nil {
			p.publish("frontend.releases", releases)
		}
		if profiles, err := p.ch.FrontendProfilesLatest(ctx); err == nil {
			p.publish("frontend.profiles", profiles)
		}
		if rules, err := p.ch.FrontendRulesLatest(ctx); err == nil {
			p.publish("frontend.rules", rules)
		}
		if runtimeState, err := p.ch.SettingsRuntimeEntryLatest(ctx, "frontend_runtime_state"); err == nil && runtimeState != nil {
			p.publish("frontend.runtime_state", runtimeState)
		}
		if allowedHosts, err := p.ch.FrontendAllowedHostsLatest(ctx); err == nil {
			p.publish("frontend.allowed_hosts", allowedHosts)
		}
		if audit, err := p.ch.FrontendAuditLogLatest(ctx); err == nil {
			p.publish("frontend.audit_log", audit)
		}
	}
	if p.cfg.AdminAPIBase != "" {
		var merchants interface{}
		if err := p.getJSON(ctx, "/api/v1/internal/merchants?limit=500&offset=0", &merchants); err == nil && merchants != nil {
			p.publish("settings.merchants", merchants)
		}
	}
	var intelligence interface{}
	if p.ch != nil {
		if chIntel, err := p.ch.IntelligenceSummary(ctx, 7); err == nil {
			intelligence = chIntel
		}
		if intelligence != nil {
			p.publish("intelligence.summary", intelligence)
		}
		if chStats, err := p.ch.LLMStats(ctx, 7); err == nil {
			p.publish("llm.stats", chStats)
		}
		if logs, total, err := p.ch.LLMLogs(ctx, 7, 200, 0, map[string]string{}); err == nil {
			p.publish("llm.logs", map[string]interface{}{"items": logs, "total": total})
		}
		if outliers, err := p.ch.LLMOutliers(ctx, 7, 50, map[string]string{}); err == nil {
			p.publish("llm.outliers", map[string]interface{}{"items": outliers})
		}
		if throughput, err := p.ch.LLMThroughput(ctx, 7, "hour"); err == nil {
			p.publish("llm.throughput", map[string]interface{}{"items": throughput})
		}
		if rows, err := p.ch.LLMBreakdown(ctx, 7, "status"); err == nil {
			p.publish("llm.breakdown.status", map[string]interface{}{"items": rows})
		}
		if rows, err := p.ch.LLMBreakdown(ctx, 7, "provider"); err == nil {
			p.publish("llm.breakdown.provider", map[string]interface{}{"items": rows})
		}
		if rows, err := p.ch.LLMBreakdown(ctx, 7, "model"); err == nil {
			p.publish("llm.breakdown.model", map[string]interface{}{"items": rows})
		}
		if rows, err := p.ch.LLMBreakdown(ctx, 7, "call_type"); err == nil {
			p.publish("llm.breakdown.call_type", map[string]interface{}{"items": rows})
		}
	}
}

func (p *Poller) pollLogs(ctx context.Context) {
	if p.cfg.AdminAPIBase != "" {
		var snap map[string]interface{}
		if err := p.getJSON(ctx, "/api/v1/internal/logs/query?limit=200&since_seconds=300", &snap); err == nil && snap != nil {
			p.publish("logs.snapshot", snap)
			if p.cfg.LogsTailEnabled {
				p.publish("logs.tail", snap)
			}
		}
		var services map[string]interface{}
		if err := p.getJSON(ctx, "/api/v1/internal/logs/services", &services); err == nil && services != nil {
			p.publish("logs.services", services)
		}
	}
}

func filterByStatus(items []map[string]interface{}, statuses ...string) []map[string]interface{} {
	allowed := map[string]bool{}
	for _, s := range statuses {
		allowed[s] = true
	}
	out := make([]map[string]interface{}, 0)
	for _, item := range items {
		status, _ := item["status"].(string)
		if allowed[status] {
			out = append(out, item)
		}
	}
	return out
}

func publishOpsSites(p *Poller, sites []map[string]interface{}) {
	p.publish("ops.sites", map[string]interface{}{"items": sites})
}

func enrichOpsSiteCounters(
	sites []map[string]interface{},
	discoveryCounts map[string]map[string]uint64,
	productCounts map[string]uint64,
	runCounts map[int]map[string]uint64,
) {
	for _, site := range sites {
		if site == nil {
			continue
		}
		siteKey := fmt.Sprintf("%v", site["site_key"])
		sourceID := toInt(site["id"])
		discovered := discoveryCounts[siteKey]
		newCnt := uint64(0)
		promotedCnt := uint64(0)
		rejectedCnt := uint64(0)
		inactiveCnt := uint64(0)
		totalCnt := uint64(0)
		for state, cnt := range discovered {
			switch state {
			case "new":
				newCnt += cnt
			case "promoted":
				promotedCnt += cnt
			case "rejected":
				rejectedCnt += cnt
			case "inactive":
				inactiveCnt += cnt
			default:
				totalCnt += cnt
			}
			totalCnt += cnt
		}
		runs := runCounts[sourceID]
		queued := uint64(0)
		running := uint64(0)
		for status, cnt := range runs {
			switch status {
			case "queued", "pending":
				queued += cnt
			case "processing", "running", "active":
				running += cnt
			}
		}
		counters := map[string]interface{}{
			"discovered_total":    totalCnt,
			"discovered_new":      newCnt,
			"discovered_promoted": promotedCnt,
			"discovered_rejected": rejectedCnt,
			"discovered_inactive": inactiveCnt,
			"products_total":      productCounts[siteKey],
			"queued":              queued,
			"running":             running,
		}
		site["counters"] = counters
	}
}

func toInt(v interface{}) int {
	switch n := v.(type) {
	case int:
		return n
	case int64:
		return int(n)
	case float64:
		return int(n)
	case string:
		if i, err := strconv.Atoi(n); err == nil {
			return i
		}
	}
	return 0
}

func dedupeSitesByKey(items []map[string]interface{}) []map[string]interface{} {
	if len(items) == 0 {
		return items
	}
	out := make([]map[string]interface{}, 0, len(items))
	index := map[string]int{}
	hubByKey := map[string]interface{}{}
	for _, item := range items {
		if item == nil {
			continue
		}
		if fmt.Sprintf("%v", item["type"]) == "hub" {
			key := fmt.Sprintf("%v", item["site_key"])
			if key == "" {
				continue
			}
			if _, ok := hubByKey[key]; !ok {
				hubByKey[key] = item["id"]
			}
		}
	}
	for _, item := range items {
		if item == nil {
			continue
		}
		key := fmt.Sprintf("%v", item["site_key"])
		if key == "" {
			out = append(out, item)
			continue
		}
		if item["runtime_hub_source_id"] == nil {
			if fmt.Sprintf("%v", item["type"]) == "hub" {
				item["runtime_hub_source_id"] = item["id"]
			} else if hubID, ok := hubByKey[key]; ok {
				item["runtime_hub_source_id"] = hubID
			}
		}
		if idx, ok := index[key]; ok {
			// Prefer hub entry if available.
			if fmt.Sprintf("%v", item["type"]) == "hub" {
				out[idx] = item
			}
			continue
		}
		index[key] = len(out)
		out = append(out, item)
	}
	return out
}
