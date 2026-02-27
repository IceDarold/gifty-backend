"use client";

import React from 'react';
import { Brain, CreditCard, Layers, Zap, ArrowRight, Activity, Loader2 } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { fetchIntelligence } from '@/lib/api';
import { useLanguage } from '@/contexts/LanguageContext';
import { ApiServerErrorBanner } from '@/components/ApiServerErrorBanner';
import { useOpsRuntimeSettings } from '@/contexts/OpsRuntimeSettingsContext';

export function Intelligence() {
    const { t } = useLanguage();
    const { getIntervalMs } = useOpsRuntimeSettings();
    const { data: stats, isLoading, error, refetch } = useQuery({
        queryKey: ['intelligence'],
        queryFn: () => fetchIntelligence(7),
        refetchInterval: (query) => (query.state.error ? false : getIntervalMs('intelligence.summary_ms', 300000)),
    });

    if (isLoading) return (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
            <Loader2 className="animate-spin text-[var(--tg-theme-button-color)]" size={32} />
            <p className="text-sm text-[var(--tg-theme-hint-color)]">Analyzing AI performance...</p>
        </div>
    );

    if (error || !stats) {
        return (
            <div className="px-4 py-6">
                <ApiServerErrorBanner
                    errors={[error]}
                    onRetry={async () => {
                        await refetch();
                    }}
                    title="AI Intelligence API временно недоступен"
                />
            </div>
        );
    }

    const { metrics, providers, latency_heatmap } = stats;

    return (
        <div className="space-y-6 px-4 animate-in fade-in duration-500">
            {/* Header Section */}
            <div className="pt-2">
                <h2 className="text-xl font-bold flex items-center gap-2">
                    <Brain className="text-[var(--tg-theme-button-color)]" size={24} />
                    AI Intelligence
                </h2>
                <p className="text-[var(--tg-theme-hint-color)] text-xs mt-1">LLM performance, latency and cost tracking</p>
            </div>

            {/* AI Cost Tracker Card */}
            <div className="bg-gradient-to-br from-[#2481cc] to-[#5288c1] p-5 rounded-2xl text-white shadow-xl relative overflow-hidden">
                <div className="absolute top-0 right-0 p-4 opacity-10">
                    <CreditCard size={100} />
                </div>

                <div className="relative z-10">
                    <div className="flex items-center gap-2 text-white/70 text-[10px] uppercase font-bold tracking-widest mb-3">
                        <Zap size={14} className="text-yellow-300" />
                        Usage Efficiency
                    </div>

                    <div className="flex flex-col">
                        <span className="text-4xl font-black">
                            ${(metrics?.total_cost || 0).toFixed(2)}
                        </span>
                        <span className="text-white/70 text-xs mt-1">Total spend in last 7 days</span>
                    </div>

                    <div className="grid grid-cols-2 gap-3 mt-6">
                        <div className="bg-white/10 backdrop-blur-sm p-3 rounded-xl border border-white/10">
                            <div className="text-[10px] text-white/60 uppercase font-bold mb-0.5">Tokens</div>
                            <div className="text-lg font-bold">{((metrics?.total_tokens || 0) / 1000).toFixed(1)}k</div>
                        </div>
                        <div className="bg-white/10 backdrop-blur-sm p-3 rounded-xl border border-white/10">
                            <div className="text-[10px] text-white/60 uppercase font-bold mb-0.5">Requests</div>
                            <div className="text-lg font-bold">{metrics?.total_requests || 0}</div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Provider Distribution Card */}
            <div className="card space-y-4">
                <h3 className="font-bold flex items-center gap-2 text-sm">
                    <Layers size={16} className="text-[var(--tg-theme-button-color)]" />
                    Provider Distribution
                </h3>

                <div className="space-y-5">
                    {providers?.map((p: any) => {
                        const pct = (p.count / metrics.total_requests) * 100;
                        return (
                            <div key={p.provider} className="space-y-2">
                                <div className="flex justify-between text-xs font-bold">
                                    <span className="capitalize">{p.provider}</span>
                                    <span className="text-[var(--tg-theme-hint-color)]">{p.count} calls</span>
                                </div>
                                <div className="h-2 w-full bg-[var(--tg-theme-secondary-bg-color)] rounded-full overflow-hidden">
                                    <div
                                        className="h-full bg-gradient-to-r from-[#2481cc] to-[#64b5ef] rounded-full transition-all duration-1000"
                                        style={{ width: `${pct}%` }}
                                    ></div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Latency Heatmap Card */}
            <div className="card space-y-4">
                <h3 className="font-bold flex items-center gap-2 text-sm">
                    <Activity size={16} className="text-emerald-500" />
                    Latency Heatmap (24h)
                </h3>

                <div className="grid grid-cols-6 gap-2">
                    {Array.from({ length: 24 }).map((_, i) => {
                        const hdata = latency_heatmap?.find((h: any) => h.hour === i);
                        const latency = hdata ? hdata.avg_latency : 0;

                        let color = "bg-[var(--tg-theme-secondary-bg-color)] border-transparent";
                        if (latency > 0) {
                            if (latency < 1000) color = "bg-emerald-500/30 border-emerald-500/20";
                            else if (latency < 2500) color = "bg-amber-500/30 border-amber-500/20";
                            else color = "bg-red-500/30 border-red-500/20";
                        }

                        return (
                            <div
                                key={i}
                                className={`h-11 rounded-xl border flex flex-col items-center justify-center transition-all ${color}`}
                            >
                                <span className="text-[9px] font-bold opacity-60">{i}</span>
                                {latency > 0 && (
                                    <span className="text-[8px] font-black leading-none">
                                        {(latency / 1000).toFixed(1)}s
                                    </span>
                                )}
                            </div>
                        );
                    })}
                </div>
                <div className="flex justify-between items-center text-[10px] text-[var(--tg-theme-hint-color)] font-bold px-1 pt-1">
                    <span>00:00</span>
                    <ArrowRight size={10} />
                    <span>23:00</span>
                </div>
            </div>

            <div className="bg-[var(--tg-theme-button-color)]/5 border border-[var(--tg-theme-button-color)]/10 p-4 rounded-2xl flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-[var(--tg-theme-button-color)]/20 flex items-center justify-center text-[var(--tg-theme-button-color)]">
                    <Zap size={20} />
                </div>
                <div>
                    <div className="text-xs font-bold text-[var(--tg-theme-button-color)]">AI Efficiency Tip</div>
                    <p className="text-[10px] text-[var(--tg-theme-hint-color)] mt-0.5">Claude remains the most efficient for complex reasoning tasks this week.</p>
                </div>
            </div>
        </div>
    );
}
