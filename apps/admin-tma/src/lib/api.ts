import axios, { AxiosError } from "axios";

type Dict = Record<string, unknown>;

const INTERNAL_PREFIX = "/api/v1/internal";
const ANALYTICS_PREFIX = "/api/v1/analytics";

const safeWindow = () => (typeof window !== "undefined" ? window : null);

export const getInitDataRaw = (): string => {
  const w = safeWindow() as any;
  const raw = w?.Telegram?.WebApp?.initData;
  if (typeof raw === "string" && raw.trim()) return raw;

  const fromEnv = process.env.NEXT_PUBLIC_TG_INIT_DATA || process.env.NEXT_PUBLIC_TELEGRAM_INIT_DATA || "";
  if (fromEnv && fromEnv.trim()) return fromEnv.trim();

  try {
    const fromStorage = w?.localStorage?.getItem("tg_init_data") || w?.localStorage?.getItem("telegram_init_data");
    if (typeof fromStorage === "string" && fromStorage.trim()) return fromStorage.trim();
  } catch {
    // ignore
  }

  const isDev = process.env.NODE_ENV === "development" || process.env.NEXT_PUBLIC_ENV === "dev";
  if (isDev) return "dev_user_1821014162";
  return "";
};

const getInternalToken = (): string => {
  const fromEnv =
    process.env.NEXT_PUBLIC_INTERNAL_API_TOKEN ||
    process.env.NEXT_PUBLIC_INTERNAL_TOKEN ||
    process.env.NEXT_PUBLIC_API_INTERNAL_TOKEN ||
    "";
  if (fromEnv && fromEnv.trim()) return fromEnv.trim();

  const w = safeWindow();
  try {
    const fromStorage = w?.localStorage?.getItem("internal_api_token") || w?.localStorage?.getItem("internal_token");
    return (fromStorage && fromStorage.trim()) || "";
  } catch {
    return "";
  }
};

const buildAuthHeaders = () => {
  const headers: Record<string, string> = {};
  const tg = getInitDataRaw();
  const internal = getInternalToken();
  if (tg) headers["x-tg-init-data"] = tg;
  if (internal) headers["x-internal-token"] = internal;
  return headers;
};

const client = axios.create({
  // Use same-origin by default; can be overridden for deployed setups.
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL || "",
  timeout: 20000,
});

const getJson = async <T = any>(url: string, params?: Dict): Promise<T> => {
  const res = await client.get<T>(url, { params, headers: buildAuthHeaders() });
  return res.data as T;
};

const postJson = async <T = any>(url: string, data?: any, params?: Dict): Promise<T> => {
  const res = await client.post<T>(url, data ?? {}, { params, headers: buildAuthHeaders() });
  return res.data as T;
};

const putJson = async <T = any>(url: string, data?: any, params?: Dict): Promise<T> => {
  const res = await client.put<T>(url, data ?? {}, { params, headers: buildAuthHeaders() });
  return res.data as T;
};

const patchJson = async <T = any>(url: string, data?: any, params?: Dict): Promise<T> => {
  const res = await client.patch<T>(url, data ?? {}, { params, headers: buildAuthHeaders() });
  return res.data as T;
};

const deleteJson = async <T = any>(url: string, params?: Dict): Promise<T> => {
  const res = await client.delete<T>(url, { params, headers: buildAuthHeaders() });
  return res.data as T;
};

const withQuery = (path: string, params: Record<string, string | number | boolean | undefined | null>) => {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null) continue;
    qs.set(k, String(v));
  }
  const s = qs.toString();
  return s ? `${path}?${s}` : path;
};

const pickAuthQuery = () => {
  const tg = getInitDataRaw();
  if (tg) return { tg_init_data: tg };
  const internal = getInternalToken();
  if (internal) return { internal_token: internal };
  return {};
};

export const isServerApiError = (err: unknown): err is AxiosError => axios.isAxiosError(err);

export const getApiErrorStatus = (err: unknown): number | null => {
  if (!axios.isAxiosError(err)) return null;
  const status = err.response?.status;
  return typeof status === "number" ? status : null;
};

export const getApiErrorMessage = (err: unknown): string => {
  if (!axios.isAxiosError(err)) return "Unknown error";
  const data: any = err.response?.data;
  const detail = data?.detail ?? data?.message;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (typeof err.message === "string" && err.message.trim()) return err.message;
  return "Request failed";
};

// --- Auth (Telegram mini app) ---
export const authWithTelegram = async () => {
  const init_data = getInitDataRaw();
  return postJson(`${INTERNAL_PREFIX}/webapp/auth`, { init_data });
};

// --- Dashboard ---
export const fetchStats = () => getJson(`${INTERNAL_PREFIX}/stats`);
export const fetchHealth = () => getJson(`${INTERNAL_PREFIX}/health`);
export const fetchScraping = () => getJson(`${ANALYTICS_PREFIX}/scraping`);
export const fetchSources = () => getJson(`${INTERNAL_PREFIX}/sources`);
export const fetchSourceDetails = (sourceId: number) => getJson(`${INTERNAL_PREFIX}/sources/${sourceId}`);
export const fetchSourceProducts = (sourceId: number, limit = 50, offset = 0) =>
  getJson(`${INTERNAL_PREFIX}/sources/${sourceId}/products`, { limit, offset });
export const deleteSourceProducts = (sourceId: number) => deleteJson(`${INTERNAL_PREFIX}/sources/${sourceId}/data`);
export const forceRunSource = (sourceId: number, strategy?: string) =>
  postJson(`${INTERNAL_PREFIX}/sources/${sourceId}/force-run`, {}, strategy ? { strategy } : undefined);
export const updateSource = (sourceId: number, updates: Record<string, any>) =>
  patchJson(`${INTERNAL_PREFIX}/sources/${sourceId}`, updates);
export const syncSources = (availableSpiders: string[]) =>
  postJson(`${INTERNAL_PREFIX}/sources/sync-spiders`, { available_spiders: availableSpiders });
export const fetchSubscriber = (chatId: number) => getJson(`${INTERNAL_PREFIX}/telegram/subscribers/${chatId}`);
export const subscribeTopic = (chatId: number, topic: string) =>
  postJson(`${INTERNAL_PREFIX}/telegram/subscribers/${chatId}/subscribe`, {}, { topic });
export const unsubscribeTopic = (chatId: number, topic: string) =>
  postJson(`${INTERNAL_PREFIX}/telegram/subscribers/${chatId}/unsubscribe`, {}, { topic });
export const setLanguage = (chatId: number, language: string) =>
  postJson(`${INTERNAL_PREFIX}/telegram/subscribers/${chatId}/language`, {}, { language });

// Optional endpoint; keep for UI wiring even if backend route is absent.
export const sendTestNotification = (topic: string) => postJson(`${INTERNAL_PREFIX}/telegram/test-notification`, {}, { topic });

export const runAllSpiders = () => postJson(`${INTERNAL_PREFIX}/sources/run-all`, {});
export const runSingleSpider = (sourceId: number) => postJson(`${INTERNAL_PREFIX}/sources/${sourceId}/force-run`, {});

export const fetchWorkers = () => getJson(`${INTERNAL_PREFIX}/workers`);
export const fetchQueueStats = () => getJson(`${INTERNAL_PREFIX}/queues/stats`);
export const fetchQueueTasks = (limit = 50) => getJson(`${INTERNAL_PREFIX}/queues/tasks`, { limit });
export const fetchQueueHistory = (limit = 100, offset = 0, status?: string) =>
  getJson(`${INTERNAL_PREFIX}/queues/history`, { limit, offset, status });
export const fetchQueueRunDetails = (runId: number) => getJson(`${INTERNAL_PREFIX}/queues/history/${runId}`);

export const fetchCatalogProducts = (limit = 20, offset = 0, search?: string, merchant?: string) =>
  getJson(`${INTERNAL_PREFIX}/products`, { limit, offset, search: search || undefined, merchant: merchant || undefined });

export const fetchDiscoveredCategories = (limit = 200) => getJson(`${INTERNAL_PREFIX}/sources/backlog`, { limit });
export const activateDiscoveredCategories = (categoryIds: number[]) =>
  postJson(`${INTERNAL_PREFIX}/sources/backlog/activate`, { category_ids: categoryIds });

export const connectWeeek = (chatId: number, token: string) =>
  postJson(`${INTERNAL_PREFIX}/weeek/connect`, { telegram_chat_id: chatId, weeek_api_token: token });

// Merchants
export const fetchMerchants = (params?: { limit?: number; offset?: number; q?: string }) =>
  getJson(`${INTERNAL_PREFIX}/merchants`, params);
export const updateMerchant = (siteKey: string, payload: { name?: string; base_url?: string }) =>
  patchJson(`${INTERNAL_PREFIX}/merchants/${encodeURIComponent(siteKey)}`, payload);

// --- Analytics ---
export const fetchTrends = (days = 7) => getJson(`${ANALYTICS_PREFIX}/trends`, { days });
export const fetchIntelligence = (days = 7) => getJson(`${INTERNAL_PREFIX}/analytics/intelligence`, { days });

// --- Logs (Loki) ---
export const fetchLogServices = () => getJson(`${INTERNAL_PREFIX}/logs/services`);
export const fetchLogsQuery = (params: { service?: string; q?: string; limit?: number; since_seconds?: number }) =>
  getJson(`${INTERNAL_PREFIX}/logs/query`, params);
export const getLogsStreamUrl = (params: { service?: string; q?: string; limit?: number }) =>
  withQuery(`${INTERNAL_PREFIX}/logs/stream`, { ...params, ...pickAuthQuery() });

// --- Ops stream + snapshots ---
export const getOpsStreamUrl = () => withQuery(`${INTERNAL_PREFIX}/ops/stream`, pickAuthQuery());
export const fetchOpsOverview = () => getJson(`${INTERNAL_PREFIX}/ops/overview`);
export const fetchOpsSites = () => getJson(`${INTERNAL_PREFIX}/ops/sites`);
export const fetchOpsPipeline = (siteKey: string) => getJson(`${INTERNAL_PREFIX}/ops/sites/${encodeURIComponent(siteKey)}/pipeline`);
export const fetchOpsActiveRuns = (limit = 200) => getJson(`${INTERNAL_PREFIX}/ops/runs/active`, { limit });
export const fetchOpsQueuedRuns = (limit = 200) => getJson(`${INTERNAL_PREFIX}/ops/runs/queued`, { limit });
export const fetchOpsRunDetails = (runId: number) => getJson(`${INTERNAL_PREFIX}/ops/runs/${runId}`);
export const retryOpsRun = (runId: number) => postJson(`${INTERNAL_PREFIX}/ops/runs/${runId}/retry`, {});
export const fetchOpsSchedulerStats = () => getJson(`${INTERNAL_PREFIX}/ops/scheduler/stats`);
export const fetchOpsTasksTrend = (params?: { granularity?: string; buckets?: number }) =>
  getJson(`${INTERNAL_PREFIX}/ops/tasks-trend`, params);
export const fetchOpsItemsTrend = (params?: { granularity?: string; buckets?: number }) =>
  getJson(`${INTERNAL_PREFIX}/ops/items-trend`, params);
export const fetchOpsSourceItemsTrend = (sourceId: number, params?: { granularity?: string; buckets?: number }) =>
  getJson(`${INTERNAL_PREFIX}/ops/sources/${sourceId}/items-trend`, params);

export const fetchOpsDiscoveryCategories = (params: { site_key?: string; state?: string; q?: string; limit?: number; offset?: number }) =>
  getJson(`${INTERNAL_PREFIX}/ops/discovery/categories`, params);
export const fetchOpsDiscoveryCategoryDetails = (categoryId: number) =>
  getJson(`${INTERNAL_PREFIX}/ops/discovery/categories/${categoryId}`);
export const promoteOpsDiscovery = (ids: number[]) => postJson(`${INTERNAL_PREFIX}/ops/discovery/promote`, { ids });
export const rejectOpsDiscovery = (ids: number[]) => postJson(`${INTERNAL_PREFIX}/ops/discovery/reject`, { ids });
export const reactivateOpsDiscovery = (ids: number[]) => postJson(`${INTERNAL_PREFIX}/ops/discovery/reactivate`, { ids });
export const runOpsDiscoveryCategoryNow = (categoryId: number) =>
  postJson(`${INTERNAL_PREFIX}/ops/discovery/categories/${categoryId}/run-now`, {});
export const runOpsDiscoveryAllForSite = (siteKey: string) =>
  postJson(`${INTERNAL_PREFIX}/ops/discovery/run-all`, { site_key: siteKey });
export const runOpsSiteDiscovery = (siteKey: string) =>
  postJson(`${INTERNAL_PREFIX}/ops/sites/${encodeURIComponent(siteKey)}/run-discovery`, {});
export const bulkUpdateOpsSources = (payload: Record<string, any>) => postJson(`${INTERNAL_PREFIX}/ops/sources/bulk-update`, payload);

export const pauseOpsWorker = (workerId: string) => postJson(`${INTERNAL_PREFIX}/ops/workers/${encodeURIComponent(workerId)}/pause`, {});
export const resumeOpsWorker = (workerId: string) => postJson(`${INTERNAL_PREFIX}/ops/workers/${encodeURIComponent(workerId)}/resume`, {});
export const pauseOpsScheduler = () => postJson(`${INTERNAL_PREFIX}/ops/scheduler/pause`, {});
export const resumeOpsScheduler = () => postJson(`${INTERNAL_PREFIX}/ops/scheduler/resume`, {});

export const fetchOpsRuntimeSettings = () => getJson(`${INTERNAL_PREFIX}/ops/runtime-settings`);
export const updateOpsRuntimeSettings = (payload: Record<string, unknown>) =>
  putJson(`${INTERNAL_PREFIX}/ops/runtime-settings`, payload);

// --- Frontend routing (deployment config) ---
export const fetchFrontendApps = () => getJson(`${INTERNAL_PREFIX}/frontend/apps`);
export const createFrontendApp = (payload: Record<string, unknown>) => postJson(`${INTERNAL_PREFIX}/frontend/apps`, payload);
export const updateFrontendApp = (id: number, payload: Record<string, unknown>) =>
  postJson(`${INTERNAL_PREFIX}/frontend/apps`, { id, ...payload });
export const deleteFrontendApp = (id: number) => deleteJson(`${INTERNAL_PREFIX}/frontend/apps/${id}`);

export const fetchFrontendReleases = () => getJson(`${INTERNAL_PREFIX}/frontend/releases`);
export const createFrontendRelease = (payload: Record<string, unknown>) => postJson(`${INTERNAL_PREFIX}/frontend/releases`, payload);
export const updateFrontendRelease = (id: number, payload: Record<string, unknown>) =>
  postJson(`${INTERNAL_PREFIX}/frontend/releases`, { id, ...payload });
export const deleteFrontendRelease = (id: number) => deleteJson(`${INTERNAL_PREFIX}/frontend/releases/${id}`);
export const validateFrontendRelease = (id: number) =>
  postJson(`${INTERNAL_PREFIX}/frontend/releases/${id}/validate`, {});

export const fetchFrontendProfiles = () => getJson(`${INTERNAL_PREFIX}/frontend/profiles`);
export const createFrontendProfile = (payload: Record<string, unknown>) => postJson(`${INTERNAL_PREFIX}/frontend/profiles`, payload);
export const updateFrontendProfile = (id: number, payload: Record<string, unknown>) =>
  postJson(`${INTERNAL_PREFIX}/frontend/profiles`, { id, ...payload });
export const fetchFrontendRules = () => getJson(`${INTERNAL_PREFIX}/frontend/rules`);
export const createFrontendRule = (payload: Record<string, unknown>) => postJson(`${INTERNAL_PREFIX}/frontend/rules`, payload);
export const updateFrontendRule = (id: number, payload: Record<string, unknown>) =>
  postJson(`${INTERNAL_PREFIX}/frontend/rules`, { id, ...payload });
export const deleteFrontendRule = (id: number) => deleteJson(`${INTERNAL_PREFIX}/frontend/rules/${id}`);

export const fetchFrontendRuntimeState = () => getJson(`${INTERNAL_PREFIX}/frontend/runtime-state`);
export const updateFrontendRuntimeState = (payload: Record<string, unknown>) =>
  postJson(`${INTERNAL_PREFIX}/frontend/runtime-state`, payload);

export const fetchFrontendAllowedHosts = () => getJson(`${INTERNAL_PREFIX}/frontend/allowed-hosts`);
export const createFrontendAllowedHost = (payload: Record<string, unknown>) => postJson(`${INTERNAL_PREFIX}/frontend/allowed-hosts`, payload);
export const updateFrontendAllowedHost = (id: number, payload: Record<string, unknown>) =>
  postJson(`${INTERNAL_PREFIX}/frontend/allowed-hosts`, { id, ...payload });
export const deleteFrontendAllowedHost = (id: number) => deleteJson(`${INTERNAL_PREFIX}/frontend/allowed-hosts/${id}`);

export const publishFrontendConfig = () => postJson(`${INTERNAL_PREFIX}/frontend/publish`, {});
export const rollbackFrontendConfig = () => postJson(`${INTERNAL_PREFIX}/frontend/rollback`, {});
export const fetchFrontendAuditLog = (limit = 100, offset = 0) => getJson(`${INTERNAL_PREFIX}/frontend/audit-log`, { limit, offset });
