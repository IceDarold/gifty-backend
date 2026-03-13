import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  bulkUpdateOpsSources,
  forceRunSource,
  promoteOpsDiscovery,
  reactivateOpsDiscovery,
  rejectOpsDiscovery,
  runOpsSiteDiscovery,
  retryOpsRun,
} from "@/lib/api";
import { useAdminChannelQuery } from "@/hooks/useAdminStreamQuery";
import { useAdminRequest } from "@/contexts/AdminStreamContext";

const MAX_BACKOFF_MS = 30000;
const QUEUED_PAGE_SIZE = 50;

export function useOperationsData(initialSiteKey?: string) {
  const [selectedSiteKey, setSelectedSiteKey] = useState<string | null>(initialSiteKey || null);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [streamState, setStreamState] = useState<"connecting" | "connected" | "disconnected">("connecting");
  const [streamError, setStreamError] = useState<string | null>(null);
  const [discoveryStateFilter, setDiscoveryStateFilter] = useState<string>("new,promoted,rejected,inactive");
  const [discoverySearch, setDiscoverySearch] = useState<string>("");
  const [queuedPage, setQueuedPage] = useState(0);
  const [queuedState, setQueuedState] = useState<{
    items: any[];
    total: number;
    isLoading: boolean;
    isFetchingNextPage: boolean;
    hasMore: boolean;
    error: unknown;
  }>({
    items: [],
    total: 0,
    isLoading: true,
    isFetchingNextPage: false,
    hasMore: true,
    error: null,
  });
  const retryDelayRef = useRef(1000);
  const reconnectTimerRef = useRef<number | null>(null);
  const selectedSiteRef = useRef<string | null>(null);
  const selectedRunRef = useRef<number | null>(null);
  const request = useAdminRequest();

  useEffect(() => {
    selectedSiteRef.current = selectedSiteKey;
  }, [selectedSiteKey]);

  useEffect(() => {
    selectedRunRef.current = selectedRunId;
  }, [selectedRunId]);

  const overview = useAdminChannelQuery<any>("ops.overview", { requireFresh: true });
  const sites = useAdminChannelQuery<any>("ops.sites");
  const pipelineMap = useAdminChannelQuery<any>("ops.pipeline");
  const activeRuns = useAdminChannelQuery<any>("ops.runs.active");
  const discoveryRaw = useAdminChannelQuery<any>("ops.discovery");
  const runDetailsMap = useAdminChannelQuery<any>("ops.run_details", { requireFresh: true });
  const runDetailsRequest = useAdminRequestQuery<any>(
    selectedRunId ? "ops.run_detail" : "",
    { id: selectedRunId },
    [selectedRunId],
  );
  const completedRuns = useAdminChannelQuery<any>("ops.runs.completed");
  const errorRuns = useAdminChannelQuery<any>("ops.runs.error");
  const schedulerStats = useAdminChannelQuery<any>("ops.scheduler_stats");
  const itemsTrendMap = useAdminChannelQuery<any>("ops.items_trend");
  const tasksTrendMap = useAdminChannelQuery<any>("ops.tasks_trend");
  const sources = useAdminChannelQuery<any>("dashboard.sources");

  useEffect(() => {
    if (!selectedSiteKey && sites.data?.items?.length) {
      setSelectedSiteKey(sites.data.items[0].site_key);
    }
  }, [selectedSiteKey, sites.data]);

  useEffect(() => {
    setStreamState("connected");
    setStreamError(null);
    return () => {
      setStreamState("disconnected");
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      retryDelayRef.current = Math.min(MAX_BACKOFF_MS, retryDelayRef.current);
    };
  }, []);

  const fetchQueuedPage = useCallback(
    async (page: number, append: boolean) => {
      const limit = QUEUED_PAGE_SIZE;
      const offset = page * limit;
      setQueuedState((prev) => ({
        ...prev,
        isLoading: append ? prev.isLoading : true,
        isFetchingNextPage: append ? true : prev.isFetchingNextPage,
        error: null,
      }));
      try {
        const res = await request("ops.runs.queued", { limit, offset });
        const items = Array.isArray(res?.items) ? res.items : [];
        const resTotal = Number.isFinite(Number(res?.total)) ? Number(res?.total) : undefined;
        setQueuedState((prev) => {
          const merged = append ? [...prev.items, ...items] : items;
          const total = resTotal ?? (append ? prev.total : merged.length);
          const hasMore = total > merged.length;
          return {
            items: merged,
            total,
            isLoading: false,
            isFetchingNextPage: false,
            hasMore,
            error: null,
          };
        });
        setQueuedPage(page);
      } catch (err) {
        setQueuedState((prev) => ({
          ...prev,
          isLoading: false,
          isFetchingNextPage: false,
          error: err,
        }));
      }
    },
    [request],
  );

  useEffect(() => {
    void fetchQueuedPage(0, false);
  }, [fetchQueuedPage]);

  const queuedRuns = useMemo(
    () => ({
      data: { items: queuedState.items, total: queuedState.total },
      isLoading: queuedState.isLoading,
      isError: !!queuedState.error,
      error: queuedState.error,
      isFetchingNextPage: queuedState.isFetchingNextPage,
      hasNextPage: queuedState.hasMore,
      refetch: async () => {
        setQueuedPage(0);
        await fetchQueuedPage(0, false);
      },
      fetchNextPage: async () => {
        if (!queuedState.hasMore || queuedState.isFetchingNextPage) return;
        await fetchQueuedPage(queuedPage + 1, true);
      },
    }),
    [queuedState, queuedPage, fetchQueuedPage],
  );

  const pipelineData = useMemo(() => {
    const map = pipelineMap.data || {};
    if (!selectedSiteKey) return null;
    return map[selectedSiteKey] ?? null;
  }, [pipelineMap.data, selectedSiteKey]);

  const runDetailsData = useMemo(() => {
    if (!selectedRunId) return null;
    const map = runDetailsMap.data || {};
    const fromMap = map[String(selectedRunId)] ?? map[selectedRunId];
    if (fromMap) {
      return { item: fromMap };
    }
    if (runDetailsRequest.data) {
      return runDetailsRequest.data;
    }
    return null;
  }, [runDetailsMap.data, runDetailsRequest.data, selectedRunId]);

  const discoveryData = useMemo(() => {
    const items = Array.isArray(discoveryRaw.data?.items) ? discoveryRaw.data.items : [];
    const states = discoveryStateFilter
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const query = discoverySearch.trim().toLowerCase();
    const filtered = items.filter((item: any) => {
      if (selectedSiteKey && String(item.site_key || "") !== selectedSiteKey) return false;
      if (states.length && !states.includes(String(item.state || ""))) return false;
      if (!query) return true;
      const hay = `${item.site_key || ""} ${item.name || ""} ${item.url || ""} ${item.category_name || ""}`.toLowerCase();
      return hay.includes(query);
    });
    return { ...discoveryRaw.data, items: filtered };
  }, [discoveryRaw.data, discoveryStateFilter, discoverySearch, selectedSiteKey]);

  const pipeline = useMemo(
    () => ({
      data: pipelineData,
      isLoading: pipelineMap.isLoading,
      isError: false,
      error: null,
      refetch: async () => {},
    }),
    [pipelineData, pipelineMap.isLoading],
  );

  const runDetails = useMemo(
    () => ({
      data: runDetailsData,
      isLoading: runDetailsMap.isLoading || runDetailsRequest.isLoading,
      isError: runDetailsMap.isError || runDetailsRequest.isError,
      error: runDetailsMap.error || runDetailsRequest.error,
      refetch: runDetailsRequest.refetch,
    }),
    [
      runDetailsData,
      runDetailsMap.isLoading,
      runDetailsMap.isError,
      runDetailsMap.error,
      runDetailsRequest.isLoading,
      runDetailsRequest.isError,
      runDetailsRequest.error,
      runDetailsRequest.refetch,
    ],
  );

  const discovery = useMemo(
    () => ({
      data: discoveryData,
      isLoading: discoveryRaw.isLoading,
      isError: false,
      error: null,
      refetch: async () => {},
    }),
    [discoveryData, discoveryRaw.isLoading],
  );

  const promoteMutation = useMutation({
    mutationFn: (ids: number[]) => promoteOpsDiscovery(ids),
  });

  const rejectMutation = useMutation({
    mutationFn: (ids: number[]) => rejectOpsDiscovery(ids),
  });

  const reactivateMutation = useMutation({
    mutationFn: (ids: number[]) => reactivateOpsDiscovery(ids),
  });

  const bulkUpdateMutation = useMutation({
    mutationFn: (payload: { source_ids: number[]; priority?: number; refresh_interval_hours?: number; is_active?: boolean }) =>
      bulkUpdateOpsSources(payload),
  });

  const retryRunMutation = useMutation({
    mutationFn: (runId: number) => retryOpsRun(runId),
  });

  const runNowMutation = useMutation({
    mutationFn: ({ sourceId, strategy }: { sourceId: number; strategy?: string }) => forceRunSource(sourceId, strategy || "deep"),
  });

  const runSiteDiscoveryMutation = useMutation({
    mutationFn: (siteKey: string) => runOpsSiteDiscovery(siteKey),
  });

  const anyPendingAction = useMemo(
    () =>
      promoteMutation.isPending ||
      rejectMutation.isPending ||
      reactivateMutation.isPending ||
      bulkUpdateMutation.isPending ||
      retryRunMutation.isPending ||
      runNowMutation.isPending ||
      runSiteDiscoveryMutation.isPending,
    [
      promoteMutation.isPending,
      rejectMutation.isPending,
      reactivateMutation.isPending,
      bulkUpdateMutation.isPending,
      retryRunMutation.isPending,
      runNowMutation.isPending,
      runSiteDiscoveryMutation.isPending,
    ],
  );

  return {
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
    promoteCategories: promoteMutation.mutateAsync,
    rejectCategories: rejectMutation.mutateAsync,
    reactivateCategories: reactivateMutation.mutateAsync,
    bulkUpdateSources: bulkUpdateMutation.mutateAsync,
    retryRun: retryRunMutation.mutateAsync,
    runSourceNow: runNowMutation.mutateAsync,
    runSiteDiscovery: runSiteDiscoveryMutation.mutateAsync,
    anyPendingAction,
  };
}
