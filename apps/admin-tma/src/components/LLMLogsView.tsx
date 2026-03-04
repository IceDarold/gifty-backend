"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, Clock, Filter, RefreshCcw } from "lucide-react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { ApiServerErrorBanner } from "@/components/ApiServerErrorBanner";
import { fetchLLMLogs, fetchLLMThroughput } from "@/lib/api";
import { useOpsRuntimeSettings } from "@/contexts/OpsRuntimeSettingsContext";

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
  const [days, setDays] = useState<number>(7);
  const [bucket, setBucket] = useState<Bucket>("hour");
  const [status, setStatus] = useState<string>("");
  const [provider, setProvider] = useState<string>("");
  const [callType, setCallType] = useState<string>("");
  const [offset, setOffset] = useState<number>(0);
  const limit = 50;

  const logsQuery = useQuery({
    queryKey: ["llm-logs", { days, bucket, status, provider, callType, offset, limit }],
    queryFn: () =>
      fetchLLMLogs({
        days,
        limit,
        offset,
        status: status || undefined,
        provider: provider || undefined,
        call_type: callType || undefined,
      }),
    refetchInterval: (q) => (q.state.error ? false : getIntervalMs("intelligence.summary_ms", 300000)),
  });

  const throughputQuery = useQuery({
    queryKey: ["llm-throughput", { days, bucket, status, provider, callType }],
    queryFn: () =>
      fetchLLMThroughput({
        days,
        bucket,
        status: status || undefined,
        provider: provider || undefined,
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

  const total = Number(logsQuery.data?.total || 0);
  const items = Array.isArray(logsQuery.data?.items) ? logsQuery.data.items : [];
  const hasPrev = offset > 0;
  const hasNext = offset + limit < total;

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
        errors={[logsQuery.error, throughputQuery.error]}
        onRetry={async () => {
          await Promise.allSettled([logsQuery.refetch(), throughputQuery.refetch()]);
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
              void Promise.allSettled([logsQuery.refetch(), throughputQuery.refetch()]);
            }}
            className="inline-flex items-center gap-2 rounded-xl bg-white/5 px-3 py-2 text-xs font-bold border border-white/10 hover:bg-white/10 active:scale-95 transition-all"
          >
            <RefreshCcw size={14} className="text-[var(--tg-theme-hint-color)]" />
            Refresh
          </button>
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-5 gap-2">
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
                  <tr key={it.id} className="border-b border-white/5 hover:bg-white/5 transition-colors">
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
    </div>
  );
}

