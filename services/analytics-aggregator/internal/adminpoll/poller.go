package adminpoll

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
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
		if meta, err := p.ch.SnapshotData(ctx, "admin.snapshot_meta"); err == nil {
			p.publish("admin.snapshot_meta", meta)
		}
		if health, err := p.ch.SnapshotData(ctx, "dashboard.health"); err == nil {
			p.publish("dashboard.health", health)
			p.publish("health.status", health)
		}
		if scraping, err := p.ch.SnapshotData(ctx, "dashboard.scraping"); err == nil {
			p.publish("dashboard.scraping", scraping)
		}
		if sources, err := p.ch.SourcesLatest(ctx); err == nil {
			p.publish("dashboard.sources", sources)
		}
		if backlog, err := p.ch.SnapshotData(ctx, "dashboard.discovered_categories"); err == nil {
			p.publish("dashboard.discovered_categories", backlog)
		}
		if workers, err := p.ch.SnapshotData(ctx, "dashboard.workers"); err == nil {
			p.publish("dashboard.workers", workers)
		}
		if queue, err := p.ch.SnapshotData(ctx, "dashboard.queue"); err == nil {
			p.publish("dashboard.queue", queue)
		}
	}
	if p.ch != nil {
		if chTrends, err := p.ch.DashboardTrends(ctx, 7); err == nil {
			p.publish("dashboard.trends", chTrends)
		}
	}
}

func (p *Poller) pollOps(ctx context.Context) {
	if p.ch != nil {
		if overview, err := p.ch.OpsOverview(ctx); err == nil {
			p.publish("ops.overview", overview)
		}
		if sites, err := p.ch.OpsSitesLatest(ctx); err == nil {
			p.publish("ops.sites", map[string]interface{}{"items": dedupeSitesByKey(sites)})
		}
		if pipeline, err := p.ch.SnapshotData(ctx, "ops.pipeline"); err == nil {
			p.publish("ops.pipeline", pipeline)
		}
		if scheduler, err := p.ch.SnapshotData(ctx, "ops.scheduler_stats"); err == nil {
			p.publish("ops.scheduler_stats", scheduler)
		}
		if discovery, err := p.ch.OpsDiscoveryLatest(ctx); err == nil {
			p.publish("ops.discovery", map[string]interface{}{"items": discovery})
		}
		if runs, err := p.ch.OpsRunsLatest(ctx); err == nil {
			details := map[string]interface{}{}
			for _, run := range runs {
				if run == nil {
					continue
				}
				id := fmt.Sprintf("%v", run["id"])
				if id == "" {
					continue
				}
				details[id] = run
			}
			p.publish("ops.run_details", details)
			p.publish("ops.runs.active", filterByStatus(runs, "processing"))
			p.publish("ops.runs.queued", filterByStatus(runs, "queued", "pending"))
			p.publish("ops.runs.completed", filterByStatus(runs, "completed"))
			p.publish("ops.runs.error", filterByStatus(runs, "error"))
		}
	}

	if p.ch != nil {
		if items, err := p.ch.OpsTrend(ctx, "ops.items.count", 7); err == nil {
			p.publish("ops.items_trend", map[string]interface{}{"day": items})
		}
		if tasks, err := p.ch.OpsTrend(ctx, "ops.tasks.count", 7); err == nil {
			p.publish("ops.tasks_trend", map[string]interface{}{"day": tasks})
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
		if merchants, err := p.ch.SnapshotData(ctx, "settings.merchants"); err == nil {
			p.publish("settings.merchants", merchants)
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
	if p.ch != nil {
		if snap, err := p.ch.SnapshotData(ctx, "logs.snapshot"); err == nil {
			p.publish("logs.snapshot", snap)
			if p.cfg.LogsTailEnabled {
				p.publish("logs.tail", snap)
			}
		}
		if services, err := p.ch.SnapshotData(ctx, "logs.services"); err == nil {
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
