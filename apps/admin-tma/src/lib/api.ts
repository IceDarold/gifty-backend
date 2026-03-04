"use client";

type ServerApiError = Error & {
  status?: number;
  payload?: any;
};

const isObject = (value: unknown): value is Record<string, any> =>
  typeof value === "object" && value !== null;

export const isServerApiError = (err: unknown): err is ServerApiError => {
  return err instanceof Error && ("status" in err || "payload" in err);
};

export const getApiErrorStatus = (err: unknown): number | null => {
  if (!isServerApiError(err)) return null;
  return typeof err.status === "number" ? err.status : null;
};

export const getApiErrorMessage = (err: unknown): string => {
  if (!err) return "Unknown error";
  if (typeof err === "string") return err;
  if (err instanceof Error) return err.message || "Error";
  return "Error";
};

export const getInitDataRaw = (): string => {
  try {
    const tg = (window as any)?.Telegram?.WebApp;
    const initData = tg?.initData;
    return typeof initData === "string" ? initData : "";
  } catch {
    return "";
  }
};

const buildAuthHeaders = () => {
  const headers: Record<string, string> = {};
  const initData = getInitDataRaw();
  if (initData) {
    headers["X-Tg-Init-Data"] = initData;
  }
  return headers;
};

const buildQuery = (params?: Record<string, any>) => {
  const sp = new URLSearchParams();
  for (const [key, value] of Object.entries(params || {})) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) {
      for (const v of value) sp.append(key, String(v));
      continue;
    }
    sp.set(key, String(value));
  }
  const qs = sp.toString();
  return qs ? `?${qs}` : "";
};

const apiJson = async <T>(
  path: string,
  opts?: { method?: string; body?: any; query?: Record<string, any> },
): Promise<T> => {
  const query = buildQuery(opts?.query);
  const res = await fetch(`${path}${query}`, {
    method: opts?.method || "GET",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: opts?.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });

  let payload: any = null;
  try {
    payload = await res.json();
  } catch {
    payload = null;
  }

  if (!res.ok) {
    const err: ServerApiError = new Error(
      (isObject(payload) && typeof payload?.detail === "string" && payload.detail) ||
        `API error (${res.status})`,
    );
    err.status = res.status;
    err.payload = payload;
    throw err;
  }

  return payload as T;
};

export const authWithTelegram = async () => {
  // Server-side verification happens in backend internal router; for admin-tma we just ensure initData exists.
  const initData = getInitDataRaw();
  if (!initData) return { ok: false, reason: "missing_init_data" };
  return { ok: true };
};

export const getOpsStreamUrl = () => {
  const base = "/api/v1/internal/ops/stream";
  if (typeof window === "undefined") return base;
  const url = new URL(base, window.location.origin);
  const initData = getInitDataRaw();
  if (initData) url.searchParams.set("tg_init_data", initData);
  return url.toString();
};

export const getLogsStreamUrl = (params?: { service?: string; q?: string; limit?: number }) => {
  const base = "/api/v1/internal/logs/stream";
  if (typeof window === "undefined") return `${base}${buildQuery(params as any)}`;
  const url = new URL(base, window.location.origin);
  const initData = getInitDataRaw();
  if (initData) url.searchParams.set("tg_init_data", initData);
  if (params?.service) url.searchParams.set("service", params.service);
  if (params?.q) url.searchParams.set("q", params.q);
  if (params?.limit) url.searchParams.set("limit", String(params.limit));
  return url.toString();
};

// ---------------------------
// Analytics (AI / LLM)
// ---------------------------

export const fetchIntelligence = async (days: number = 7) => {
  return apiJson<any>("/api/v1/internal/analytics/intelligence", { query: { days } });
};

export const fetchLLMLogs = async (params?: {
  days?: number;
  limit?: number;
  offset?: number;
  provider?: string;
  model?: string;
  call_type?: string;
  status?: string;
  session_id?: string;
  experiment_id?: string;
  variant_id?: string;
}) => {
  return apiJson<any>("/api/v1/internal/analytics/llm/logs", { query: params as any });
};

export const fetchLLMThroughput = async (params?: {
  days?: number;
  bucket?: "minute" | "hour" | "day" | "week";
  provider?: string;
  model?: string;
  call_type?: string;
  status?: string;
}) => {
  return apiJson<any>("/api/v1/internal/analytics/llm/throughput", { query: params as any });
};

export const fetchLLMBreakdown = async (params?: { days?: number; group_by?: string; limit?: number }) => {
  return apiJson<any>("/api/v1/internal/analytics/llm/breakdown", { query: params as any });
};

// ---------------------------
// Ops runtime
// ---------------------------

export const fetchOpsRuntimeSettings = async () => apiJson<any>("/api/v1/internal/ops/runtime-settings");
export const updateOpsRuntimeSettings = async (payload: Record<string, unknown>) =>
  apiJson<any>("/api/v1/internal/ops/runtime-settings", { method: "PATCH", body: payload });

export const fetchOpsOverview = async () => apiJson<any>("/api/v1/internal/ops/overview");
export const fetchOpsSites = async () => apiJson<any>("/api/v1/internal/ops/sites");
export const fetchOpsPipeline = async (siteKey: string) =>
  apiJson<any>(`/api/v1/internal/ops/sites/${encodeURIComponent(siteKey)}/pipeline`);
export const fetchOpsActiveRuns = async (limit: number = 200) =>
  apiJson<any>("/api/v1/internal/ops/runs/active", { query: { limit } });
export const fetchOpsQueuedRuns = async (limit: number = 200) =>
  apiJson<any>("/api/v1/internal/ops/runs/queued", { query: { limit } });
export const fetchOpsRunDetails = async (runId: number) =>
  apiJson<any>(`/api/v1/internal/ops/runs/${runId}`);
export const retryOpsRun = async (runId: number) =>
  apiJson<any>(`/api/v1/internal/ops/runs/${runId}/retry`, { method: "POST", body: {} });

export const fetchOpsSchedulerStats = async () => apiJson<any>("/api/v1/internal/ops/scheduler/stats");
export const pauseOpsScheduler = async () => apiJson<any>("/api/v1/internal/ops/scheduler/pause", { method: "POST", body: {} });
export const resumeOpsScheduler = async () => apiJson<any>("/api/v1/internal/ops/scheduler/resume", { method: "POST", body: {} });
export const pauseOpsWorker = async (workerId: string) =>
  apiJson<any>(`/api/v1/internal/ops/workers/${encodeURIComponent(workerId)}/pause`, { method: "POST", body: {} });
export const resumeOpsWorker = async (workerId: string) =>
  apiJson<any>(`/api/v1/internal/ops/workers/${encodeURIComponent(workerId)}/resume`, { method: "POST", body: {} });

export const fetchOpsItemsTrend = async (params?: { granularity?: string; buckets?: number; force_fresh?: boolean }) =>
  apiJson<any>("/api/v1/internal/ops/items-trend", { query: params as any });
export const fetchOpsTasksTrend = async (params?: { granularity?: string; buckets?: number; force_fresh?: boolean }) =>
  apiJson<any>("/api/v1/internal/ops/tasks-trend", { query: params as any });
export const fetchOpsSourceItemsTrend = async (sourceId: number, params?: { granularity?: string; buckets?: number; force_fresh?: boolean }) =>
  apiJson<any>(`/api/v1/internal/ops/sources/${sourceId}/items-trend`, { query: params as any });

export const fetchOpsDiscoveryCategories = async (params?: {
  site_key?: string;
  state?: string;
  q?: string;
  limit?: number;
  offset?: number;
}) => apiJson<any>("/api/v1/internal/ops/discovery/categories", { query: params as any });

export const fetchOpsDiscoveryCategoryDetails = async (categoryId: number) =>
  apiJson<any>(`/api/v1/internal/ops/discovery/categories/${categoryId}`);

export const promoteOpsDiscovery = async (payload: { category_id: number }) =>
  apiJson<any>("/api/v1/internal/ops/discovery/promote", { method: "POST", body: payload });
export const rejectOpsDiscovery = async (payload: { category_id: number }) =>
  apiJson<any>("/api/v1/internal/ops/discovery/reject", { method: "POST", body: payload });
export const reactivateOpsDiscovery = async (payload: { category_id: number }) =>
  apiJson<any>("/api/v1/internal/ops/discovery/reactivate", { method: "POST", body: payload });
export const runOpsDiscoveryCategoryNow = async (categoryId: number) =>
  apiJson<any>(`/api/v1/internal/ops/discovery/categories/${categoryId}/run-now`, { method: "POST", body: {} });
export const runOpsDiscoveryAllForSite = async (payload: { site_key: string }) =>
  apiJson<any>("/api/v1/internal/ops/discovery/run-all", { method: "POST", body: payload });
export const runOpsSiteDiscovery = async (siteKey: string) =>
  apiJson<any>(`/api/v1/internal/ops/sites/${encodeURIComponent(siteKey)}/run-discovery`, { method: "POST", body: {} });

export const bulkUpdateOpsSources = async (payload: any) =>
  apiJson<any>("/api/v1/internal/ops/sources/bulk-update", { method: "POST", body: payload });

// ---------------------------
// Logs (Loki)
// ---------------------------

export const fetchLogServices = async () => apiJson<any>("/api/v1/internal/logs/services");
export const fetchLogsQuery = async (params?: { service?: string; q?: string; limit?: number; since_seconds?: number }) =>
  apiJson<any>("/api/v1/internal/logs/query", { query: params as any });

// ---------------------------
// Parsing sources / dashboard helpers
// ---------------------------

export const fetchStats = async () => {
  // Prefer analytics GraphQL stats (KPIs) when available; fallback to parsing stats.
  try {
    const gql = await apiJson<any>("/api/v1/analytics/graphql", {
      method: "POST",
      body: { query: "query { stats { dau quiz_completion_rate gift_ctr total_sessions last_updated } }" },
    });
    return gql?.data?.stats ?? gql?.stats ?? gql;
  } catch {
    return apiJson<any>("/api/v1/internal/stats");
  }
};

export const fetchTrends = async (days: number = 7) => apiJson<any>("/api/v1/analytics/trends", { query: { days } });
export const fetchScraping = async () => apiJson<any>("/api/v1/analytics/scraping");
export const fetchHealth = async () => apiJson<any>("/api/v1/internal/health");

export const fetchSources = async () => apiJson<any>("/api/v1/internal/sources");
export const fetchSourceDetails = async (id: number) => apiJson<any>(`/api/v1/internal/sources/${id}`);
export const fetchSourceProducts = async (id: number, limit: number = 50, offset: number = 0, q?: string) =>
  apiJson<any>(`/api/v1/internal/sources/${id}/products`, { query: { limit, offset, q } });
export const deleteSourceProducts = async (id: number) =>
  apiJson<any>(`/api/v1/internal/sources/${id}/data`, { method: "DELETE" });
export const forceRunSource = async (id: number, strategy?: string) =>
  apiJson<any>(`/api/v1/internal/sources/${id}/force-run`, { method: "POST", query: { strategy }, body: {} });
export const updateSource = async (id: number, updates: Record<string, any>) =>
  apiJson<any>(`/api/v1/internal/sources/${id}`, { method: "PATCH", body: updates });
export const syncSources = async (spiders: string[]) =>
  apiJson<any>("/api/v1/internal/sources/sync-spiders", { method: "POST", body: { spiders } });
export const runAllSpiders = async () => apiJson<any>("/api/v1/internal/sources/run-all", { method: "POST", body: {} });
export const runSingleSpider = async (id: number) => forceRunSource(id);

export const fetchDiscoveredCategories = async (limit: number = 200) =>
  apiJson<any>("/api/v1/internal/sources/backlog", { query: { limit } });
export const activateDiscoveredCategories = async (category_ids: number[]) =>
  apiJson<any>("/api/v1/internal/sources/backlog/activate", { method: "POST", body: { category_ids } });

// Catalog / queue
export const fetchQueueStats = async () => apiJson<any>("/api/v1/internal/queues/stats");
export const fetchQueueTasks = async (limit: number = 50) => apiJson<any>("/api/v1/internal/queues/tasks", { query: { limit } });
export const fetchQueueHistory = async (limit: number = 50) => apiJson<any>("/api/v1/internal/queues/history", { query: { limit } });
export const fetchQueueRunDetails = async (runId: string) => apiJson<any>(`/api/v1/internal/queues/history/${encodeURIComponent(runId)}`);

export const fetchWorkers = async () => apiJson<any>("/api/v1/internal/workers");

export const fetchCatalogProducts = async (limit: number = 20, offset: number = 0, q?: string) =>
  apiJson<any>("/api/v1/internal/products", { query: { limit, offset, search: q } });

// Merchants
export const fetchMerchants = async (params?: { limit?: number; offset?: number; q?: string }) =>
  apiJson<any>("/api/v1/internal/merchants", { query: params as any });
export const updateMerchant = async (siteKey: string, payload: { name?: string; base_url?: string }) =>
  apiJson<any>(`/api/v1/internal/merchants/${encodeURIComponent(siteKey)}`, { method: "PATCH", body: payload });

// Telegram admin subscriptions / settings
export const fetchSubscriber = async (chatId: number) => apiJson<any>(`/api/v1/internal/telegram/subscribers/${chatId}`);
export const subscribeTopic = async (chatId: number, topic: string) =>
  apiJson<any>(`/api/v1/internal/telegram/subscribers/${chatId}/subscribe`, { method: "POST", query: { topic }, body: {} });
export const unsubscribeTopic = async (chatId: number, topic: string) =>
  apiJson<any>(`/api/v1/internal/telegram/subscribers/${chatId}/unsubscribe`, { method: "POST", query: { topic }, body: {} });
export const setLanguage = async (chatId: number, language: string) =>
  apiJson<any>(`/api/v1/internal/telegram/subscribers/${chatId}/language`, { method: "POST", query: { language }, body: {} });
export const sendTestNotification = async (topic: string) =>
  apiJson<any>("/api/v1/internal/telegram/test-notification", { method: "POST", body: { topic } });

// Weeek integration (best-effort)
export const connectWeeek = async (chatId: number, token: string) =>
  apiJson<any>("/api/v1/internal/weeek/connect", { method: "POST", body: { telegram_chat_id: chatId, weeek_api_token: token } });

// Frontend routing control plane
export const fetchFrontendApps = async () => apiJson<any>("/api/v1/internal/frontend/apps");
export const createFrontendApp = async (payload: any) => apiJson<any>("/api/v1/internal/frontend/apps", { method: "POST", body: payload });
export const updateFrontendApp = async (appId: number, payload: any) =>
  apiJson<any>(`/api/v1/internal/frontend/apps/${appId}`, { method: "PATCH", body: payload });
export const deleteFrontendApp = async (appId: number) =>
  apiJson<any>(`/api/v1/internal/frontend/apps/${appId}`, { method: "DELETE" });

export const fetchFrontendReleases = async () => apiJson<any>("/api/v1/internal/frontend/releases");
export const createFrontendRelease = async (payload: any) =>
  apiJson<any>("/api/v1/internal/frontend/releases", { method: "POST", body: payload });
export const updateFrontendRelease = async (releaseId: number, payload: any) =>
  apiJson<any>(`/api/v1/internal/frontend/releases/${releaseId}`, { method: "PATCH", body: payload });
export const deleteFrontendRelease = async (releaseId: number) =>
  apiJson<any>(`/api/v1/internal/frontend/releases/${releaseId}`, { method: "DELETE" });
export const validateFrontendRelease = async (releaseId: number) =>
  apiJson<any>(`/api/v1/internal/frontend/releases/${releaseId}/validate`, { method: "POST", body: {} });

export const fetchFrontendProfiles = async () => apiJson<any>("/api/v1/internal/frontend/profiles");
export const createFrontendProfile = async (payload: any) =>
  apiJson<any>("/api/v1/internal/frontend/profiles", { method: "POST", body: payload });
export const updateFrontendProfile = async (profileId: number, payload: any) =>
  apiJson<any>(`/api/v1/internal/frontend/profiles/${profileId}`, { method: "PATCH", body: payload });
export const deleteFrontendProfile = async (profileId: number) =>
  apiJson<any>(`/api/v1/internal/frontend/profiles/${profileId}`, { method: "DELETE" });

export const fetchFrontendRules = async () => apiJson<any>("/api/v1/internal/frontend/rules");
export const createFrontendRule = async (payload: any) =>
  apiJson<any>("/api/v1/internal/frontend/rules", { method: "POST", body: payload });
export const updateFrontendRule = async (ruleId: number, payload: any) =>
  apiJson<any>(`/api/v1/internal/frontend/rules/${ruleId}`, { method: "PATCH", body: payload });
export const deleteFrontendRule = async (ruleId: number) =>
  apiJson<any>(`/api/v1/internal/frontend/rules/${ruleId}`, { method: "DELETE" });

export const fetchFrontendRuntimeState = async () => apiJson<any>("/api/v1/internal/frontend/runtime-state");
export const updateFrontendRuntimeState = async (payload: any) =>
  apiJson<any>("/api/v1/internal/frontend/runtime-state", { method: "PATCH", body: payload });
export const publishFrontendConfig = async () => apiJson<any>("/api/v1/internal/frontend/publish", { method: "POST", body: {} });
export const rollbackFrontendConfig = async () => apiJson<any>("/api/v1/internal/frontend/rollback", { method: "POST", body: {} });

export const fetchFrontendAllowedHosts = async () => apiJson<any>("/api/v1/internal/frontend/allowed-hosts");
export const createFrontendAllowedHost = async (payload: any) =>
  apiJson<any>("/api/v1/internal/frontend/allowed-hosts", { method: "POST", body: payload });
export const updateFrontendAllowedHost = async (hostId: number, payload: any) =>
  apiJson<any>(`/api/v1/internal/frontend/allowed-hosts/${hostId}`, { method: "PATCH", body: payload });
export const deleteFrontendAllowedHost = async (hostId: number) =>
  apiJson<any>(`/api/v1/internal/frontend/allowed-hosts/${hostId}`, { method: "DELETE" });

export const fetchFrontendAuditLog = async () => apiJson<any>("/api/v1/internal/frontend/audit-log");
