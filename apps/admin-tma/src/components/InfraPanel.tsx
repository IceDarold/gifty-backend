"use client";

import { Cpu, Layers, Server } from "lucide-react";

interface InfraPanelProps {
    workers?: any[];
    queue?: any;
}

export function InfraPanel({ workers, queue }: InfraPanelProps) {
    const workerList = Array.isArray(workers) ? workers : [];
    const queueData = queue || {};

    return (
        <div className="px-4 py-2 space-y-3">
            <h3 className="text-xs font-black uppercase tracking-wider text-[var(--tg-theme-hint-color)] px-1">
                Infrastructure
            </h3>

            <div className="grid grid-cols-2 gap-3">
                <div className="card">
                    <div className="flex items-center gap-2 text-[var(--tg-theme-hint-color)] text-[10px] uppercase font-bold">
                        <Server size={14} />
                        Workers
                    </div>
                    <div className="text-2xl font-black mt-2">{workerList.length}</div>
                </div>
                <div className="card">
                    <div className="flex items-center gap-2 text-[var(--tg-theme-hint-color)] text-[10px] uppercase font-bold">
                        <Layers size={14} />
                        Queue Ready
                    </div>
                    <div className="text-2xl font-black mt-2">{queueData.messages_ready || 0}</div>
                </div>
            </div>

            <div className="card space-y-2">
                <div className="text-[10px] uppercase font-bold text-[var(--tg-theme-hint-color)]">Active Workers</div>
                {workerList.length === 0 ? (
                    <div className="text-xs text-[var(--tg-theme-hint-color)]">No active worker heartbeat</div>
                ) : (
                    workerList.slice(0, 6).map((w: any, idx: number) => (
                        <div key={`${w.hostname || "worker"}-${idx}`} className="flex items-center justify-between text-xs">
                            <span className="font-semibold truncate max-w-[45%]">{w.hostname || "worker"}</span>
                            <div className="flex items-center gap-2 text-[var(--tg-theme-hint-color)]">
                                <span className="inline-flex items-center gap-1">
                                    <Cpu size={12} />
                                    {w.cpu_usage_pct ?? 0}%
                                </span>
                                <span>{w.concurrent_tasks ?? 0} tasks</span>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}
