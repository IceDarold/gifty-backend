"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, Clock, Filter, RefreshCcw, X } from "lucide-react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ApiServerErrorBanner } from "@/components/ApiServerErrorBanner";
import { fetchLLMBreakdown, fetchLLMLogDetails, fetchLLMLogs, fetchLLMOutliers, fetchLLMStats, fetchLLMThroughput } from "@/lib/api";
import { useOpsRuntimeSettings } from "@/contexts/OpsRuntimeSettingsContext";
import { Modal } from "@/components/frontend/Modal";
import { useApiErrorToast } from "@/hooks/useApiErrorToast";
import { useRetryRegistry } from "@/contexts/RetryRegistryContext";

type Bucket = "minute" | "hour" | "day" | "week";

const clampInt = (value: number, min: number, max: number) => Math.max(min, Math.min(max, Math.trunc(value)));

const formatTsLabel = (iso: string, bucket: Bucket) => {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  const y = d.getUTCFullYear();
  const m = pad(d.getUTCMonth() + 1);
  const day = pad(d.getUTCDate());
  const hh = pad(d.getUTCHours());
  const mm = pad(d.getUTCMinutes());
  if (bucket === "minute") return `${m}/${day} ${hh}:${mm}`;
  if (bucket === "hour") return `${m}/${day} ${hh}:00`;
  if (bucket === "day") return `${y}-${m}-${day}`;
  return `${y}-${m}-${day}`; // week bucket start
};

export function LLMLogsView() {
  const { getIntervalMs } = useOpsRuntimeSettings();
  const retryRegistry = useRetryRegistry();
  const [days, setDays] = useState<number>(7);
  const [bucket, setBucket] = useState<Bucket>("hour");
  const [status, setStatus] = useState<string>("");
  const [provider, setProvider] = useState<string>("");
  const [model, setModel] = useState<string>("");
  const [callType, setCallType] = useState<string>("");
  const [sessionId, setSessionId] = useState<string>("");
  const [experimentId, setExperimentId] = useState<string>("");
  const [variantId, setVariantId] = useState<string>("");
  const [offset, setOffset] = useState<number>(0);
  const [selectedId, setSelectedId] = useState<string>("");
  const [selectedRow, setSelectedRow] = useState<any | null>(null);
  const [outlierMetric, setOutlierMetric] = useState<"latency" | "tokens" | "cost">("latency");
  const limit = 50;

  const logsQuery = useQuery({
    queryKey: ["llm-logs", { days, status, provider, model, callType, sessionId, experimentId, variantId, offset, limit }],
    queryFn: () =>
      fetchLLMLogs({
        days,
        limit,
        offset,
        status: status || undefined,
        provider: provider || undefined,
        model: model || undefined,
        call_type: callType || undefined,
        session_id: sessionId || undefined,
        experiment_id: experimentId || undefined,
        variant_id: variantId || undefined,
      }),
    refetchInterval: (q) => (q.state.error ? false : getIntervalMs("intelligence.summary_ms", 300000)),
  });

  const throughputQuery = useQuery({
    queryKey: ["llm-throughput", { days, bucket, status, provider, model, callType }],
    queryFn: () =>
      fetchLLMThroughput({
        days,
        bucket,
        status: status || undefined,
        provider: provider || undefined,
        model: model || undefined,
        call_type: callType || undefined,
      }),
    refetchInterval: (q) => (q.state.error ? false : 60000),
  });

  const chartData = useMemo(() => {
    const points = throughputQuery.data?.points || [];
    return points.map((p: any) => ({
      ts: p.ts,
      name: formatTsLabel(String(p.ts), bucket),
      count: Number(p.count || 0),
    }));
  }, [throughputQuery.data, bucket]);

  const statsQuery = useQuery({
    queryKey: ["llm-stats", { days, status, provider, model, callType }],
    queryFn: () =>
      fetchLLMStats({
        days,
        status: status || undefined,
        provider: provider || undefined,
        model: model || undefined,
        call_type: callType || undefined,
      }),
    refetchInterval: (q) => (q.state.error ? false : 120000),
  });

  const outliersQuery = useQuery({
    queryKey: ["llm-outliers", { days, metric: outlierMetric, status, provider, model, callType }],
    queryFn: () =>
      fetchLLMOutliers({
        days,
        metric: outlierMetric,
        limit: 10,
        status: status || undefined,
        provider: provider || undefined,
        model: model || undefined,
        call_type: callType || undefined,
      }),
    refetchInterval: (q) => (q.state.error ? false : 120000),
  });

  const detailsQuery = useQuery({
    queryKey: ["llm-log-details", { id: selectedId }],
    queryFn: () => fetchLLMLogDetails(selectedId),
    enabled: !!selectedId,
    staleTime: 60000,
  });

  const providerBreakdown = useQuery({
    queryKey: ["llm-breakdown", { days, group_by: "provider", status, provider, model, callType }],
    queryFn: () =>
      fetchLLMBreakdown({
        days,
        group_by: "provider",
        limit: 8,
        status: status || undefined,
        provider: provider || undefined,
        model: model || undefined,
        call_type: callType || undefined,
      }),
    refetchInterval: (q) => (q.state.error ? false : 120000),
  });

  const modelBreakdown = useQuery({
    queryKey: ["llm-breakdown", { days, group_by: "model", status, provider, model, callType }],
    queryFn: () =>
      fetchLLMBreakdown({
        days,
        group_by: "model",
        limit: 8,
        status: status || undefined,
        provider: provider || undefined,
        model: model || undefined,
        call_type: callType || undefined,
      }),
    refetchInterval: (q) => (q.state.error ? false : 120000),
  });

  const callTypeBreakdown = useQuery({
    queryKey: ["llm-breakdown", { days, group_by: "call_type", status, provider, model, callType }],
    queryFn: () =>
      fetchLLMBreakdown({
        days,
        group_by: "call_type",
        limit: 10,
        status: status || undefined,
        provider: provider || undefined,
        model: model || undefined,
        call_type: callType || undefined,
      }),
    refetchInterval: (q) => (q.state.error ? false : 120000),
  });

  const statusBreakdown = useQuery({
    queryKey: ["llm-breakdown", { days, group_by: "status", status, provider, model, callType }],
    queryFn: () =>
      fetchLLMBreakdown({
        days,
        group_by: "status",
        limit: 8,
        status: status || undefined,
        provider: provider || undefined,
        model: model || undefined,
        call_type: callType || undefined,
      }),
    refetchInterval: (q) => (q.state.error ? false : 120000),
  });

	  useApiErrorToast({
	    id: "llm-analytics-api",
	    title: "LLM Analytics API временно недоступен",
	    retryKey: "llm-analytics-api",
	    retryLabel: "Повторить",
	    errors: [
	      logsQuery.error,
	      throughputQuery.error,
	      statsQuery.error,
	      outliersQuery.error,
	      providerBreakdown.error,
	      modelBreakdown.error,
	      callTypeBreakdown.error,
	      statusBreakdown.error,
	      detailsQuery.error,
	    ],
	    enabled: true,
	    ttlMs: 10000,
	  });

  useEffect(() => {
	    const unregister = retryRegistry.register("llm-analytics-api", async () => {
	      await Promise.allSettled([
	        logsQuery.refetch(),
	        throughputQuery.refetch(),
	        statsQuery.refetch(),
	        outliersQuery.refetch(),
	        providerBreakdown.refetch(),
	        modelBreakdown.refetch(),
	        callTypeBreakdown.refetch(),
	        statusBreakdown.refetch(),
	        detailsQuery.refetch(),
	      ]);
	    });
	    return unregister;
	  }, [
	    retryRegistry,
	    logsQuery.refetch,
	    throughputQuery.refetch,
	    statsQuery.refetch,
	    outliersQuery.refetch,
	    providerBreakdown.refetch,
	    modelBreakdown.refetch,
	    callTypeBreakdown.refetch,
	    statusBreakdown.refetch,
	    detailsQuery.refetch,
	  ]);

  const total = Number(logsQuery.data?.total || 0);
  const items = Array.isArray(logsQuery.data?.items) ? logsQuery.data.items : [];
  const hasPrev = offset > 0;
  const hasNext = offset + limit < total;

  const formatMoney = (value: any) => {
    const num = Number(value || 0);
    if (!Number.isFinite(num)) return "$0.0000";
    return `$${num.toFixed(4)}`;
  };

  const formatNum = (value: any) => {
    const num = Number(value || 0);
    if (!Number.isFinite(num)) return "0";
    return num.toLocaleString();
  };

  const toPrettyJson = (value: any) => {
    try {
      if (value === null || value === undefined) return "";
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value ?? "");
    }
  };

  const details = detailsQuery.data as any | undefined;
  const modalOpen = !!selectedId;
  const modalHeader = details || selectedRow;

  const copyToClipboard = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      // ignore
    }
  };

  return (
    <div className="space-y-4 px-4 pb-6 animate-in fade-in duration-300">
      <div className="pt-2">
        <h2 className="text-xl font-bold flex items-center gap-2">
          <BarChart3 className="text-[var(--tg-theme-button-color)]" size={22} />
          LLM Logs
        </h2>
        <p className="text-[var(--tg-theme-hint-color)] text-xs mt-1">
          Throughput + call-level observability (UTC)
        </p>
      </div>

	      <ApiServerErrorBanner
	        errors={[
	          logsQuery.error,
	          throughputQuery.error,
	          statsQuery.error,
	          outliersQuery.error,
	          providerBreakdown.error,
	          modelBreakdown.error,
	          callTypeBreakdown.error,
	          statusBreakdown.error,
	          detailsQuery.error,
	        ]}
	        onRetry={async () => {
	          await Promise.allSettled([logsQuery.refetch(), throughputQuery.refetch(), statsQuery.refetch(), outliersQuery.refetch()]);
	        }}
	        title="LLM Analytics API временно недоступен"
	      />

      <div className="card space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm font-bold">
            <Filter size={16} className="text-[var(--tg-theme-hint-color)]" />
            Filters
          </div>
	          <button
	            onClick={() => {
	              void Promise.allSettled([
	                logsQuery.refetch(),
	                throughputQuery.refetch(),
	                statsQuery.refetch(),
	                outliersQuery.refetch(),
	                providerBreakdown.refetch(),
	                modelBreakdown.refetch(),
	                callTypeBreakdown.refetch(),
	                statusBreakdown.refetch(),
	              ]);
	            }}
            className="inline-flex items-center gap-2 rounded-xl bg-white/5 px-3 py-2 text-xs font-bold border border-white/10 hover:bg-white/10 active:scale-95 transition-all"
          >
            <RefreshCcw size={14} className="text-[var(--tg-theme-hint-color)]" />
            Refresh
          </button>
        </div>

	        <div className="grid grid-cols-2 lg:grid-cols-9 gap-2">
          <label className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-wider text-[var(--tg-theme-hint-color)]">Days</span>
            <input
              type="number"
              value={days}
              min={1}
              max={90}
              onChange={(e) => {
                setOffset(0);
                setDays(clampInt(Number(e.target.value || 7), 1, 90));
              }}
              className="rounded-xl bg-white/5 border border-white/10 px-3 py-2 text-sm outline-none"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-wider text-[var(--tg-theme-hint-color)]">Bucket</span>
            <select
              value={bucket}
              onChange={(e) => setBucket(e.target.value as Bucket)}
              className="rounded-xl bg-white/5 border border-white/10 px-3 py-2 text-sm outline-none"
            >
              <option value="minute">Minute</option>
              <option value="hour">Hour</option>
              <option value="day">Day</option>
              <option value="week">Week</option>
            </select>
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-wider text-[var(--tg-theme-hint-color)]">Status</span>
            <select
              value={status}
              onChange={(e) => {
                setOffset(0);
                setStatus(e.target.value);
              }}
              className="rounded-xl bg-white/5 border border-white/10 px-3 py-2 text-sm outline-none"
            >
              <option value="">All</option>
              <option value="ok">ok</option>
              <option value="error">error</option>
            </select>
          </label>

	          <label className="flex flex-col gap-1">
	            <span className="text-[10px] uppercase tracking-wider text-[var(--tg-theme-hint-color)]">Provider</span>
	            <input
	              value={provider}
	              onChange={(e) => {
	                setOffset(0);
	                setProvider(e.target.value);
	              }}
	              placeholder="groq / anthropic / gemini..."
	              className="rounded-xl bg-white/5 border border-white/10 px-3 py-2 text-sm outline-none"
	            />
	          </label>

	          <label className="flex flex-col gap-1">
	            <span className="text-[10px] uppercase tracking-wider text-[var(--tg-theme-hint-color)]">Model</span>
	            <input
	              value={model}
	              onChange={(e) => {
	                setOffset(0);
	                setModel(e.target.value);
	              }}
	              placeholder="claude-3-haiku..."
	              className="rounded-xl bg-white/5 border border-white/10 px-3 py-2 text-sm outline-none"
	            />
	          </label>

	          <label className="flex flex-col gap-1">
	            <span className="text-[10px] uppercase tracking-wider text-[var(--tg-theme-hint-color)]">Call type</span>
	            <input
	              value={callType}
	              onChange={(e) => {
	                setOffset(0);
	                setCallType(e.target.value);
	              }}
	              placeholder="normalize_topics..."
	              className="rounded-xl bg-white/5 border border-white/10 px-3 py-2 text-sm outline-none"
	            />
	          </label>

	          <label className="flex flex-col gap-1">
	            <span className="text-[10px] uppercase tracking-wider text-[var(--tg-theme-hint-color)]">Session</span>
	            <input
	              value={sessionId}
	              onChange={(e) => {
	                setOffset(0);
	                setSessionId(e.target.value);
	              }}
	              placeholder="session_id"
	              className="rounded-xl bg-white/5 border border-white/10 px-3 py-2 text-sm outline-none"
	            />
	          </label>

	          <label className="flex flex-col gap-1">
	            <span className="text-[10px] uppercase tracking-wider text-[var(--tg-theme-hint-color)]">Experiment</span>
	            <input
	              value={experimentId}
	              onChange={(e) => {
	                setOffset(0);
	                setExperimentId(e.target.value);
	              }}
	              placeholder="experiment_id"
	              className="rounded-xl bg-white/5 border border-white/10 px-3 py-2 text-sm outline-none"
	            />
	          </label>

	          <label className="flex flex-col gap-1">
	            <span className="text-[10px] uppercase tracking-wider text-[var(--tg-theme-hint-color)]">Variant</span>
	            <input
	              value={variantId}
	              onChange={(e) => {
	                setOffset(0);
	                setVariantId(e.target.value);
	              }}
	              placeholder="variant_id"
	              className="rounded-xl bg-white/5 border border-white/10 px-3 py-2 text-sm outline-none"
	            />
	          </label>
	        </div>
	      </div>

	      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
	        <div className="card overflow-hidden">
	          <div className="flex items-center justify-between">
	            <h3 className="text-sm font-bold">Summary</h3>
	            <span className="text-[10px] text-[var(--tg-theme-hint-color)]">{days}d</span>
	          </div>
	          <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
	            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
	              <div className="text-[10px] uppercase tracking-wider text-[var(--tg-theme-hint-color)]">Requests</div>
	              <div className="mt-1 text-lg font-black">{formatNum(statsQuery.data?.total || 0)}</div>
	              <div className="text-[10px] text-[var(--tg-theme-hint-color)]">
	                errors: {formatNum(statsQuery.data?.errors || 0)} · rate: {((statsQuery.data?.error_rate || 0) * 100).toFixed(1)}%
	              </div>
	            </div>
	            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
	              <div className="text-[10px] uppercase tracking-wider text-[var(--tg-theme-hint-color)]">Cost</div>
	              <div className="mt-1 text-lg font-black">{formatMoney(statsQuery.data?.total_cost_usd || 0)}</div>
	              <div className="text-[10px] text-[var(--tg-theme-hint-color)]">
	                avg: {formatMoney(statsQuery.data?.avg_cost_usd || 0)}
	              </div>
	            </div>
	            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
	              <div className="text-[10px] uppercase tracking-wider text-[var(--tg-theme-hint-color)]">Latency</div>
	              <div className="mt-1 text-lg font-black">{Math.round(Number(statsQuery.data?.p95_latency_ms || 0))}ms</div>
	              <div className="text-[10px] text-[var(--tg-theme-hint-color)]">
	                p50: {Math.round(Number(statsQuery.data?.p50_latency_ms || 0))}ms · avg: {Math.round(Number(statsQuery.data?.avg_latency_ms || 0))}ms
	              </div>
	            </div>
	            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
	              <div className="text-[10px] uppercase tracking-wider text-[var(--tg-theme-hint-color)]">Tokens</div>
	              <div className="mt-1 text-lg font-black">{formatNum(Math.round(Number(statsQuery.data?.p95_total_tokens || 0)))}</div>
	              <div className="text-[10px] text-[var(--tg-theme-hint-color)]">
	                p50: {formatNum(Math.round(Number(statsQuery.data?.p50_total_tokens || 0)))} · avg:{" "}
	                {formatNum(Math.round(Number(statsQuery.data?.avg_total_tokens || 0)))}
	              </div>
	            </div>
	          </div>
	        </div>

	        <div className="card overflow-hidden">
	          <div className="flex items-center justify-between gap-3">
	            <h3 className="text-sm font-bold">Outliers</h3>
	            <div className="flex items-center gap-2">
	              <select
	                value={outlierMetric}
	                onChange={(e) => setOutlierMetric(e.target.value as any)}
	                className="rounded-xl bg-white/5 border border-white/10 px-3 py-2 text-xs outline-none"
	              >
	                <option value="latency">Latency</option>
	                <option value="tokens">Tokens</option>
	                <option value="cost">Cost</option>
	              </select>
	            </div>
	          </div>
	          <div className="mt-3 space-y-2">
	            {(outliersQuery.data?.items || []).map((row: any) => (
	              <button
	                key={String(row.id)}
	                onClick={() => {
	                  setSelectedRow(row);
	                  setSelectedId(String(row.id));
	                }}
	                className="w-full flex items-center justify-between rounded-xl border border-white/10 bg-white/5 px-3 py-2 hover:bg-white/10 transition-colors"
	              >
	                <div className="min-w-0">
	                  <div className="text-xs font-bold truncate">
	                    {row.provider} · {row.model} · {row.call_type}
	                  </div>
	                  <div className="text-[10px] text-[var(--tg-theme-hint-color)] truncate">
	                    {formatTsLabel(String(row.created_at || ""), "minute")}
	                  </div>
	                </div>
	                <div className="text-right">
	                  <div className="text-xs font-bold">
	                    {outlierMetric === "cost"
	                      ? formatMoney(row.cost_usd)
	                      : outlierMetric === "tokens"
	                        ? `${formatNum(row.total_tokens)} t`
	                        : `${Number(row.latency_ms || 0)}ms`}
	                  </div>
	                  <div className="text-[10px] text-[var(--tg-theme-hint-color)]">{String(row.status || "ok")}</div>
	                </div>
	              </button>
	            ))}
	            {!outliersQuery.data?.items?.length ? (
	              <div className="text-xs text-[var(--tg-theme-hint-color)]">No data</div>
	            ) : null}
	          </div>
	        </div>
	      </div>

	      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
	        <div className="card overflow-hidden">
	          <div className="flex items-center justify-between">
	            <h3 className="text-sm font-bold">Breakdown: status</h3>
	            <span className="text-[10px] text-[var(--tg-theme-hint-color)]">{days}d</span>
          </div>
          <div className="mt-3 space-y-2">
            {(statusBreakdown.data?.items || []).map((row: any) => (
              <button
                key={String(row.key)}
                onClick={() => {
                  setOffset(0);
                  setStatus(String(row.key || ""));
                }}
                className="w-full flex items-center justify-between rounded-xl border border-white/10 bg-white/5 px-3 py-2 hover:bg-white/10 transition-colors"
              >
                <span className="text-xs font-bold">{String(row.key || "-")}</span>
                <span className="text-xs text-[var(--tg-theme-hint-color)]">{formatNum(row.requests)}</span>
              </button>
            ))}
            {!statusBreakdown.data?.items?.length ? (
              <div className="text-xs text-[var(--tg-theme-hint-color)]">No data</div>
            ) : null}
          </div>
        </div>

        <div className="card overflow-hidden">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold">Breakdown: provider</h3>
            <span className="text-[10px] text-[var(--tg-theme-hint-color)]">{days}d</span>
          </div>
          <div className="mt-3 space-y-2">
            {(providerBreakdown.data?.items || []).map((row: any) => (
              <button
                key={String(row.key)}
                onClick={() => {
                  setOffset(0);
                  setProvider(String(row.key || ""));
                }}
                className="w-full flex items-center justify-between rounded-xl border border-white/10 bg-white/5 px-3 py-2 hover:bg-white/10 transition-colors"
              >
                <div className="flex flex-col items-start">
                  <span className="text-xs font-bold">{String(row.key || "-")}</span>
                  <span className="text-[10px] text-[var(--tg-theme-hint-color)]">
                    {formatMoney(row.total_cost_usd)} · {formatNum(row.total_tokens)} tokens
                  </span>
                </div>
                <span className="text-xs text-[var(--tg-theme-hint-color)]">{formatNum(row.requests)}</span>
              </button>
            ))}
            {!providerBreakdown.data?.items?.length ? (
              <div className="text-xs text-[var(--tg-theme-hint-color)]">No data</div>
            ) : null}
          </div>
        </div>

        <div className="card overflow-hidden">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold">Breakdown: model</h3>
            <span className="text-[10px] text-[var(--tg-theme-hint-color)]">{days}d</span>
          </div>
          <div className="mt-3 space-y-2">
            {(modelBreakdown.data?.items || []).map((row: any) => (
              <div
                key={String(row.key)}
                className="w-full flex items-center justify-between rounded-xl border border-white/10 bg-white/5 px-3 py-2"
                title={String(row.key || "")}
              >
                <div className="flex flex-col items-start min-w-0">
                  <span className="text-xs font-bold truncate max-w-[260px]">{String(row.key || "-")}</span>
                  <span className="text-[10px] text-[var(--tg-theme-hint-color)]">
                    {formatMoney(row.total_cost_usd)} · {Math.round(Number(row.avg_latency_ms || 0))}ms avg
                  </span>
                </div>
                <span className="text-xs text-[var(--tg-theme-hint-color)]">{formatNum(row.requests)}</span>
              </div>
            ))}
            {!modelBreakdown.data?.items?.length ? (
              <div className="text-xs text-[var(--tg-theme-hint-color)]">No data</div>
            ) : null}
          </div>
        </div>

        <div className="card overflow-hidden">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold">Breakdown: call type</h3>
            <span className="text-[10px] text-[var(--tg-theme-hint-color)]">{days}d</span>
          </div>
          <div className="mt-3 space-y-2">
            {(callTypeBreakdown.data?.items || []).map((row: any) => (
              <button
                key={String(row.key)}
                onClick={() => {
                  setOffset(0);
                  setCallType(String(row.key || ""));
                }}
                className="w-full flex items-center justify-between rounded-xl border border-white/10 bg-white/5 px-3 py-2 hover:bg-white/10 transition-colors"
                title={String(row.key || "")}
              >
                <div className="flex flex-col items-start min-w-0">
                  <span className="text-xs font-bold truncate max-w-[260px]">{String(row.key || "-")}</span>
                  <span className="text-[10px] text-[var(--tg-theme-hint-color)]">
                    {formatMoney(row.total_cost_usd)} · {formatNum(row.total_tokens)} tokens
                  </span>
                </div>
                <span className="text-xs text-[var(--tg-theme-hint-color)]">{formatNum(row.requests)}</span>
              </button>
            ))}
            {!callTypeBreakdown.data?.items?.length ? (
              <div className="text-xs text-[var(--tg-theme-hint-color)]">No data</div>
            ) : null}
          </div>
        </div>
      </div>

      <div className="card space-y-3 overflow-hidden">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock size={16} className="text-[var(--tg-theme-hint-color)]" />
            <div>
              <h3 className="text-sm font-bold">Requests throughput</h3>
              <p className="text-[10px] text-[var(--tg-theme-hint-color)]">
                {chartData.length ? `${chartData.length} points` : "No data"}
              </p>
            </div>
          </div>
        </div>
        <div className="h-52 -mx-2">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="llmCount" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#2481cc" stopOpacity={0.45} />
                  <stop offset="100%" stopColor="#2481cc" stopOpacity={0.06} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
              <Tooltip
                contentStyle={{
                  background: "rgba(0,0,0,0.75)",
                  border: "1px solid rgba(255,255,255,0.12)",
                  borderRadius: 12,
                }}
                labelStyle={{ color: "rgba(255,255,255,0.8)", fontSize: 12 }}
              />
              <Area type="monotone" dataKey="count" stroke="#64b5ef" fill="url(#llmCount)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-bold">Calls</h3>
            <p className="text-[10px] text-[var(--tg-theme-hint-color)]">
              {logsQuery.isLoading ? "Loading..." : `${Math.min(offset + limit, total)} / ${total}`}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              disabled={!hasPrev}
              onClick={() => setOffset((v) => Math.max(0, v - limit))}
              className="rounded-xl px-3 py-2 text-xs font-bold border border-white/10 bg-white/5 disabled:opacity-40"
            >
              Prev
            </button>
            <button
              disabled={!hasNext}
              onClick={() => setOffset((v) => v + limit)}
              className="rounded-xl px-3 py-2 text-xs font-bold border border-white/10 bg-white/5 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>

        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-[10px] uppercase tracking-wider text-[var(--tg-theme-hint-color)]">
              <tr className="border-b border-white/10">
                <th className="text-left py-2 pr-3">Time</th>
                <th className="text-left py-2 pr-3">Status</th>
                <th className="text-left py-2 pr-3">Provider / Model</th>
                <th className="text-left py-2 pr-3">Call</th>
                <th className="text-right py-2 pr-3">Latency</th>
                <th className="text-right py-2 pr-3">Tokens</th>
                <th className="text-right py-2 pr-3">Cost</th>
              </tr>
            </thead>
            <tbody>
	              {items.map((it: any) => {
                const isErr = String(it.status) === "error";
                const ts = String(it.created_at || "");
                return (
	                  <tr
	                    key={it.id}
	                    className="border-b border-white/5 hover:bg-white/5 transition-colors cursor-pointer"
	                    onClick={() => {
	                      setSelectedRow(it);
	                      setSelectedId(String(it.id));
	                    }}
	                  >
                    <td className="py-2 pr-3 whitespace-nowrap text-xs">{ts ? formatTsLabel(ts, "minute") : "-"}</td>
                    <td className="py-2 pr-3 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold border ${
                          isErr
                            ? "text-red-300 bg-red-500/10 border-red-400/30"
                            : "text-emerald-300 bg-emerald-500/10 border-emerald-400/30"
                        }`}
                        title={isErr ? String(it.error_type || "error") : "ok"}
                      >
                        {String(it.status || "ok")}
                      </span>
                    </td>
                    <td className="py-2 pr-3 whitespace-nowrap">
                      <div className="font-bold text-xs">{String(it.provider || "-")}</div>
                      <div className="text-[10px] text-[var(--tg-theme-hint-color)]">{String(it.model || "-")}</div>
                    </td>
                    <td className="py-2 pr-3 whitespace-nowrap text-xs">{String(it.call_type || "-")}</td>
                    <td className="py-2 pr-3 whitespace-nowrap text-right text-xs">{Number(it.latency_ms || 0)}ms</td>
                    <td className="py-2 pr-3 whitespace-nowrap text-right text-xs">{Number(it.total_tokens || 0)}</td>
                    <td className="py-2 pr-3 whitespace-nowrap text-right text-xs">
                      ${Number(it.cost_usd || 0).toFixed(4)}
                    </td>
                  </tr>
                );
              })}
              {!items.length && !logsQuery.isLoading ? (
                <tr>
                  <td colSpan={7} className="py-6 text-center text-xs text-[var(--tg-theme-hint-color)]">
                    No LLM logs found for current filters.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
	      </div>

	      <Modal
	        isOpen={modalOpen}
	        onClose={() => {
	          setSelectedId("");
	          setSelectedRow(null);
	        }}
	      >
	        <div className="flex items-start justify-between gap-3">
	          <div className="min-w-0">
	            <h3 className="text-base font-black truncate">LLM Call Details</h3>
	            <p className="text-[10px] text-[var(--tg-theme-hint-color)] mt-1">
	              {modalHeader?.provider} · {modalHeader?.model} · {modalHeader?.call_type}
	            </p>
	          </div>
	          <button
	            onClick={() => {
	              setSelectedId("");
	              setSelectedRow(null);
	            }}
	            className="rounded-xl border border-white/10 bg-white/5 p-2 hover:bg-white/10 transition-colors"
	            aria-label="Close"
	          >
	            <X size={16} className="text-[var(--tg-theme-hint-color)]" />
	          </button>
	        </div>

	        <div className="mt-4 grid grid-cols-1 lg:grid-cols-2 gap-3">
	          <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
	            <div className="text-[10px] uppercase tracking-wider text-[var(--tg-theme-hint-color)]">Meta</div>
	            <div className="mt-2 text-xs space-y-1">
	              <div>
	                <span className="text-[var(--tg-theme-hint-color)]">Time:</span>{" "}
	                <span className="font-bold">{modalHeader?.created_at || "-"}</span>
	              </div>
	              <div>
	                <span className="text-[var(--tg-theme-hint-color)]">Status:</span>{" "}
	                <span className="font-bold">{modalHeader?.status || "ok"}</span>
	              </div>
	              <div>
	                <span className="text-[var(--tg-theme-hint-color)]">Finish reason:</span>{" "}
	                <span className="font-bold">{details?.finish_reason || "-"}</span>
	              </div>
	              <div>
	                <span className="text-[var(--tg-theme-hint-color)]">Latency:</span>{" "}
	                <span className="font-bold">{Number(modalHeader?.latency_ms || 0)}ms</span>
	              </div>
	              <div>
	                <span className="text-[var(--tg-theme-hint-color)]">Tokens (in/out/total):</span>{" "}
	                <span className="font-bold">
	                  {formatNum(details?.prompt_tokens ?? modalHeader?.prompt_tokens ?? 0)} /{" "}
	                  {formatNum(details?.completion_tokens ?? modalHeader?.completion_tokens ?? 0)} /{" "}
	                  {formatNum(details?.total_tokens ?? modalHeader?.total_tokens ?? 0)}
	                </span>
	              </div>
	              <div>
	                <span className="text-[var(--tg-theme-hint-color)]">Cost:</span>{" "}
	                <span className="font-bold">{formatMoney(modalHeader?.cost_usd)}</span>
	              </div>
	              <div>
	                <span className="text-[var(--tg-theme-hint-color)]">Provider request id:</span>{" "}
	                <span className="font-bold">{modalHeader?.provider_request_id || details?.provider_request_id || "-"}</span>
	              </div>
	              <div className="break-all">
	                <span className="text-[var(--tg-theme-hint-color)]">Prompt hash:</span>{" "}
	                <span className="font-bold">{modalHeader?.prompt_hash || details?.prompt_hash || "-"}</span>
	              </div>
	              {details?.session_id ? (
	                <div className="flex items-center justify-between gap-2">
	                  <div className="break-all">
	                    <span className="text-[var(--tg-theme-hint-color)]">Session:</span>{" "}
	                    <span className="font-bold">{details.session_id}</span>
	                  </div>
	                  <button
	                    onClick={() => {
	                      setOffset(0);
	                      setSessionId(String(details.session_id || ""));
	                      setSelectedId("");
	                      setSelectedRow(null);
	                    }}
	                    className="rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-[10px] font-semibold hover:bg-white/10"
	                  >
	                    Filter
	                  </button>
	                </div>
	              ) : null}

	              {Array.isArray(details?.related_calls) && details.related_calls.length ? (
	                <div className="pt-2">
	                  <div className="text-[10px] uppercase tracking-wider text-[var(--tg-theme-hint-color)]">Related calls</div>
	                  <div className="mt-2 space-y-1">
	                    {details.related_calls.slice(0, 10).map((c: any) => (
	                      <button
	                        key={String(c.id)}
	                        onClick={() => {
	                          setSelectedRow(c);
	                          setSelectedId(String(c.id));
	                        }}
	                        className="w-full flex items-center justify-between rounded-xl border border-white/10 bg-white/5 px-2.5 py-2 hover:bg-white/10 transition-colors"
	                      >
	                        <div className="min-w-0 text-left">
	                          <div className="text-[11px] font-bold truncate">{String(c.call_type || "-")}</div>
	                          <div className="text-[10px] text-[var(--tg-theme-hint-color)] truncate">
	                            {formatTsLabel(String(c.created_at || ""), "minute")}
	                          </div>
	                        </div>
	                        <div className="text-right">
	                          <div className="text-[11px] font-bold">{Number(c.latency_ms || 0)}ms</div>
	                          <div className="text-[10px] text-[var(--tg-theme-hint-color)]">{String(c.status || "ok")}</div>
	                        </div>
	                      </button>
	                    ))}
	                  </div>
	                </div>
	              ) : null}
	            </div>
	          </div>

	          <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
	            <div className="text-[10px] uppercase tracking-wider text-[var(--tg-theme-hint-color)]">Error</div>
	            <div className="mt-2 text-xs space-y-2">
	              <div className="flex items-center justify-between">
	                <span className="text-[var(--tg-theme-hint-color)]">Type</span>
	                <span className="font-bold">{details?.error_type || modalHeader?.error_type || "-"}</span>
	              </div>
	              <div className="text-[10px] text-[var(--tg-theme-hint-color)]">Message</div>
	              <pre className="whitespace-pre-wrap break-words rounded-xl border border-white/10 bg-black/20 p-2 text-[11px] leading-snug">
	                {details?.error_message || modalHeader?.error_message || ""}
	              </pre>
	            </div>
	          </div>

	          <div className="lg:col-span-2 rounded-2xl border border-white/10 bg-white/5 p-3">
	            <div className="flex items-center justify-between gap-3">
	              <div className="text-[10px] uppercase tracking-wider text-[var(--tg-theme-hint-color)]">Prompts</div>
	              <button
	                onClick={() => void copyToClipboard(toPrettyJson(details))}
	                className="rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-[10px] font-semibold hover:bg-white/10"
	              >
	                Copy JSON
	              </button>
	            </div>
	            <div className="mt-2 grid grid-cols-1 lg:grid-cols-2 gap-3">
	              <div>
	                <div className="text-[10px] text-[var(--tg-theme-hint-color)]">System</div>
	                <pre className="mt-1 max-h-[260px] overflow-auto whitespace-pre-wrap break-words rounded-xl border border-white/10 bg-black/20 p-2 text-[11px] leading-snug">
	                  {details?.system_prompt?.rendered || ""}
	                </pre>
	                <button
	                  onClick={() => void copyToClipboard(String(details?.system_prompt?.rendered || ""))}
	                  className="mt-2 rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-[10px] font-semibold hover:bg-white/10"
	                >
	                  Copy
	                </button>
	              </div>
	              <div>
	                <div className="text-[10px] text-[var(--tg-theme-hint-color)]">User</div>
	                <pre className="mt-1 max-h-[260px] overflow-auto whitespace-pre-wrap break-words rounded-xl border border-white/10 bg-black/20 p-2 text-[11px] leading-snug">
	                  {details?.user_prompt?.rendered || ""}
	                </pre>
	                <button
	                  onClick={() => void copyToClipboard(String(details?.user_prompt?.rendered || ""))}
	                  className="mt-2 rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-[10px] font-semibold hover:bg-white/10"
	                >
	                  Copy
	                </button>
	              </div>
	            </div>
	          </div>

	          <div className="lg:col-span-2 rounded-2xl border border-white/10 bg-white/5 p-3">
	            <div className="text-[10px] uppercase tracking-wider text-[var(--tg-theme-hint-color)]">Response</div>
	            <div className="mt-2 grid grid-cols-1 lg:grid-cols-2 gap-3">
	              <div>
	                <div className="text-[10px] text-[var(--tg-theme-hint-color)]">Output</div>
	                <pre className="mt-1 max-h-[320px] overflow-auto whitespace-pre-wrap break-words rounded-xl border border-white/10 bg-black/20 p-2 text-[11px] leading-snug">
	                  {details?.response?.output_text || ""}
	                </pre>
	                <button
	                  onClick={() => void copyToClipboard(String(details?.response?.output_text || ""))}
	                  className="mt-2 rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-[10px] font-semibold hover:bg-white/10"
	                >
	                  Copy
	                </button>
	              </div>
	              <div>
	                <div className="text-[10px] text-[var(--tg-theme-hint-color)]">Raw provider JSON</div>
	                <pre className="mt-1 max-h-[320px] overflow-auto whitespace-pre rounded-xl border border-white/10 bg-black/20 p-2 text-[11px] leading-snug">
	                  {toPrettyJson(details?.response?.raw_response)}
	                </pre>
	                <button
	                  onClick={() => void copyToClipboard(toPrettyJson(details?.response?.raw_response))}
	                  className="mt-2 rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-[10px] font-semibold hover:bg-white/10"
	                >
	                  Copy
	                </button>
	              </div>
	            </div>
	          </div>

	          <div className="lg:col-span-2 rounded-2xl border border-white/10 bg-white/5 p-3">
	            <div className="text-[10px] uppercase tracking-wider text-[var(--tg-theme-hint-color)]">Params</div>
	            <pre className="mt-2 max-h-[320px] overflow-auto whitespace-pre rounded-xl border border-white/10 bg-black/20 p-2 text-[11px] leading-snug">
	              {toPrettyJson(details?.params ?? modalHeader?.params)}
	            </pre>
	          </div>
	        </div>
	      </Modal>
	    </div>
	  );
}
