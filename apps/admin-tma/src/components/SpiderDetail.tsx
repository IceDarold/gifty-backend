"use client";

import { X, Play, Power, Terminal, Calendar, Package, TrendingUp, Loader2 } from "lucide-react";
import { useSourceDetails } from "@/hooks/useDashboard";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { useLanguage } from "@/contexts/LanguageContext";

interface SpiderDetailProps {
    sourceId: number;
    onClose: () => void;
    onForceRun: (id: number, strategy: string) => void;
    isForceRunning: boolean;
}

export function SpiderDetail({ sourceId, onClose, onForceRun, isForceRunning }: SpiderDetailProps) {
    const { data: source, isLoading } = useSourceDetails(sourceId);
    const { t } = useLanguage();

    if (isLoading || !source) {
        return (
            <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-300">
                <div className="bg-[var(--tg-theme-bg-color)] p-8 rounded-2xl flex flex-col items-center gap-4">
                    <Loader2 className="animate-spin text-[var(--tg-theme-button-color)]" size={32} />
                    <p className="text-sm">{t('spiders.loading_details')}</p>
                </div>
            </div>
        );
    }

    const history = source.history || [];
    const lastLogs = source.config?.last_logs || t('spiders.no_logs');

    return (
        <div className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-300">
            <div className="bg-[var(--tg-theme-bg-color)] w-full max-w-lg rounded-t-3xl sm:rounded-3xl overflow-hidden shadow-2xl animate-in slide-in-from-bottom duration-300">
                {/* Header */}
                <div className="p-5 border-b border-[var(--tg-theme-secondary-bg-color)] flex items-center justify-between bg-gradient-to-r from-[var(--tg-theme-secondary-bg-color)] to-[var(--tg-theme-bg-color)]">
                    <div>
                        <h2 className="font-bold text-xl">{source.site_key || source.name}</h2>
                        <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full ${source.status === 'running' ? 'bg-blue-500/20 text-blue-500' :
                            source.status === 'broken' ? 'bg-red-500/20 text-red-500' :
                                'bg-green-500/20 text-green-500'
                            }`}>
                            {source.status}
                        </span>
                    </div>
                    <button onClick={onClose} className="p-2 rounded-full hover:bg-black/5 transition-colors">
                        <X size={20} />
                    </button>
                </div>

                <div className="overflow-y-auto max-h-[80vh] p-5 space-y-6 pb-10">
                    {/* Stats Grid */}
                    <div className="grid grid-cols-2 gap-3">
                        <div className="card p-3 flex flex-col gap-1">
                            <div className="flex items-center gap-2 text-[var(--tg-theme-hint-color)]">
                                <Package size={14} />
                                <span className="text-[10px] font-bold uppercase">{t('spiders.total_items')}</span>
                            </div>
                            <p className="text-xl font-bold">{(source.total_items || 0).toLocaleString()}</p>
                        </div>
                        <div className="card p-3 flex flex-col gap-1">
                            <div className="flex items-center gap-2 text-[var(--tg-theme-hint-color)]">
                                <TrendingUp size={14} />
                                <span className="text-[10px] font-bold uppercase">{t('spiders.last_sync')}</span>
                            </div>
                            <p className="text-xl font-bold">+{source.last_run_new || 0}</p>
                        </div>
                        <div className="col-span-2 card p-3 flex items-center gap-3">
                            <Calendar size={18} className="text-[var(--tg-theme-button-color)]" />
                            <div>
                                <span className="text-[10px] font-bold uppercase text-[var(--tg-theme-hint-color)]">{t('spiders.next_schedule')}</span>
                                <p className="text-sm font-medium">
                                    {new Date(source.next_sync_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}
                                </p>
                            </div>
                        </div>
                    </div>

                    {/* Chart */}
                    {history.length > 0 && (
                        <div className="space-y-3">
                            <h3 className="text-sm font-bold flex items-center gap-2 px-1">
                                <TrendingUp size={16} className="text-green-500" />
                                {t('spiders.scraping_trends')} (15d)
                            </h3>
                            <div className="h-40 w-full card p-2">
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={[...history].reverse()} margin={{ top: 5, right: 5, left: -25, bottom: 20 }}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--tg-theme-hint-color)" strokeOpacity={0.1} />
                                        <XAxis
                                            dataKey="date"
                                            axisLine={false}
                                            tickLine={false}
                                            tick={{ fill: 'var(--tg-theme-hint-color)', fontSize: 9 }}
                                        />
                                        <YAxis
                                            axisLine={false}
                                            tickLine={false}
                                            tick={{ fill: 'var(--tg-theme-hint-color)', fontSize: 9 }}
                                        />
                                        <Tooltip
                                            contentStyle={{
                                                backgroundColor: 'var(--tg-theme-secondary-bg-color)',
                                                border: 'none',
                                                borderRadius: '12px',
                                                fontSize: '12px'
                                            }}
                                        />
                                        <Line
                                            type="monotone"
                                            dataKey="items_new"
                                            stroke="var(--tg-theme-button-color)"
                                            strokeWidth={3}
                                            dot={false}
                                        />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    )}

                    {/* Logs */}
                    <div className="space-y-3">
                        <h3 className="text-sm font-bold flex items-center gap-2 px-1">
                            <Terminal size={16} className="text-blue-500" />
                            {t('spiders.live_logs')}
                        </h3>
                        <div className="bg-black text-[#00ff00] font-mono text-[10px] p-4 rounded-xl overflow-x-auto h-40 border border-white/5 shadow-inner">
                            <pre className="whitespace-pre-wrap">{lastLogs}</pre>
                        </div>
                    </div>

                    {/* Actions */}
                    <div className="flex gap-2 pt-2">
                        <button
                            onClick={() => onForceRun(sourceId, "deep")}
                            disabled={isForceRunning}
                            className="flex-1 bg-[var(--tg-theme-button-color)] text-white py-3 rounded-xl font-bold flex items-center justify-center gap-2 active:scale-95 transition-all disabled:opacity-50"
                        >
                            <Play size={18} fill="white" />
                            {t('spiders.run_deep')}
                        </button>
                        <button
                            onClick={() => onForceRun(sourceId, "discovery")}
                            disabled={isForceRunning}
                            className="flex-1 border-2 border-[var(--tg-theme-button-color)] text-[var(--tg-theme-button-color)] py-3 rounded-xl font-bold flex items-center justify-center gap-2 active:scale-95 transition-all disabled:opacity-50"
                        >
                            <TrendingUp size={18} />
                            {t('spiders.run_discovery')}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
