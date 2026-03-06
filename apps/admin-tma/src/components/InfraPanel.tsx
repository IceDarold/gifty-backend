"use client";

import React from "react";
import { Cpu, Layers, Timer } from "lucide-react";

type InfraPanelProps = {
  workers?: any[];
  queue?: any;
};

export function InfraPanel({ workers, queue }: InfraPanelProps) {
  const workerCount = Array.isArray(workers) ? workers.length : 0;
  const queueTotal = Number(queue?.messages_total ?? queue?.messages ?? queue?.total ?? 0) || 0;
  const queueReady = Number(queue?.messages_ready ?? queue?.ready ?? 0) || 0;
  const queueUnacked = Number(queue?.messages_unacked ?? queue?.unacked ?? 0) || 0;
  const updatedAt = queue?.updated_at || queue?.ts || null;

  return (
    <div className="p-4">
      <div className="card">
        <div className="flex items-center justify-between gap-3">
          <h3 className="font-black text-sm tracking-tight text-white/90">Infrastructure</h3>
          {updatedAt ? (
            <div className="text-[10px] text-[var(--tg-theme-hint-color)]">updated: {String(updatedAt).slice(0, 19)}</div>
          ) : null}
        </div>

        <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <Tile icon={<Cpu size={16} />} label="Workers" value={String(workerCount)} />
          <Tile icon={<Layers size={16} />} label="Queue total" value={String(queueTotal)} />
          <Tile icon={<Timer size={16} />} label="Ready" value={String(queueReady)} />
          <Tile icon={<Timer size={16} />} label="Unacked" value={String(queueUnacked)} />
        </div>
      </div>
    </div>
  );
}

function Tile({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3 flex items-center gap-2">
      <div className="w-9 h-9 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center text-white/80">
        {icon}
      </div>
      <div className="min-w-0">
        <div className="text-[10px] uppercase tracking-[0.14em] text-[var(--tg-theme-hint-color)]">{label}</div>
        <div className="text-base font-black text-white/90 truncate">{value}</div>
      </div>
    </div>
  );
}

