"use client";

import React from "react";
import { Activity, Database, Layers, Server } from "lucide-react";

type HealthViewProps = {
  health?: any;
  workers?: any[];
  queue?: any;
};

function Chip({ label, value, testId }: { label: string; value?: string; testId?: string }) {
  return (
    <div className="rounded-xl border border-white/12 bg-white/[0.03] px-3 py-2" data-testid={testId}>
      <div className="text-[10px] uppercase tracking-[0.14em] text-[var(--tg-theme-hint-color)]">{label}</div>
      <div className="mt-0.5 text-sm font-bold text-white/90">{value ?? "—"}</div>
    </div>
  );
}

export function HealthView({ health, workers, queue }: HealthViewProps) {
  const apiStatus = health?.api?.status ?? health?.api_status ?? "Unknown";
  const apiLatency = health?.api?.latency ?? health?.api_latency_ms ? `${health.api_latency_ms}ms` : undefined;

  const dbStatus = health?.database?.status ?? health?.db?.status ?? "Unknown";
  const dbEngine = health?.database?.engine ?? health?.db?.engine;

  const redisStatus = health?.redis?.status ?? "Unknown";
  const redisMem = health?.redis?.memory_usage ?? health?.redis?.memory;

  const workerCount = Array.isArray(workers) ? workers.length : 0;
  const queueTotal = queue?.messages_total ?? queue?.messages ?? queue?.total ?? 0;

  return (
    <div className="p-4 space-y-4" data-testid="health-view">
      <div className="card" data-testid="health-card">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Heart />
            <h2 className="font-black text-lg">System Health</h2>
          </div>
          <div className="text-[10px] uppercase tracking-[0.14em] text-[var(--tg-theme-hint-color)]">
            workers: {workerCount} • queue: {Number(queueTotal) || 0}
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <Chip label="API" value={`${apiStatus}${apiLatency ? ` · ${apiLatency}` : ""}`} testId="health-api" />
          <Chip label="Database" value={`${dbStatus}${dbEngine ? ` · ${dbEngine}` : ""}`} testId="health-db" />
          <Chip label="Redis" value={`${redisStatus}${redisMem ? ` · ${redisMem}` : ""}`} testId="health-redis" />
          <Chip label="Queue" value={String(Number(queueTotal) || 0)} testId="health-queue" />
        </div>

        <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
          <MiniStat icon={<Server size={16} />} label="API" value={String(apiStatus)} testId="health-mini-api" />
          <MiniStat icon={<Database size={16} />} label="DB" value={String(dbStatus)} testId="health-mini-db" />
          <MiniStat icon={<Layers size={16} />} label="Redis" value={String(redisStatus)} testId="health-mini-redis" />
          <MiniStat icon={<Activity size={16} />} label="Queue" value={String(Number(queueTotal) || 0)} testId="health-mini-queue" />
        </div>
      </div>
    </div>
  );
}

function MiniStat({ icon, label, value, testId }: { icon: React.ReactNode; label: string; value: string; testId?: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3 flex items-center gap-2" data-testid={testId}>
      <div className="w-8 h-8 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-white/80">
        {icon}
      </div>
      <div className="min-w-0">
        <div className="text-[10px] uppercase tracking-[0.14em] text-[var(--tg-theme-hint-color)]">{label}</div>
        <div className="text-sm font-bold text-white/90 truncate">{value}</div>
      </div>
    </div>
  );
}

function Heart() {
  return (
    <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-emerald-400/25 to-sky-400/20 border border-white/10 flex items-center justify-center">
      <Activity size={18} className="text-emerald-200" />
    </div>
  );
}
