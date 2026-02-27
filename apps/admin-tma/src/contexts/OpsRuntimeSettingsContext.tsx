"use client";

import { createContext, useContext, useEffect, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchOpsRuntimeSettings, getOpsStreamUrl, updateOpsRuntimeSettings } from "@/lib/api";

export const OPS_CLIENT_INTERVAL_DEFAULTS: Record<string, number> = {
  "ops.overview_ms": 30000,
  "ops.sites_ms": 30000,
  "ops.pipeline_ms": 30000,
  "ops.active_runs_ms": 30000,
  "ops.discovery_ms": 30000,
  "ops.run_details_ms": 15000,
  "ops.queue_lanes_ms": 30000,
  "ops.scheduler_stats_ms": 30000,
  "ops.items_trend_ms": 30000,
  "ops.tasks_trend_ms": 30000,
  "ops.source_trend_ms": 30000,
  "dashboard.stats_ms": 60000,
  "dashboard.health_ms": 30000,
  "dashboard.scraping_ms": 60000,
  "dashboard.sources_ms": 30000,
  "dashboard.workers_ms": 30000,
  "dashboard.queue_stats_ms": 5000,
  "dashboard.queue_tasks_ms": 10000,
  "dashboard.queue_history_ms": 15000,
  "intelligence.summary_ms": 300000,
  "catalog.revalidate_ms": 30000,
};

type OpsRuntimeSettingsContextValue = {
  data: any;
  isLoading: boolean;
  error: unknown;
  refetch: () => Promise<any>;
  updateSettings: (payload: Record<string, unknown>) => Promise<any>;
  isUpdating: boolean;
  getIntervalMs: (key: string, fallbackMs: number) => number;
  restoreDefaults: () => Promise<any>;
};

const OpsRuntimeSettingsContext = createContext<OpsRuntimeSettingsContextValue | null>(null);

const clampMs = (value: unknown, fallback: number) => {
  const num = Number(value);
  if (!Number.isFinite(num)) return fallback;
  return Math.max(1000, Math.min(600000, Math.trunc(num)));
};

export function OpsRuntimeSettingsProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const settingsQuery = useQuery({
    queryKey: ["ops-runtime-settings"],
    queryFn: fetchOpsRuntimeSettings,
    staleTime: 30000,
    refetchInterval: (query) => (query.state.error ? false : 120000),
  });

  const updateMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => updateOpsRuntimeSettings(payload),
    onSuccess: (data) => {
      queryClient.setQueryData(["ops-runtime-settings"], data);
    },
  });

  useEffect(() => {
    let source: EventSource | null = null;
    try {
      source = new EventSource(getOpsStreamUrl());
    } catch {
      return;
    }
    const handler = () => {
      queryClient.invalidateQueries({ queryKey: ["ops-runtime-settings"] });
    };
    source.addEventListener("ops.settings.updated", handler);
    return () => {
      source?.removeEventListener("ops.settings.updated", handler);
      source?.close();
    };
  }, [queryClient]);

  const value = useMemo<OpsRuntimeSettingsContextValue>(() => {
    const getIntervalMs = (key: string, fallbackMs: number) => {
      const fromServer = settingsQuery.data?.item?.ops_client_intervals?.[key];
      const fromDefault = OPS_CLIENT_INTERVAL_DEFAULTS[key];
      return clampMs(fromServer, clampMs(fromDefault, fallbackMs));
    };

    const restoreDefaults = async () => {
      return updateMutation.mutateAsync({
        ops_aggregator_enabled: true,
        ops_aggregator_interval_ms: 2000,
        ops_snapshot_ttl_ms: 10000,
        ops_stale_max_age_ms: 60000,
        ops_client_intervals: OPS_CLIENT_INTERVAL_DEFAULTS,
      });
    };

    return {
      data: settingsQuery.data,
      isLoading: settingsQuery.isLoading,
      error: settingsQuery.error,
      refetch: settingsQuery.refetch,
      updateSettings: updateMutation.mutateAsync,
      isUpdating: updateMutation.isPending,
      getIntervalMs,
      restoreDefaults,
    };
  }, [
    settingsQuery.data,
    settingsQuery.error,
    settingsQuery.isLoading,
    settingsQuery.refetch,
    updateMutation.mutateAsync,
    updateMutation.isPending,
  ]);

  return <OpsRuntimeSettingsContext.Provider value={value}>{children}</OpsRuntimeSettingsContext.Provider>;
}

export function useOpsRuntimeSettings() {
  const ctx = useContext(OpsRuntimeSettingsContext);
  if (!ctx) {
    throw new Error("useOpsRuntimeSettings must be used within OpsRuntimeSettingsProvider");
  }
  return ctx;
}
