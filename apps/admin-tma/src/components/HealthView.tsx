"use client";

import { Activity, Database, Server, Zap } from "lucide-react";

interface HealthViewProps {
    health?: any;
    workers?: any[];
    queue?: any;
}

const statusClass = (value?: string) => {
    const v = (value || "").toLowerCase();
    if (v.includes("healthy") || v.includes("connected")) return "text-emerald-500 bg-emerald-500/10";
    if (v.includes("error")) return "text-red-500 bg-red-500/10";
    return "text-amber-500 bg-amber-500/10";
};

export function HealthView({ health, workers, queue }: HealthViewProps) {
    const workerCount = Array.isArray(workers) ? workers.length : 0;
    const queueData = queue || {};

    return (
        <div className="p-4 pb-24 space-y-4">
            <div>
                <h2 className="text-lg font-bold">System Health</h2>
                <p className="text-xs text-[var(--tg-theme-hint-color)]">Infrastructure and runtime metrics</p>
            </div>

            <div className="grid grid-cols-1 gap-3">
                <div className="card flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Server size={18} className="text-blue-500" />
                        <div>
                            <div className="text-xs font-bold">API</div>
                            <div className="text-[10px] text-[var(--tg-theme-hint-color)]">{health?.api?.latency || "N/A"}</div>
                        </div>
                    </div>
                    <span className={`px-2 py-1 rounded-md text-[10px] font-bold ${statusClass(health?.api?.status)}`}>
                        {health?.api?.status || "UNKNOWN"}
                    </span>
                </div>

                <div className="card flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Database size={18} className="text-emerald-500" />
                        <div>
                            <div className="text-xs font-bold">Database</div>
                            <div className="text-[10px] text-[var(--tg-theme-hint-color)]">{health?.database?.engine || "N/A"}</div>
                        </div>
                    </div>
                    <span className={`px-2 py-1 rounded-md text-[10px] font-bold ${statusClass(health?.database?.status)}`}>
                        {health?.database?.status || "UNKNOWN"}
                    </span>
                </div>

                <div className="card flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Zap size={18} className="text-amber-500" />
                        <div>
                            <div className="text-xs font-bold">Redis</div>
                            <div className="text-[10px] text-[var(--tg-theme-hint-color)]">{health?.redis?.memory_usage || "N/A"}</div>
                        </div>
                    </div>
                    <span className={`px-2 py-1 rounded-md text-[10px] font-bold ${statusClass(health?.redis?.status)}`}>
                        {health?.redis?.status || "UNKNOWN"}
                    </span>
                </div>

                <div className="card">
                    <div className="flex items-center gap-2 mb-3">
                        <Activity size={16} className="text-[var(--tg-theme-button-color)]" />
                        <span className="text-xs font-bold">Runtime</span>
                    </div>
                    <div className="grid grid-cols-2 gap-3 text-xs">
                        <div className="bg-[var(--tg-theme-secondary-bg-color)] rounded-lg p-2">
                            <div className="text-[10px] text-[var(--tg-theme-hint-color)] uppercase font-bold">Workers</div>
                            <div className="font-black text-lg">{workerCount}</div>
                        </div>
                        <div className="bg-[var(--tg-theme-secondary-bg-color)] rounded-lg p-2">
                            <div className="text-[10px] text-[var(--tg-theme-hint-color)] uppercase font-bold">Queue</div>
                            <div className="font-black text-lg">{queueData.messages_total || 0}</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
