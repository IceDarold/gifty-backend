"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode, type UIEvent } from "react";
import {
  Activity,
  AlertCircle,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock3,
  Copy,
  ExternalLink,
  Loader2,
  Play,
  RefreshCcw,
  Server,
  ShieldAlert,
  Sparkles,
  XCircle,
} from "lucide-react";
import { useOperationsData } from "@/hooks/useOperations";
import { useNotificationCenter } from "@/contexts/NotificationCenterContext";
import { getApiErrorMessage, getApiErrorStatus, isServerApiError, pauseOpsScheduler, pauseOpsWorker, resumeOpsScheduler, resumeOpsWorker } from "@/lib/api";
import { openGrafanaExploreLoki, openGrafanaExplorePrometheus } from "@/lib/grafana";
import { useApiErrorToast } from "@/hooks/useApiErrorToast";
import { useRetryRegistry } from "@/contexts/RetryRegistryContext";
import { useAdminRequestQuery } from "@/hooks/useAdminStreamQuery";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CategoriesTable } from "@/components/CategoriesTable";
import {
  formatDateTime,
  formatDayLabel,
  formatDuration,
  formatTrendLabel,
  getRunDisplayTitle,
  isPlaceholderUrl,
  parseLogLine,
  statusBadgeClass,
  type LogFilter,
  type LogItem,
  type ParsedLogLine,
} from "@/components/operations/operationsUtils";

const SITES_PAGE_SIZE = 12;

interface OperationsViewProps {
  onOpenSourceDetails: (
    sourceId: number,
    initial?: { name?: string; slug?: string; url?: string },
  ) => void;
}

const isJsonLikeStart = (line: ParsedLogLine) => {
  const raw = line.raw.trim();
  return raw.startsWith("{") || raw.startsWith("[") || raw.startsWith("{'") || raw.startsWith("[{");
};

const isJsonLikeLine = (line: ParsedLogLine) => {
  const raw = line.raw.trim();
  if (!raw) return false;
  if (raw.startsWith("{") || raw.startsWith("}") || raw.startsWith("[") || raw.startsWith("]")) return true;
  if (/^['"][^'"]+['"]\s*:/.test(raw)) return true;
  if (/^\"[^"]+\"\s*:/.test(raw)) return true;
  if (raw.endsWith(",") && raw.includes(":")) return true;
  return false;
};

const buildLogItems = (lines: ParsedLogLine[]): LogItem[] => {
  const items: LogItem[] = [];
  let i = 0;
  while (i < lines.length) {
    const current = lines[i];
    if (isJsonLikeStart(current)) {
      const jsonLines: ParsedLogLine[] = [current];
      let j = i + 1;
      while (j < lines.length && isJsonLikeLine(lines[j])) {
        jsonLines.push(lines[j]);
        j += 1;
      }
      if (jsonLines.length >= 2) {
        const summaryRaw = jsonLines[0].raw.trim();
        const summary = summaryRaw.length > 92 ? `${summaryRaw.slice(0, 92)}...` : summaryRaw;
        items.push({
          kind: "json",
          id: `json-${i}`,
          lines: jsonLines,
          summary,
          payload: jsonLines.map((l) => l.raw).join("\n"),
        });
        i = j;
        continue;
      }
    }
    items.push({ kind: "line", id: current.id, line: current });
    i += 1;
  }
  return items;
};

const levelBadgeClass = (level: ParsedLogLine["level"]) => {
  switch (level) {
    case "error":
      return "text-red-300 bg-red-500/15 border-red-400/30";
    case "warn":
      return "text-amber-300 bg-amber-500/15 border-amber-400/30";
    case "success":
      return "text-emerald-300 bg-emerald-500/15 border-emerald-400/30";
    case "info":
      return "text-sky-200 bg-sky-500/15 border-sky-300/30";
    default:
      return "text-slate-300 bg-white/8 border-white/20";
  }
};

const levelTextClass = (level: ParsedLogLine["level"]) => {
  switch (level) {
    case "error":
      return "text-red-300";
    case "warn":
      return "text-amber-300";
    case "success":
      return "text-emerald-300";
    case "info":
      return "text-sky-200";
    default:
      return "text-slate-200";
  }
};

const formatTimeColumn = (value: string | null) => {
  if (!value) return null;
  const d = new Date(value);
  if (!Number.isNaN(d.valueOf())) {
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    const ss = String(d.getSeconds()).padStart(2, "0");
    return `${hh}:${mm}:${ss}`;
  }
  return value.slice(11, 19) || value;
};

const renderJsonStyledLine = (input: string) => {
  const text = input.trim();
  if (!text) return null;
  const tokenRegex =
    /("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\b-?\d+(?:\.\d+)?\b|\btrue\b|\bfalse\b|\bnull\b|[{}\[\],:])/gi;
  const nodes: ReactNode[] = [];
  let last = 0;
  let match: RegExpExecArray | null;
  let idx = 0;
  while ((match = tokenRegex.exec(text)) !== null) {
    const start = match.index;
    const token = match[0];
    if (start > last) {
      nodes.push(
        <span key={`plain-${idx++}`} className="text-slate-300">
          {text.slice(last, start)}
        </span>,
      );
    }
    const end = tokenRegex.lastIndex;
    const rest = text.slice(end);
    const nextNonSpace = rest.match(/^\s*(.)/)?.[1];
    let cls = "text-slate-300";
    if (/^["']/.test(token)) {
      cls = nextNonSpace === ":" ? "text-sky-300" : "text-orange-300";
    } else if (/^-?\d/.test(token) || /^(true|false|null)$/i.test(token)) {
      cls = "text-emerald-300";
    } else if (/^[{}\[\]]$/.test(token)) {
      cls = "text-fuchsia-300";
    } else if (/^[:,]$/.test(token)) {
      cls = "text-slate-400";
    }
    nodes.push(
      <span key={`tok-${idx++}`} className={cls}>
        {token}
      </span>,
    );
    last = end;
  }
  if (last < text.length) {
    nodes.push(
      <span key={`tail-${idx++}`} className="text-slate-300">
        {text.slice(last)}
      </span>,
    );
  }
  return <>{nodes}</>;
};

function MetricCard({
  label,
  value,
  hint,
  isLoading,
}: {
  label: string;
  value: string | number;
  hint: string;
  isLoading?: boolean;
}) {
  return (
    <div className="rounded-xl border border-white/15 bg-white/[0.04] px-3 py-2.5">
      <p className="text-[11px] uppercase tracking-[0.1em] text-white/65">{label}</p>
      <p className="mt-1 text-lg font-semibold text-white">
        {isLoading ? <Loader2 size={16} className="animate-spin inline-block" /> : value}
      </p>
      <p className="text-[11px] text-white/70">{hint}</p>
    </div>
  );
}

export function OperationsView({ onOpenSourceDetails }: OperationsViewProps) {
  const [activeTab, setActiveTab] = useState<"stats" | "parsers" | "categories" | "queue" | "workers" | "scheduler">("stats");
  const [siteSearch, setSiteSearch] = useState("");
  const [categorySearch, setCategorySearch] = useState("");
  const [logsCopied, setLogsCopied] = useState(false);
  const [expandedJsonIds, setExpandedJsonIds] = useState<Record<string, boolean>>({});
  const [logSearchQuery, setLogSearchQuery] = useState("");
  const [activeLogFilter, setActiveLogFilter] = useState<LogFilter>("all");
  const [sitesVisibleCount, setSitesVisibleCount] = useState(SITES_PAGE_SIZE);
  const [runningDiscoveryBySite, setRunningDiscoveryBySite] = useState<Record<string, boolean>>({});
  const [selectedWorkerId, setSelectedWorkerId] = useState<string | null>(null);
  const [itemsTrendGranularity, setItemsTrendGranularity] = useState<"week" | "day" | "hour" | "minute">("day");
  const [tasksTrendGranularity, setTasksTrendGranularity] = useState<"week" | "day" | "hour" | "minute">("day");
  const [workerHistoryById, setWorkerHistoryById] = useState<
    Record<string, { ts: string; status: string; tasks: number; ram: number; completed: number }[]>
  >({});
  const [workerPausePendingId, setWorkerPausePendingId] = useState<string | null>(null);
  const [schedulerPausePending, setSchedulerPausePending] = useState(false);
  const { toast: showToast, dismissToast } = useNotificationCenter();
  const retryRegistry = useRetryRegistry();

  const {
    selectedSiteKey,
    setSelectedSiteKey,
    selectedRunId,
    setSelectedRunId,
    streamState,
    streamError,
    discoveryStateFilter,
    setDiscoveryStateFilter,
    discoverySearch,
    setDiscoverySearch,
    overview,
    sites,
    pipeline,
    activeRuns,
    runDetails,
    discovery,
    queuedRuns,
    completedRuns,
    errorRuns,
    schedulerStats,
    itemsTrendMap,
    tasksTrendMap,
    sources,
    promoteCategories,
    rejectCategories,
    reactivateCategories,
    bulkUpdateSources,
    retryRun,
    runSourceNow,
    runSiteDiscovery,
    anyPendingAction,
  } = useOperationsData();

  useApiErrorToast({
    id: "ops-run-details-api",
    title: "Run details API временно недоступен",
    retryKey: "ops-run-details-api",
    retryLabel: "Повторить",
    errors: [runDetails.error],
    enabled: !!selectedRunId,
    ttlMs: 10000,
  });

  const filteredSites = useMemo(() => {
    const q = siteSearch.trim().toLowerCase();
    if (!q) return sites.data?.items || [];
    return (sites.data?.items || []).filter(
      (site: any) =>
        String(site.site_key || "").toLowerCase().includes(q) ||
        String(site.name || "").toLowerCase().includes(q),
    );
  }, [siteSearch, sites.data?.items]);

  const sourcesQuery = sources;

  const categoryLimit = 200;
  const [categoryPage, setCategoryPage] = useState(0);
  const categoryQuery = useAdminRequestQuery<any>(
    "catalog.categories",
    {
      limit: categoryLimit,
      offset: categoryPage * categoryLimit,
      search: categorySearch || "",
    },
    [categoryPage, categorySearch],
  );
  const categorySources = useMemo(() => {
    const sources: any[] = Array.isArray(categoryQuery.data?.items) ? categoryQuery.data.items : [];
    return sources.map((s) => ({
      id: Number(s.id),
      site_key: String(s.site_key || ""),
      url: String(s.url || ""),
      status: String(s.status || ""),
      last_synced_at: s.last_synced_at ? String(s.last_synced_at) : null,
      next_sync_at: s.next_sync_at ? String(s.next_sync_at) : "",
      total_items: Number(s.total_items || 0),
      is_active: Boolean(s.is_active),
      config: { discovery_name: s?.config?.discovery_name ? String(s.config.discovery_name) : undefined },
    }));
  }, [categoryQuery.data]);
  const visibleSites = useMemo(
    () => filteredSites.slice(0, sitesVisibleCount),
    [filteredSites, sitesVisibleCount],
  );

  useEffect(() => {
    setSitesVisibleCount(SITES_PAGE_SIZE);
  }, [siteSearch, sites.data?.items]);

  useEffect(() => {
    const workers = overview.data?.workers?.items || [];
    if (!workers.length) return;
    const now = new Date().toISOString();
    setWorkerHistoryById((prev) => {
      const next = { ...prev };
      for (const worker of workers) {
        const workerId = String(worker.worker_id || `${worker.hostname || "worker"}:${worker.pid || "?"}`);
        const current = next[workerId] || [];
        const entry = {
          ts: now,
          status: String(worker.status || "online"),
          tasks: Number(worker.concurrent_tasks ?? 0),
          ram: Number(worker.ram_usage_pct ?? 0),
          completed: Number(worker.tasks_processed_total ?? 0),
        };
        const last = current[current.length - 1];
        if (
          !last ||
          last.status !== entry.status ||
          last.tasks !== entry.tasks ||
          Math.abs(last.ram - entry.ram) >= 1 ||
          last.completed !== entry.completed
        ) {
          next[workerId] = [...current, entry].slice(-60);
        }
      }
      return next;
    });
  }, [overview.data?.workers?.items]);

  const runItem = runDetails.data?.item;
  const itemsTrend = useMemo(() => {
    const data = itemsTrendMap.data || {};
    return { ...itemsTrendMap, data: data[itemsTrendGranularity] ?? data } as typeof itemsTrendMap;
  }, [itemsTrendMap, itemsTrendGranularity]);
  const tasksTrend = useMemo(() => {
    const data = tasksTrendMap.data || {};
    return { ...tasksTrendMap, data: data[tasksTrendGranularity] ?? data } as typeof tasksTrendMap;
  }, [tasksTrendMap, tasksTrendGranularity]);

  useEffect(() => {
    const unregisterDetails = retryRegistry.register("ops-run-details-api", async () => {
      if (!selectedRunId) return;
      await runDetails.refetch();
    });
    const unregisterOps = retryRegistry.register("ops-api-error", async () => {
      await Promise.allSettled([
        overview.refetch(),
        sites.refetch(),
        activeRuns.refetch(),
        queuedRuns.refetch(),
        completedRuns.refetch(),
        errorRuns.refetch(),
        schedulerStats.refetch(),
        itemsTrend.refetch(),
        tasksTrend.refetch(),
        selectedRunId ? runDetails.refetch() : Promise.resolve(),
      ]);
    });
    return () => {
      unregisterDetails();
      unregisterOps();
    };
  }, [
    retryRegistry,
    selectedRunId,
    overview.refetch,
    sites.refetch,
    activeRuns.refetch,
    queuedRuns.refetch,
    completedRuns.refetch,
    errorRuns.refetch,
    schedulerStats.refetch,
    itemsTrend.refetch,
    tasksTrend.refetch,
    runDetails.refetch,
  ]);
  const queuedItems = useMemo(
    () => (queuedRuns.data?.items || []),
    [queuedRuns.data?.items],
  );
  const runningItems = useMemo(
    () => (activeRuns.data?.items || []).filter((r: any) => r.status === "running"),
    [activeRuns.data?.items],
  );
  const completedItems = useMemo(
    () => (completedRuns.data?.items || []),
    [completedRuns.data?.items],
  );
  const errorItems = useMemo(
    () => (errorRuns.data?.items || []).filter((r: any) => r.status === "error"),
    [errorRuns.data?.items],
  );
  const parsedLogLines = useMemo(
    () =>
      String(runItem?.logs || "")
        .split(/\r?\n/)
        .filter((line) => line.trim().length > 0)
        .map((line, idx) => parseLogLine(line, idx)),
    [runItem?.logs],
  );
  const logItems = useMemo(() => buildLogItems(parsedLogLines), [parsedLogLines]);
  const logCounts = useMemo(() => {
    let errors = 0;
    let warnings = 0;
    let infos = 0;
    let success = 0;
    for (const line of parsedLogLines) {
      if (line.level === "error") errors += 1;
      else if (line.level === "warn") warnings += 1;
      else if (line.level === "info") infos += 1;
      else if (line.level === "success") success += 1;
    }
    return { errors, warnings, infos, success };
  }, [parsedLogLines]);
  const visibleLogItems = useMemo(() => {
    const query = logSearchQuery.trim().toLowerCase();
    return logItems.filter((item) => {
      const levels = item.kind === "line" ? [item.line.level] : item.lines.map((line) => line.level);
      const matchesFilter =
        activeLogFilter === "all" ||
        (activeLogFilter === "errors" && levels.includes("error")) ||
        (activeLogFilter === "warnings" && levels.includes("warn")) ||
        (activeLogFilter === "info" && levels.includes("info")) ||
        (activeLogFilter === "success" && levels.includes("success"));
      if (!matchesFilter) return false;

      if (!query) return true;
      const haystack =
        item.kind === "line"
          ? `${item.line.raw} ${item.line.message}`.toLowerCase()
          : `${item.summary}\n${item.payload}`.toLowerCase();
      return haystack.includes(query);
    });
  }, [logItems, activeLogFilter, logSearchQuery]);
  const copyLogs = async () => {
    const logs = String(runItem?.logs || "").trim();
    if (!logs) return;
    try {
      await navigator.clipboard.writeText(logs);
      setLogsCopied(true);
      window.setTimeout(() => setLogsCopied(false), 1200);
    } catch {
      setLogsCopied(false);
    }
  };

  const handleSitesScroll = (event: UIEvent<HTMLDivElement>) => {
    const node = event.currentTarget;
    const nearBottom = node.scrollHeight - node.scrollTop - node.clientHeight < 80;
    if (!nearBottom) return;
    if (sitesVisibleCount >= filteredSites.length) return;
    setSitesVisibleCount((prev) => Math.min(filteredSites.length, prev + SITES_PAGE_SIZE));
  };
  const handleLaneScroll = (laneKey: string) => (event: UIEvent<HTMLDivElement>) => {
    if (laneKey !== "queued") return;
    const node = event.currentTarget;
    const nearBottom = node.scrollHeight - node.scrollTop - node.clientHeight < 80;
    if (!nearBottom) return;
    if (!queuedRuns.hasNextPage || queuedRuns.isFetchingNextPage) return;
    void queuedRuns.fetchNextPage?.();
  };

  const upsertNotification = (next: { id: string; status: "running" | "success" | "error"; title: string; message: string }) => {
    showToast(
      {
        id: next.id,
        level: next.status,
        title: next.title,
        message: next.message,
        dedupeKey: next.id,
      },
      { ttlMs: next.status === "running" ? 0 : next.status === "error" ? 10000 : 6000 },
    );
  };

  const opsApiErrorSignatureRef = useRef<string | null>(null);
  const opsApiErrorSnapshot = useMemo(() => {
    const entries: { label: string; error: unknown }[] = [
      { label: "overview", error: overview.error },
      { label: "sites", error: sites.error },
      { label: "active runs", error: activeRuns.error },
      { label: "queued runs", error: queuedRuns.error },
      { label: "completed runs", error: completedRuns.error },
      { label: "error runs", error: errorRuns.error },
      { label: "scheduler", error: schedulerStats.error },
      { label: "items trend", error: itemsTrend.error },
      { label: "tasks trend", error: tasksTrend.error },
      { label: "run details", error: runDetails.error },
    ];
    const apiErrors = entries.filter((e) => isServerApiError(e.error));
    if (!apiErrors.length) return null;

    const signature = apiErrors
      .map((e) => {
        const status = getApiErrorStatus(e.error);
        const msg = getApiErrorMessage(e.error);
        return `${e.label}:${status ?? "x"}:${msg}`;
      })
      .join("|");

    const labels = apiErrors.map((e) => e.label).join(", ");
    const firstErr = apiErrors[0]!.error;
    const status = getApiErrorStatus(firstErr);
    const msg = getApiErrorMessage(firstErr);
    const messageRaw = `${labels}: ${msg}${status ? ` (HTTP ${status})` : ""}`;
    const message = messageRaw.length > 220 ? `${messageRaw.slice(0, 217)}...` : messageRaw;

    return { signature, message };
  }, [
    overview.error,
    sites.error,
    activeRuns.error,
    queuedRuns.error,
    completedRuns.error,
    errorRuns.error,
    schedulerStats.error,
    itemsTrend.error,
    tasksTrend.error,
    runDetails.error,
  ]);

  useEffect(() => {
    if (!opsApiErrorSnapshot) {
      opsApiErrorSignatureRef.current = null;
      return;
    }
    if (opsApiErrorSignatureRef.current === opsApiErrorSnapshot.signature) return;
    opsApiErrorSignatureRef.current = opsApiErrorSnapshot.signature;

    const notifId = "ops-api-error";
    showToast(
      {
        id: notifId,
        level: "error",
        title: "Operations API временно недоступен",
        message: opsApiErrorSnapshot.message,
        dedupeKey: `ops-api-error:${opsApiErrorSnapshot.signature}`,
        retryKey: "ops-api-error",
        retryLabel: "Повторить",
      },
      { ttlMs: 10000 },
    );
    window.setTimeout(() => dismissToast(notifId), 10000);
  }, [opsApiErrorSnapshot, dismissToast, showToast]);

  const handleRunDiscovery = async (site: any) => {
    const siteKey = String(site?.site_key || "");
    if (!siteKey || runningDiscoveryBySite[siteKey]) return;
    const notifId = `site-discovery-${siteKey}`;
    const beforeTotal = Number(site?.counters?.discovered_new || 0) + Number(site?.counters?.discovered_promoted || 0);
    setRunningDiscoveryBySite((prev) => ({ ...prev, [siteKey]: true }));
    upsertNotification({
      id: notifId,
      status: "running",
      title: `${site.name || siteKey} · Discovery`,
      message: "Discovery started...",
    });

    try {
      await runSiteDiscovery(siteKey);
      let finalSite: any = null;
      let finalStatus = "queued";

      for (let i = 0; i < 120; i += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 1500));
        const fresh = sites.data;
        const current = (fresh?.items || []).find((s: any) => s.site_key === siteKey);
        if (!current) continue;
        finalSite = current;
        finalStatus = String(current.status || "").toLowerCase();
        if (["error", "broken", "failed"].includes(finalStatus)) break;
        if (!["queued", "running", "processing"].includes(finalStatus)) break;
      }

      const afterTotal = finalSite
        ? Number(finalSite?.counters?.discovered_new || 0) + Number(finalSite?.counters?.discovered_promoted || 0)
        : beforeTotal;
      const foundDelta = Math.max(0, afterTotal - beforeTotal);

      if (["error", "broken", "failed"].includes(finalStatus)) {
        upsertNotification({
          id: notifId,
          status: "error",
          title: `${site.name || siteKey} · Discovery failed`,
          message: `Status: ${finalStatus}`,
        });
      } else {
        upsertNotification({
          id: notifId,
          status: "success",
          title: `${site.name || siteKey} · Discovery finished`,
          message: `Found categories: ${foundDelta}`,
        });
      }
      await Promise.allSettled([sites.refetch(), overview.refetch()]);
    } catch (error: any) {
      upsertNotification({
        id: notifId,
        status: "error",
        title: `${site.name || siteKey} · Discovery failed`,
        message: String(error?.response?.data?.detail || error?.message || "Unknown error"),
      });
    } finally {
      setRunningDiscoveryBySite((prev) => ({ ...prev, [siteKey]: false }));
      window.setTimeout(() => dismissToast(notifId), 10000);
    }
  };

  const selectedWorker = useMemo(
    () => (overview.data?.workers?.items || []).find((w: any) => String(w.worker_id || `${w.hostname || "worker"}:${w.pid || "?"}`) === selectedWorkerId) || null,
    [overview.data?.workers?.items, selectedWorkerId],
  );
  const selectedWorkerHistory = selectedWorkerId ? (workerHistoryById[selectedWorkerId] || []) : [];
  const selectedWorkerCreatedAt = useMemo(() => {
    if (selectedWorker?.started_at) return String(selectedWorker.started_at);
    if (selectedWorker?.created_at) return String(selectedWorker.created_at);
    if (selectedWorkerHistory.length) return selectedWorkerHistory[0]?.ts || null;
    return null;
  }, [selectedWorker?.started_at, selectedWorker?.created_at, selectedWorkerHistory]);
  const selectedWorkerStats = useMemo(() => {
    if (!selectedWorkerHistory.length) {
      return {
        heartbeats: 0,
        busySnapshots: 0,
        idleSnapshots: 0,
        avgRam: 0,
        completedTasks: Number(selectedWorker?.tasks_processed_total || 0),
      };
    }
    const heartbeats = selectedWorkerHistory.length;
    const busySnapshots = selectedWorkerHistory.filter((h) => h.tasks > 0).length;
    const idleSnapshots = heartbeats - busySnapshots;
    const avgRam = Math.round(selectedWorkerHistory.reduce((acc, h) => acc + h.ram, 0) / heartbeats);
    const completedTasks = Number(selectedWorker?.tasks_processed_total || 0);
    return { heartbeats, busySnapshots, idleSnapshots, avgRam, completedTasks };
  }, [selectedWorkerHistory, selectedWorker?.tasks_processed_total]);

  const handleToggleWorkerPause = async () => {
    const workerId = selectedWorkerId;
    if (!workerId || workerPausePendingId) return;
    const paused = Boolean(selectedWorker?.paused || selectedWorker?.status === "paused");
    const notifId = `worker-pause-${workerId}`;
    setWorkerPausePendingId(workerId);
    upsertNotification({
      id: notifId,
      status: "running",
      title: paused ? "Resuming worker" : "Pausing worker",
      message: workerId,
    });
    try {
      if (paused) {
        await resumeOpsWorker(workerId);
      } else {
        await pauseOpsWorker(workerId);
      }
      upsertNotification({
        id: notifId,
        status: "success",
        title: paused ? "Worker resumed" : "Worker paused",
        message: workerId,
      });
      await overview.refetch();
    } catch (error: any) {
      upsertNotification({
        id: notifId,
        status: "error",
        title: "Worker control failed",
        message: String(error?.response?.data?.detail || error?.message || "Unknown error"),
      });
    } finally {
      setWorkerPausePendingId(null);
      window.setTimeout(() => dismissToast(notifId), 6000);
    }
  };

  const handleToggleSchedulerPause = async () => {
    if (schedulerPausePending) return;
    const paused = Boolean(schedulerStats.data?.summary?.scheduler_paused);
    const notifId = "scheduler-pause-toggle";
    setSchedulerPausePending(true);
    upsertNotification({
      id: notifId,
      status: "running",
      title: paused ? "Resuming scheduler" : "Pausing scheduler",
      message: "Applying state...",
    });
    try {
      if (paused) {
        await resumeOpsScheduler();
      } else {
        await pauseOpsScheduler();
      }
      upsertNotification({
        id: notifId,
        status: "success",
        title: paused ? "Scheduler resumed" : "Scheduler paused",
        message: paused ? "New tasks will be scheduled again." : "New tasks are not being scheduled now.",
      });
      await schedulerStats.refetch();
    } catch (error: any) {
      upsertNotification({
        id: notifId,
        status: "error",
        title: "Scheduler control failed",
        message: String(error?.response?.data?.detail || error?.message || "Unknown error"),
      });
    } finally {
      setSchedulerPausePending(false);
      window.setTimeout(() => dismissToast(notifId), 6000);
    }
  };

  const isInitialMainPanelLoading =
    (overview.isLoading || itemsTrend.isLoading || tasksTrend.isLoading) &&
    !overview.data &&
    !itemsTrend.data &&
    !tasksTrend.data &&
    !overview.error &&
    !itemsTrend.error &&
    !tasksTrend.error;

  if (isInitialMainPanelLoading) {
    return (
      <div className="px-3 py-4 md:px-4">
        <div className="rounded-3xl border border-white/12 bg-white/[0.03] min-h-[52vh] flex items-center justify-center">
          <Loader2 className="animate-spin text-[var(--tg-theme-button-color)]" size={34} />
        </div>
      </div>
    );
  }

  return (
    <div className="px-3 py-4 md:px-4" data-testid="ops-view">
      <div className="rounded-3xl border border-white/12 bg-white/[0.03] p-4 md:p-5 space-y-4" data-testid="ops-card">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="inline-flex items-center gap-2 rounded-xl border border-white/20 bg-white/10 px-3 py-2 text-sm font-semibold text-white">
              <Activity size={16} />
              Operations Center
            </div>
            <div
              className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs ${
                streamState === "connected"
                  ? "border-emerald-300/35 bg-emerald-400/10 text-emerald-100"
                  : streamState === "connecting"
                    ? "border-amber-300/35 bg-amber-400/10 text-amber-100"
                    : "border-rose-300/35 bg-rose-400/10 text-rose-100"
              }`}
              data-testid="ops-stream-state"
            >
              {streamState === "connected" ? <CheckCircle2 size={14} /> : streamState === "connecting" ? <Loader2 size={14} className="animate-spin" /> : <ShieldAlert size={14} />}
              {streamState === "connected" ? "Live connected" : streamState === "connecting" ? "Connecting" : "Disconnected"}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              className="inline-flex items-center gap-1.5 rounded-xl border border-white/12 bg-black/20 px-3 py-2 text-xs font-semibold text-white/85 hover:bg-white/10 active:scale-95 transition-all"
              onClick={() => openGrafanaExploreLoki('{service="api"}')}
              title="Open API logs in Grafana (Loki)"
            >
              <ExternalLink size={14} />
              Grafana logs
            </button>
            <button
              className="inline-flex items-center gap-1.5 rounded-xl border border-white/12 bg-black/20 px-3 py-2 text-xs font-semibold text-white/85 hover:bg-white/10 active:scale-95 transition-all"
              onClick={() => openGrafanaExplorePrometheus()}
              title="Open metrics in Grafana (Prometheus)"
            >
              <ExternalLink size={14} />
              Grafana metrics
            </button>
            {streamError ? <span className="text-xs text-rose-200">{streamError}</span> : null}
          </div>
        </div>

        <div className="flex flex-wrap gap-2" data-testid="ops-tabs">
          {([
            { key: "stats", label: "Stats" },
            { key: "parsers", label: "Parsers" },
            { key: "categories", label: "Categories" },
            { key: "queue", label: "Queue" },
            { key: "workers", label: "Workers" },
            { key: "scheduler", label: "Scheduler" },
          ] as { key: "stats" | "parsers" | "categories" | "queue" | "workers" | "scheduler"; label: string }[]).map((tab) => (
            <button
              key={tab.key}
              className={`rounded-lg border px-3 py-1.5 text-xs transition ${
                activeTab === tab.key
                  ? "border-sky-300/55 bg-sky-500/20 text-sky-100"
                  : "border-white/20 bg-black/20 text-white/80 hover:bg-white/10"
              }`}
              onClick={() => setActiveTab(tab.key)}
              data-testid={`ops-tab-${tab.key}`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === "stats" ? (
        <div className="space-y-3" data-testid="ops-stats">
          <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-xl border border-white/15 bg-white/[0.04] px-3 py-2.5 sm:col-span-2" data-testid="ops-task-states">
              <p className="text-[11px] uppercase tracking-[0.1em] text-white/65">Task states</p>
              <div className="mt-1 grid grid-cols-2 gap-2 text-[12px]">
                <div className="rounded-md border border-sky-400/30 bg-sky-500/10 px-2 py-1.5">
                  <p className="text-white/70">Running</p>
                  <p className="text-lg font-semibold text-white">
                    {overview.isLoading ? <Loader2 size={14} className="animate-spin inline-block" /> : Number(overview.data?.runs?.running ?? 0)}
                  </p>
                </div>
                <div className="rounded-md border border-amber-400/30 bg-amber-500/10 px-2 py-1.5">
                  <p className="text-white/70">Queue</p>
                  <p className="text-lg font-semibold text-white">
                    {overview.isLoading ? <Loader2 size={14} className="animate-spin inline-block" /> : Number(overview.data?.queue?.messages_total ?? 0)}
                  </p>
                </div>
                <div className="rounded-md border border-emerald-400/30 bg-emerald-500/10 px-2 py-1.5">
                  <p className="text-white/70">Successful</p>
                  <p className="text-lg font-semibold text-white">
                    {overview.isLoading ? <Loader2 size={14} className="animate-spin inline-block" /> : Number(overview.data?.runs?.completed ?? 0)}
                  </p>
                </div>
                <div className="rounded-md border border-rose-400/30 bg-rose-500/10 px-2 py-1.5">
                  <p className="text-white/70">Error</p>
                  <p className="text-lg font-semibold text-white">
                    {overview.isLoading ? <Loader2 size={14} className="animate-spin inline-block" /> : Number(overview.data?.runs?.error ?? 0)}
                  </p>
                </div>
              </div>
              <p className="mt-1 text-[11px] text-white/70">
                ready {overview.data?.queue?.messages_ready ?? 0}, unacked {overview.data?.queue?.messages_unacknowledged ?? 0}
              </p>
            </div>
            <MetricCard
              label="Workers"
              value={overview.data?.workers?.online ?? 0}
              hint="Active worker heartbeat"
              isLoading={overview.isLoading}
            />
            <MetricCard
              label="Discovery Categories"
              value={overview.data?.discovery_categories?.new ?? overview.data?.discovery?.new ?? 0}
              hint={`new categories (approved ${overview.data?.discovery_categories?.promoted ?? overview.data?.discovery?.promoted ?? 0})`}
              isLoading={overview.isLoading}
            />
            <MetricCard
              label="Discovery Products"
              value={overview.data?.discovery_products?.total ?? 0}
              hint={`global catalog total (window new: ${itemsTrend.data?.totals?.items_new ?? 0})`}
              isLoading={overview.isLoading}
            />
          </div>

          <section className="rounded-2xl border border-white/12 bg-white/[0.02] p-3" data-testid="ops-items-trend">
            <div className="mb-2 flex items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-white">Daily New Products</h3>
              <span className="text-[11px] text-white/70">
                total new products: {itemsTrend.data?.totals?.items_new ?? 0}, new categories: {itemsTrend.data?.totals?.categories_new ?? 0}
              </span>
            </div>
            <div className="mb-2 flex flex-wrap gap-1.5">
              {([
                { key: "week", label: "Weeks" },
                { key: "day", label: "Days" },
                { key: "hour", label: "Hours" },
                { key: "minute", label: "Minutes" },
              ] as { key: "week" | "day" | "hour" | "minute"; label: string }[]).map((g) => (
                <button
                  key={g.key}
                  className={`rounded-md border px-2 py-1 text-[11px] transition ${
                    itemsTrendGranularity === g.key
                      ? "border-sky-300/55 bg-sky-500/25 text-sky-100"
                      : "border-white/20 bg-white/5 text-white/80 hover:bg-white/10"
                  }`}
                  onClick={() => setItemsTrendGranularity(g.key)}
                >
                  {g.label}
                </button>
              ))}
            </div>
            <div className="h-56 rounded-xl border border-white/12 bg-black/20 p-2" data-testid="ops-items-trend-chart">
              {itemsTrend.isLoading ? (
                <div className="flex h-full items-center justify-center text-sm text-white/75">
                  <Loader2 size={16} className="mr-2 animate-spin" />
                  Loading trend...
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={itemsTrend.data?.items || []} margin={{ top: 8, right: 8, left: -20, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.12)" />
                    <XAxis
                      dataKey="date"
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: "#b6c5dd", fontSize: 11 }}
                      tickFormatter={(v) => formatTrendLabel(String(v), itemsTrendGranularity)}
                    />
                    <YAxis axisLine={false} tickLine={false} tick={{ fill: "#b6c5dd", fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#0f172a",
                        border: "1px solid rgba(255,255,255,0.12)",
                        borderRadius: 10,
                        fontSize: 12,
                      }}
                      labelFormatter={(v) => formatTrendLabel(String(v), itemsTrendGranularity)}
                    />
                    <Line type="monotone" dataKey="items_new" stroke="#34d399" strokeWidth={2.5} dot={false} name="new products" />
                    <Line type="monotone" dataKey="categories_new" stroke="#f59e0b" strokeWidth={2} dot={false} name="new categories" />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </section>

          <section className="rounded-2xl border border-white/12 bg-white/[0.02] p-3" data-testid="ops-tasks-trend">
            <div className="mb-2 flex items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-white">Task States Trend</h3>
              <span className="text-[11px] text-white/70">
                max queue: {tasksTrend.data?.totals?.queue_max ?? 0}, max running: {tasksTrend.data?.totals?.running_max ?? 0}, success: {tasksTrend.data?.totals?.success ?? 0}, error: {tasksTrend.data?.totals?.error ?? 0}
              </span>
            </div>
            <div className="mb-2 flex flex-wrap gap-1.5">
              {([
                { key: "week", label: "Weeks" },
                { key: "day", label: "Days" },
                { key: "hour", label: "Hours" },
                { key: "minute", label: "Minutes" },
              ] as { key: "week" | "day" | "hour" | "minute"; label: string }[]).map((g) => (
                <button
                  key={`tasks-${g.key}`}
                  className={`rounded-md border px-2 py-1 text-[11px] transition ${
                    tasksTrendGranularity === g.key
                      ? "border-sky-300/55 bg-sky-500/25 text-sky-100"
                      : "border-white/20 bg-white/5 text-white/80 hover:bg-white/10"
                  }`}
                  onClick={() => setTasksTrendGranularity(g.key)}
                >
                  {g.label}
                </button>
              ))}
            </div>
            <div className="h-56 rounded-xl border border-white/12 bg-black/20 p-2" data-testid="ops-tasks-trend-chart">
              {tasksTrend.isLoading ? (
                <div className="flex h-full items-center justify-center text-sm text-white/75">
                  <Loader2 size={16} className="mr-2 animate-spin" />
                  Loading task trend...
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={tasksTrend.data?.items || []} margin={{ top: 8, right: 8, left: -20, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.12)" />
                    <XAxis
                      dataKey="date"
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: "#b6c5dd", fontSize: 11 }}
                      tickFormatter={(v) => formatTrendLabel(String(v), tasksTrendGranularity)}
                    />
                    <YAxis axisLine={false} tickLine={false} tick={{ fill: "#b6c5dd", fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#0f172a",
                        border: "1px solid rgba(255,255,255,0.12)",
                        borderRadius: 10,
                        fontSize: 12,
                      }}
                      labelFormatter={(v) => formatTrendLabel(String(v), tasksTrendGranularity)}
                    />
                    <Line type="monotone" dataKey="running" stroke="#38bdf8" strokeWidth={2.3} dot={false} name="running" />
                    <Line type="monotone" dataKey="queue" stroke="#f59e0b" strokeWidth={2.3} dot={false} name="queue" />
                    <Line type="monotone" dataKey="success" stroke="#34d399" strokeWidth={2.3} dot={false} name="success" />
                    <Line type="monotone" dataKey="error" stroke="#fb7185" strokeWidth={2.3} dot={false} name="error" />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </section>
        </div>
        ) : null}

        {activeTab === "workers" ? (
        <section className="rounded-2xl border border-white/12 bg-white/[0.02] p-3" data-testid="ops-workers">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-white">Workers Activity</h3>
            <span className="text-xs text-white/75">{overview.data?.workers?.items?.length || 0} workers</span>
          </div>
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {(overview.data?.workers?.items || []).map((worker: any) => {
              const workerId = String(worker.worker_id || `${worker.hostname || "worker"}:${worker.pid || "?"}`);
              const activeTasks = Array.isArray(worker.active_tasks) ? worker.active_tasks : [];
              const history = workerHistoryById[workerId] || [];
              return (
                <button
                  key={workerId}
                  className="rounded-xl border border-white/12 bg-black/20 p-2.5 text-left hover:border-sky-300/45 transition"
                  onClick={() => setSelectedWorkerId(workerId)}
                  data-testid={`ops-worker-${workerId}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-white truncate">{workerId}</p>
                    <span className={`text-[10px] rounded-full border px-2 py-0.5 ${statusBadgeClass(worker.status)}`}>{worker.status || "online"}</span>
                  </div>
                  <div className="mt-1 grid grid-cols-2 gap-1 text-[11px] text-white/80">
                    <span>tasks: {worker.concurrent_tasks ?? 0}</span>
                    <span>RAM: {worker.ram_usage_pct ?? 0}%</span>
                    <span className="col-span-2">completed: {Number(worker.tasks_processed_total || 0)}</span>
                  </div>
                  <div className="mt-1 text-[10px] text-white/65">history points: {history.length}</div>
                  <div className="mt-2 space-y-1">
                    {activeTasks.length ? (
                      activeTasks.map((task: any, idx: number) => (
                        <div key={`${workerId}-task-${idx}`} className="rounded-md border border-sky-400/25 bg-sky-500/10 px-2 py-1.5">
                          <p className="text-[11px] font-medium text-sky-100">
                            {task.site_key || "unknown"} · source #{task.source_id ?? "?"}
                          </p>
                          <p className="text-[10px] text-sky-100/80">
                            run #{task.run_id ?? "?"} · {task.strategy || "deep"}
                          </p>
                          {task.url ? <p className="text-[10px] text-sky-100/70 truncate">{task.url}</p> : null}
                        </div>
                      ))
                    ) : (
                      <div className="rounded-md border border-dashed border-white/20 px-2 py-1.5 text-[11px] text-white/65">
                        Idle
                      </div>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
          {!overview.data?.workers?.items?.length ? (
            <div className="mt-2 text-xs text-white/70">No active worker heartbeat.</div>
          ) : null}
        </section>
        ) : null}

        {activeTab === "parsers" ? (
        <section className="rounded-2xl border border-white/12 bg-white/[0.02] p-3" data-testid="ops-parsers">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-white">Parsers</h3>
            <span className="text-sm text-white/80">{filteredSites.length}</span>
          </div>
          <input
            value={siteSearch}
            onChange={(event) => setSiteSearch(event.target.value)}
            placeholder="Search site"
            className="mb-2 h-9 w-full rounded-lg border border-white/20 bg-black/20 px-2.5 text-sm text-white placeholder:text-white/45 outline-none"
            data-testid="ops-parsers-search"
          />
          <div className="max-h-[54rem] overflow-y-auto pr-1" onScroll={handleSitesScroll}>
            <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {visibleSites.map((site: any) => (
              <div
                key={site.site_key}
                role="button"
                tabIndex={0}
                className={`rounded-xl border p-2.5 text-left transition cursor-pointer focus:outline-none focus:ring-2 focus:ring-sky-300/40 ${
                  selectedSiteKey === site.site_key ? "border-sky-300/55 bg-sky-500/20" : "border-white/15 bg-black/20 hover:border-white/35"
                }`}
                onClick={() => {
                  setSelectedSiteKey(site.site_key);
                }}
                onKeyDown={(event) => {
                  if (event.key !== "Enter" && event.key !== " ") return;
                  event.preventDefault();
                  setSelectedSiteKey(site.site_key);
                }}
                data-testid={`ops-parser-${site.site_key}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-lg leading-none text-white">{site.name || site.site_key}</span>
                  <span className={`text-[11px] rounded-full border px-2 py-0.5 ${statusBadgeClass(site.status)}`}>{site.status || "unknown"}</span>
                </div>
                <p className="mt-1 truncate text-[12px] text-white/75">{site.site_key}</p>
                <p className="mt-1 truncate text-[12px] text-white/85">{site.url || "URL not set"}</p>
                {isPlaceholderUrl(site.url) ? (
                  <div className="mt-1 inline-flex items-center rounded-md border border-amber-400/45 bg-amber-500/15 px-2 py-0.5 text-[10px] text-amber-200">
                    Placeholder URL. Configure real domain before production runs.
                  </div>
                ) : null}
                <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-[12px] text-white/80">
                  <span title="Все обнаруженные категории для этого парсера">Categories: {site.counters?.discovered_total ?? ((site.counters?.discovered_new || 0) + (site.counters?.discovered_promoted || 0) + (site.counters?.discovered_rejected || 0) + (site.counters?.discovered_inactive || 0))}</span>
                  <span title="Категории одобрены (promoted) для runtime">Approved: {site.counters?.discovered_promoted || 0}</span>
                  <span title="Все товары этого парсера в базе">Products: {site.counters?.products_total || 0}</span>
                  <span title="Задачи стоят в очереди и ждут воркер">In queue: {site.counters?.queued || 0}</span>
                  <span title="Задачи сейчас выполняются воркерами">Running now: {site.counters?.running || 0}</span>
                </div>
                <div className="mt-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      className="rounded-md border border-sky-400/45 bg-sky-500/15 px-2 py-1 text-[11px] text-sky-100 disabled:opacity-50"
                      disabled={!site.runtime_hub_source_id}
                      title={site.runtime_hub_source_id ? "Open parser details" : "Hub source is not created yet"}
                      onClick={(event) => {
                        event.preventDefault();
                        event.stopPropagation();
                        if (!site.runtime_hub_source_id) return;
                        onOpenSourceDetails(site.runtime_hub_source_id, {
                          name: site.name || site.site_key,
                          slug: site.site_key,
                          url: site.url || "",
                        });
                      }}
                    >
                      Open parser card
                    </button>
                    <button
                      className="inline-flex items-center gap-1 rounded-md border border-emerald-400/45 bg-emerald-500/15 px-2 py-1 text-[11px] text-emerald-100 disabled:opacity-50"
                      disabled={!!runningDiscoveryBySite[site.site_key]}
                      onClick={(event) => {
                        event.preventDefault();
                        event.stopPropagation();
                        void handleRunDiscovery(site);
                      }}
                    >
                      {runningDiscoveryBySite[site.site_key] ? <Loader2 size={12} className="animate-spin" /> : <RefreshCcw size={12} />}
                      Run discovery
                    </button>
                  </div>
                </div>
                {selectedSiteKey === site.site_key ? (
                  <div
                    className="mt-3 rounded-lg border border-dashed border-white/20 bg-black/20 px-2.5 py-2 text-[11px] text-white/70"
                    onClick={(event) => event.stopPropagation()}
                    onKeyDown={(event) => event.stopPropagation()}
                  >
                    Categories and category pipeline are available only inside <span className="text-white/90">Open parser card</span>.
                  </div>
                ) : null}
              </div>
            ))}
            </div>
          </div>
          {sitesVisibleCount < filteredSites.length ? (
            <div className="mt-2 text-[11px] text-white/65">
              Showing {visibleSites.length} of {filteredSites.length}. Scroll to load more.
            </div>
          ) : null}
          {!filteredSites.length ? <div className="mt-2 text-sm text-white/70">No sites matched search.</div> : null}
        </section>
        ) : null}

        {activeTab === "categories" ? (
        <section className="rounded-2xl border border-white/12 bg-white/[0.02] p-3" data-testid="ops-categories">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-semibold text-white">Categories</h3>
              <p className="text-[11px] text-white/70">All list sources (type=list) across all sites.</p>
            </div>
            <div className="flex items-center gap-2">
              <input
                value={categorySearch}
                onChange={(event) => {
                  setCategorySearch(event.target.value);
                  setCategoryPage(0);
                }}
                placeholder="Search site / category / url"
                className="h-9 w-[280px] max-w-[70vw] rounded-lg border border-white/20 bg-black/20 px-2.5 text-sm text-white placeholder:text-white/45 outline-none"
                data-testid="ops-categories-search"
              />
              <div className="flex items-center gap-1 text-[11px] text-white/70">
                <button
                  className="h-9 px-2 rounded-md border border-white/10 bg-white/5 disabled:opacity-40"
                  onClick={() => setCategoryPage((p) => Math.max(0, p - 1))}
                  disabled={categoryPage === 0}
                  data-testid="ops-categories-prev"
                >
                  Prev
                </button>
                <button
                  className="h-9 px-2 rounded-md border border-white/10 bg-white/5 disabled:opacity-40"
                  onClick={() => setCategoryPage((p) => p + 1)}
                  disabled={(categoryQuery.data?.total ?? 0) <= (categoryPage + 1) * categoryLimit}
                  data-testid="ops-categories-next"
                >
                  Next
                </button>
              </div>
            </div>
          </div>

          {categoryQuery.isLoading ? (
            <div className="rounded-xl border border-white/12 bg-white/[0.03] min-h-[42vh] flex items-center justify-center">
              <Loader2 className="animate-spin text-[var(--tg-theme-button-color)]" size={28} />
            </div>
          ) : categoryQuery.error ? (
            <div className="rounded-xl border border-rose-400/30 bg-rose-500/10 p-3 text-xs text-rose-100">
              Failed to load sources: {getApiErrorMessage(categoryQuery.error)}
            </div>
          ) : (
            <CategoriesTable
              sources={categorySources}
              onOpenDetail={(id) => onOpenSourceDetails(id)}
              onOpenChart={(id) => onOpenSourceDetails(id)}
            />
          )}
        </section>
        ) : null}

        {activeTab === "queue" ? (
        <section className="rounded-2xl border border-white/12 bg-white/[0.02] p-3" data-testid="ops-queue">
          <h3 className="text-sm font-semibold text-white">Queue Board</h3>
          <div className="mt-2 grid gap-2 md:grid-cols-2">
            {([
              {
                key: "queued",
                title: "Queued",
                items: queuedItems,
                total: Number(queuedRuns.data?.total ?? overview.data?.queue?.messages_total ?? queuedItems.length),
              },
              { key: "running", title: "Running", items: runningItems, total: runningItems.length },
              {
                key: "completed",
                title: "Completed",
                items: completedItems,
                total: Number(completedRuns.data?.total ?? completedItems.length),
              },
              { key: "error", title: "Error", items: errorItems, total: Number(errorRuns.data?.total ?? errorItems.length) },
            ] as { key: string; title: string; items: any[]; total: number }[]).map((lane) => (
              <div key={lane.key} className="rounded-lg border border-white/12 bg-black/20 p-2" data-testid={`ops-queue-lane-${lane.key}`}>
                <div className="mb-2 flex items-center justify-between">
                  <h4 className="text-xs uppercase tracking-[0.08em] text-white/80">{lane.title}</h4>
                  <span className="text-[10px] text-white/70">{lane.total}</span>
                </div>
                <div className="max-h-64 overflow-y-auto space-y-1.5 pr-1" onScroll={handleLaneScroll(lane.key)}>
                  {lane.items.map((run: any, idx: number) => {
                    const runId = run.run_id || run.id;
                    const sourceLabel = run.source_name || run.source_url || run.site_key || "-";
                    const categoryLabel = typeof run.category_name === "string" && run.category_name.trim() ? run.category_name.trim() : null;
                    const runTitle = getRunDisplayTitle(runId, idx);
                    return (
                      <button
                        key={`${lane.key}-${runId}-${idx}`}
                        className={`w-full rounded-md border p-2 text-left ${selectedRunId === runId ? "border-sky-300/45 bg-sky-500/10" : "border-white/12 bg-white/[0.02]"}`}
                        onClick={() => {
                          if (!runId) return;
                          setSelectedRunId(runId);
                        }}
                        data-testid={`ops-queue-item-${lane.key}-${runId}`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-sm font-medium text-white truncate">{runTitle}</span>
                          <span className={`rounded-full border px-1.5 py-0.5 text-[10px] ${statusBadgeClass(run.status)}`}>{run.status}</span>
                        </div>
                        <p className="mt-1 truncate text-[11px] text-white/75">
                          {categoryLabel ? `category: ${categoryLabel}` : sourceLabel}
                        </p>
                        {categoryLabel ? <p className="truncate text-[10px] text-white/60">{sourceLabel}</p> : null}
                        <p className="mt-1 text-[11px] text-white/70">
                          products: {Number(run.items_scraped || 0)} · categories: {Number(run.categories_scraped || 0)}
                        </p>
                        {run.updated_at ? <p className="text-[10px] text-white/60 mt-0.5">{formatDateTime(run.updated_at)}</p> : null}
                      </button>
                    );
                  })}
                  {!lane.items.length ? <div className="rounded-md border border-dashed border-white/20 p-2 text-xs text-white/70">No items</div> : null}
                  {lane.key === "queued" && queuedRuns.isFetchingNextPage ? (
                    <div className="rounded-md border border-white/12 bg-white/[0.03] p-2 text-xs text-white/75 inline-flex items-center gap-2">
                      <Loader2 size={12} className="animate-spin" />
                      Loading more queued tasks...
                    </div>
                  ) : null}
                  {lane.key === "completed" && completedRuns.isFetchingNextPage ? (
                    <div className="rounded-md border border-white/12 bg-white/[0.03] p-2 text-xs text-white/75 inline-flex items-center gap-2">
                      <Loader2 size={12} className="animate-spin" />
                      Loading more completed runs...
                    </div>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </section>
        ) : null}

        {activeTab === "scheduler" ? (
        <section className="rounded-2xl border border-white/12 bg-white/[0.02] p-3" data-testid="ops-scheduler">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-white">Scheduler Analytics</h3>
            <button
              className={`inline-flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-xs font-medium disabled:opacity-50 ${
                schedulerStats.data?.summary?.scheduler_paused
                  ? "border-emerald-400/45 bg-emerald-500/20 text-emerald-100"
                  : "border-amber-400/45 bg-amber-500/20 text-amber-100"
              }`}
              disabled={schedulerPausePending}
              onClick={() => void handleToggleSchedulerPause()}
              data-testid="ops-scheduler-toggle"
            >
              {schedulerPausePending ? <Loader2 size={13} className="animate-spin" /> : null}
              {schedulerStats.data?.summary?.scheduler_paused ? "Resume scheduler" : "Pause scheduler"}
            </button>
          </div>
          <div className="mt-2 grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
            <MetricCard
              label="Active sources"
              value={schedulerStats.data?.summary?.active_sources ?? 0}
              hint="Participating in schedule"
              isLoading={schedulerStats.isLoading}
            />
            <MetricCard
              label="Due now"
              value={schedulerStats.data?.summary?.due_now ?? 0}
              hint="Should be scheduled now"
              isLoading={schedulerStats.isLoading}
            />
            <MetricCard
              label="Overdue 15m"
              value={schedulerStats.data?.summary?.overdue_15m ?? 0}
              hint="Potential scheduler lag"
              isLoading={schedulerStats.isLoading}
            />
            <MetricCard
              label="Next hour"
              value={schedulerStats.data?.summary?.scheduled_next_hour ?? 0}
              hint="Upcoming by schedule"
              isLoading={schedulerStats.isLoading}
            />
            <MetricCard
              label="Scheduler state"
              value={schedulerStats.data?.summary?.scheduler_paused ? "Paused" : "Running"}
              hint={`disabled sources ${schedulerStats.data?.summary?.paused_sources ?? 0}`}
              isLoading={schedulerStats.isLoading}
            />
          </div>

          <div className="mt-3 grid gap-2 xl:grid-cols-2">
            <div className="rounded-lg border border-white/12 bg-black/20 p-2.5">
              <div className="mb-2 flex items-center justify-between">
                <h4 className="text-xs uppercase tracking-[0.08em] text-white/80">Interval distribution</h4>
                <span className="text-[10px] text-white/70">top 8</span>
              </div>
              <div className="space-y-1.5">
                {(schedulerStats.data?.intervals || []).map((row: any) => (
                  <div key={`int-${row.refresh_interval_hours}`} className="rounded-md border border-white/12 bg-white/[0.02] px-2 py-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-white/85">{row.refresh_interval_hours}h</span>
                      <span className="text-white/70">{row.sources_count} sources</span>
                    </div>
                  </div>
                ))}
                {!(schedulerStats.data?.intervals || []).length ? (
                  <div className="rounded-md border border-dashed border-white/20 p-2 text-xs text-white/70">No data</div>
                ) : null}
              </div>
            </div>

            <div className="rounded-lg border border-white/12 bg-black/20 p-2.5">
              <div className="mb-2 flex items-center justify-between">
                <h4 className="text-xs uppercase tracking-[0.08em] text-white/80">Last 24h runs</h4>
                <span className="text-[10px] text-white/70">completed/error</span>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                <div className="rounded-md border border-emerald-400/25 bg-emerald-500/10 p-2">
                  <p className="text-[11px] text-emerald-100">Completed</p>
                  <p className="text-lg font-semibold text-white">{schedulerStats.data?.runs_24h?.completed?.count ?? 0}</p>
                  <p className="text-[11px] text-white/70">new {schedulerStats.data?.runs_24h?.completed?.items_new ?? 0}</p>
                </div>
                <div className="rounded-md border border-rose-400/25 bg-rose-500/10 p-2">
                  <p className="text-[11px] text-rose-100">Error</p>
                  <p className="text-lg font-semibold text-white">{schedulerStats.data?.runs_24h?.error?.count ?? 0}</p>
                  <p className="text-[11px] text-white/70">new {schedulerStats.data?.runs_24h?.error?.items_new ?? 0}</p>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-3 rounded-lg border border-white/12 bg-black/20 p-2.5" data-testid="ops-scheduler-queue-trend">
            <div className="mb-2 flex items-center justify-between">
              <h4 className="text-xs uppercase tracking-[0.08em] text-white/80">Queue vs Planned Trend</h4>
              <span className="text-[10px] text-white/70">past queued / future planned</span>
            </div>
            <div className="h-56 rounded-md border border-white/12 bg-[#081120] p-2">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={schedulerStats.data?.queue_plan_trend || []} margin={{ top: 8, right: 8, left: -20, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.12)" />
                  <XAxis
                    dataKey="date"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: "#b6c5dd", fontSize: 11 }}
                    tickFormatter={(v) => formatDayLabel(String(v))}
                  />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: "#b6c5dd", fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#0f172a",
                      border: "1px solid rgba(255,255,255,0.12)",
                      borderRadius: 10,
                      fontSize: 12,
                    }}
                    labelFormatter={(v) => formatDayLabel(String(v))}
                  />
                  <Line type="monotone" dataKey="queued_actual" stroke="#38bdf8" strokeWidth={2.5} dot={false} name="queued (actual)" />
                  <Line type="monotone" dataKey="planned_future" stroke="#f59e0b" strokeWidth={2.2} dot={false} name="planned (future)" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="mt-3 rounded-lg border border-white/12 bg-black/20 p-2.5">
            <div className="mb-2 flex items-center justify-between">
              <h4 className="text-xs uppercase tracking-[0.08em] text-white/80">Upcoming scheduled runs</h4>
              <span className="text-[10px] text-white/70">next 30</span>
            </div>
            <div className="max-h-72 overflow-y-auto space-y-1.5 pr-1">
              {(schedulerStats.data?.upcoming || []).map((row: any) => (
                <div key={`up-${row.source_id}`} className="rounded-md border border-white/12 bg-white/[0.02] px-2 py-1.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-medium text-white truncate">{row.site_key} · source #{row.source_id}</span>
                    <span className={`rounded-full border px-1.5 py-0.5 text-[10px] ${statusBadgeClass(row.status)}`}>{row.status}</span>
                  </div>
                  <p className="mt-1 truncate text-[11px] text-white/75">{row.url}</p>
                  <div className="mt-1 grid grid-cols-2 gap-2 text-[11px] text-white/70">
                    <span>next: {formatDateTime(row.next_sync_at)}</span>
                    <span className="text-right">interval: {row.refresh_interval_hours}h · prio: {row.priority}</span>
                  </div>
                </div>
              ))}
              {!(schedulerStats.data?.upcoming || []).length ? (
                <div className="rounded-md border border-dashed border-white/20 p-2 text-xs text-white/70">No upcoming sources</div>
              ) : null}
            </div>
          </div>
        </section>
        ) : null}

      </div>
      {selectedRunId ? (
        <div className="fixed inset-0 z-[86] flex items-end sm:items-center justify-center bg-black/65 p-2 sm:p-4">
          <div className="w-full max-w-5xl rounded-2xl border border-white/20 bg-[#0a1322] shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between border-b border-white/12 px-4 py-3">
              <div>
                <h3 className="text-lg font-semibold text-white">Run Details</h3>
                <p className="text-xs text-white/70">{getRunDisplayTitle(runItem?.run_id ?? selectedRunId, 0)}</p>
              </div>
              <button
                className="rounded-lg border border-white/25 px-2 py-1 text-xs text-white/85 hover:bg-white/10"
                onClick={() => setSelectedRunId(null)}
              >
                Close
              </button>
            </div>
            <div className="max-h-[82vh] overflow-y-auto p-4">
              <div className="mt-2 rounded-xl border border-white/12 bg-black/25 p-3 min-h-[320px]">
                {runDetails.isLoading ? (
                  <div className="flex items-center justify-center py-12 text-white/80 text-sm">
                    <Loader2 size={16} className="animate-spin mr-2" />
                    Loading run details...
                  </div>
                ) : runItem ? (
                  <>
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h4 className="text-base font-semibold text-white">{getRunDisplayTitle(runItem.run_id, 0)}</h4>
                        <p className="text-[12px] text-white/75 mt-0.5">{runItem.category_name ? `category: ${runItem.category_name}` : (runItem.source_name || runItem.source_url)}</p>
                        {runItem.category_name ? <p className="text-[11px] text-white/60">{runItem.source_name || runItem.source_url}</p> : null}
                      </div>
                      <span className={`rounded-full border px-2 py-0.5 text-[10px] ${statusBadgeClass(runItem.run_status)}`}>{runItem.run_status}</span>
                    </div>

                    <div className="mt-3 grid grid-cols-2 gap-2 text-[12px]">
                      <div className="rounded-lg border border-white/12 bg-white/[0.03] p-2">
                        <p className="text-white/70">Duration</p>
                        <p className="text-white font-medium">{formatDuration(runItem.duration_seconds)}</p>
                      </div>
                      <div className="rounded-lg border border-white/12 bg-white/[0.03] p-2">
                        <p className="text-white/70">Items</p>
                        <p className="text-white font-medium">{runItem.items_new || 0} new / {runItem.items_scraped || 0} scraped</p>
                        <p className="text-[11px] text-white/70">categories: {Number((runItem as any).categories_scraped || 0)}</p>
                      </div>
                      <div className="rounded-lg border border-white/12 bg-white/[0.03] p-2 col-span-2">
                        <p className="text-white/70">Timeline</p>
                        <div className="mt-1 space-y-1">
                          {(runItem.timeline || []).map((step: any, idx: number) => (
                            <div key={`${step.status}-${idx}`} className="flex items-center gap-2 text-white/90">
                              {step.status === "error" ? <XCircle size={13} className="text-rose-300" /> : step.status === "completed" ? <CheckCircle2 size={13} className="text-emerald-300" /> : step.status === "running" ? <Server size={13} className="text-sky-300" /> : <Clock3 size={13} className="text-amber-300" />}
                              <span>{step.status}</span>
                              <span className="text-white/65">{formatDateTime(step.at)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>

                    {runItem.error_message ? (
                      <div className="mt-3 rounded-lg border border-rose-400/35 bg-rose-500/12 p-2 text-xs text-rose-100 flex gap-2">
                        <AlertCircle size={14} className="mt-0.5 shrink-0" />
                        <span>{runItem.error_message}</span>
                      </div>
                    ) : null}

                    <div className="mt-3 flex flex-wrap gap-2">
                      <button className="rounded-lg border border-sky-400/45 bg-sky-500/20 px-2.5 py-1.5 text-xs font-semibold text-sky-100" onClick={async () => { await retryRun(runItem.run_id); }}>
                        <RefreshCcw size={13} className="inline mr-1" /> Retry run
                      </button>
                      <button className="rounded-lg border border-emerald-400/45 bg-emerald-500/20 px-2.5 py-1.5 text-xs font-medium text-emerald-100" onClick={() => onOpenSourceDetails(runItem.source_id)}>
                        Open source details
                      </button>
                      <button className="rounded-lg border border-violet-400/45 bg-violet-500/20 px-2.5 py-1.5 text-xs font-medium text-violet-100" onClick={async () => { await runSourceNow({ sourceId: runItem.source_id, strategy: "deep" }); }}>
                        <Play size={13} className="inline mr-1" /> Run source now
                      </button>
                    </div>

                    <div className="mt-3">
                      <div className="mb-1 flex items-center justify-between text-[11px] text-white/75">
                        <span>Live logs</span>
                        <div className="flex items-center gap-2">
                          <span>{runItem.logs_meta?.lines || 0} lines</span>
                          <button
                            className="inline-flex items-center gap-1 rounded-md border border-white/25 px-2 py-1 text-[10px] text-white/85 hover:bg-white/10"
                            onClick={copyLogs}
                            disabled={!runItem.logs?.trim()}
                          >
                            {logsCopied ? <Check size={11} /> : <Copy size={11} />}
                            Copy logs
                          </button>
                        </div>
                      </div>
                      <div className="mb-2 space-y-2 rounded-lg border border-white/12 bg-black/20 p-2">
                        <input
                          value={logSearchQuery}
                          onChange={(event) => setLogSearchQuery(event.target.value)}
                          placeholder="Search logs..."
                          className="h-8 w-full rounded-md border border-white/20 bg-black/35 px-2 text-xs text-white placeholder:text-white/45 outline-none"
                        />
                        <div className="flex flex-wrap gap-1.5 text-[10px]">
                          {([
                            { key: "all", label: "All" },
                            { key: "errors", label: `Errors ${logCounts.errors}` },
                            { key: "warnings", label: `Warnings ${logCounts.warnings}` },
                            { key: "info", label: `Info ${logCounts.infos}` },
                            { key: "success", label: `Success ${logCounts.success}` },
                          ] as { key: LogFilter; label: string }[]).map((item) => (
                            <button
                              key={item.key}
                              className={`rounded-md border px-2 py-1 transition ${
                                activeLogFilter === item.key
                                  ? "border-sky-300/55 bg-sky-500/25 text-sky-100"
                                  : "border-white/20 bg-white/5 text-white/80 hover:bg-white/10"
                              }`}
                              onClick={() => setActiveLogFilter(item.key)}
                            >
                              {item.label}
                            </button>
                          ))}
                        </div>
                      </div>
                      <div className="max-h-[280px] overflow-auto rounded-lg border border-white/12 bg-[#050c17] p-2 text-[11px] leading-5">
                        {logItems.length === 0 ? (
                          <div className="text-slate-300">No logs captured yet. Wait for log events or open source details.</div>
                        ) : visibleLogItems.length === 0 ? (
                          <div className="text-slate-300">No logs match current search/filter.</div>
                        ) : (
                          <div className="space-y-1">
                            {visibleLogItems.map((item) => {
                              if (item.kind === "line") {
                                const ts = formatTimeColumn(item.line.timestamp);
                                return (
                                  <div key={item.id} className="flex items-start gap-2 font-mono">
                                    <span className="opacity-35 min-w-[1.8rem] text-right text-slate-500">{item.line.id.replace("log-", "")}</span>
                                    {ts ? <span className="text-cyan-300/90 min-w-[4.8rem] whitespace-nowrap">{ts}</span> : null}
                                    <span className={`uppercase text-[9px] px-1 py-[1px] rounded border ${levelBadgeClass(item.line.level)}`}>{item.line.level}</span>
                                    <span className={`break-words ${levelTextClass(item.line.level)}`}>{item.line.message}</span>
                                  </div>
                                );
                              }

                              const isExpanded = expandedJsonIds[item.id] ?? false;
                              return (
                                <div key={item.id} className="rounded-md border border-white/10 bg-white/[0.02]">
                                  <button
                                    className="w-full px-2 py-1.5 text-left text-[11px] text-slate-200 flex items-center gap-1.5"
                                    onClick={() =>
                                      setExpandedJsonIds((prev) => ({
                                        ...prev,
                                        [item.id]: !isExpanded,
                                      }))
                                    }
                                  >
                                    {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                                    <span className="text-fuchsia-200">JSON block ({item.lines.length} lines)</span>
                                    <span className="text-slate-400 truncate">{item.summary}</span>
                                  </button>
                                  {isExpanded ? (
                                    <div className="px-2 pb-2 font-mono text-[11px] leading-6">
                                      {item.payload.split(/\r?\n/).map((line, idx) => (
                                        <div key={`${item.id}-json-${idx}`}>{renderJsonStyledLine(line)}</div>
                                      ))}
                                    </div>
                                  ) : null}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="py-10 text-center text-sm text-white/75 space-y-2">
                    <p>Run not found.</p>
                    <p className="text-xs text-white/60">It may already be removed from history.</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : null}
      {selectedWorkerId ? (
        <div className="fixed inset-0 z-[85] flex items-end sm:items-center justify-center bg-black/65 p-2 sm:p-4">
          <div className="w-full max-w-2xl rounded-2xl border border-white/20 bg-[#0a1322] shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between border-b border-white/12 px-4 py-3">
              <div>
                <h3 className="text-lg font-semibold text-white">Worker Card</h3>
                <p className="text-xs text-white/70">{selectedWorkerId}</p>
                <p className="text-[11px] text-white/55">Created: {formatDateTime(selectedWorkerCreatedAt)}</p>
              </div>
              <button className="rounded-lg border border-white/25 px-2 py-1 text-xs text-white/85 hover:bg-white/10" onClick={() => setSelectedWorkerId(null)}>
                Close
              </button>
            </div>
            <div className="max-h-[78vh] overflow-y-auto p-4 space-y-3">
              <div className="flex items-center justify-end">
                <button
                  className={`inline-flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-xs font-medium disabled:opacity-50 ${
                    selectedWorker?.paused || selectedWorker?.status === "paused"
                      ? "border-emerald-400/45 bg-emerald-500/20 text-emerald-100"
                      : "border-amber-400/45 bg-amber-500/20 text-amber-100"
                  }`}
                  disabled={!selectedWorkerId || workerPausePendingId === selectedWorkerId}
                  onClick={() => void handleToggleWorkerPause()}
                >
                  {workerPausePendingId === selectedWorkerId ? <Loader2 size={13} className="animate-spin" /> : null}
                  {selectedWorker?.paused || selectedWorker?.status === "paused" ? "Resume worker" : "Pause worker"}
                </button>
              </div>
              <div className="grid gap-2 sm:grid-cols-6">
                <div className="rounded-lg border border-white/12 bg-black/20 p-2">
                  <p className="text-[11px] text-white/70">Status</p>
                  <p className="text-sm font-semibold text-white">{selectedWorker?.status || "unknown"}</p>
                </div>
                <div className="rounded-lg border border-white/12 bg-black/20 p-2">
                  <p className="text-[11px] text-white/70">Heartbeats</p>
                  <p className="text-sm font-semibold text-white">{selectedWorkerStats.heartbeats}</p>
                </div>
                <div className="rounded-lg border border-white/12 bg-black/20 p-2">
                  <p className="text-[11px] text-white/70">Busy snapshots</p>
                  <p className="text-sm font-semibold text-white">{selectedWorkerStats.busySnapshots}</p>
                </div>
                <div className="rounded-lg border border-white/12 bg-black/20 p-2">
                  <p className="text-[11px] text-white/70">Avg RAM</p>
                  <p className="text-sm font-semibold text-white">{selectedWorkerStats.avgRam}%</p>
                </div>
                <div className="rounded-lg border border-white/12 bg-black/20 p-2">
                  <p className="text-[11px] text-white/70">Idle snapshots</p>
                  <p className="text-sm font-semibold text-white">{selectedWorkerStats.idleSnapshots}</p>
                </div>
                <div className="rounded-lg border border-white/12 bg-black/20 p-2">
                  <p className="text-[11px] text-white/70">Completed tasks</p>
                  <p className="text-sm font-semibold text-white">{selectedWorkerStats.completedTasks}</p>
                </div>
              </div>

              <div className="rounded-xl border border-white/12 bg-white/[0.03] p-3">
                <p className="text-sm font-semibold text-white mb-2">Current tasks</p>
                <div className="space-y-1.5">
                  {(selectedWorker?.active_tasks || []).length ? (
                    (selectedWorker?.active_tasks || []).map((task: any, idx: number) => (
                      <div key={`active-${idx}`} className="rounded-lg border border-sky-400/25 bg-sky-500/10 px-2 py-1.5">
                        <p className="text-xs font-medium text-sky-100">{task.site_key || "unknown"} · source #{task.source_id ?? "?"}</p>
                        <p className="text-[11px] text-sky-100/80">run #{task.run_id ?? "?"} · {task.strategy || "deep"}</p>
                        {task.url ? <p className="text-[11px] text-sky-100/70 truncate">{task.url}</p> : null}
                      </div>
                    ))
                  ) : (
                    <div className="rounded-lg border border-dashed border-white/20 p-2 text-sm text-white/70">Idle</div>
                  )}
                </div>
              </div>

              <div className="rounded-xl border border-white/12 bg-white/[0.03] p-3">
                <p className="text-sm font-semibold text-white mb-2">Heartbeat history</p>
                <div className="max-h-64 overflow-y-auto space-y-1.5 pr-1">
                  {selectedWorkerHistory.slice().reverse().map((h, idx) => (
                    <div key={`${h.ts}-${idx}`} className="rounded-lg border border-white/12 bg-black/20 px-2 py-1.5">
                      <div className="flex items-center justify-between gap-2 text-xs">
                        <span className="text-white/90">{formatDateTime(h.ts)}</span>
                        <span className={`rounded-full border px-1.5 py-0.5 text-[10px] ${statusBadgeClass(h.status)}`}>{h.status}</span>
                      </div>
                      <div className="mt-1 grid grid-cols-2 gap-2 text-[11px] text-white/75">
                        <span>tasks: {h.tasks}</span>
                        <span className="text-right">completed: {h.completed}</span>
                        <span className="text-right">RAM: {h.ram}%</span>
                      </div>
                    </div>
                  ))}
                  {!selectedWorkerHistory.length ? <div className="rounded-lg border border-dashed border-white/20 p-2 text-sm text-white/70">No history yet.</div> : null}
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
