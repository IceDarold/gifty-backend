"use client";

import { useState } from "react";
import { CheckCircle2, AlertTriangle, RefreshCcw, ExternalLink, Play, PlayCircle, Loader2 } from "lucide-react";
import { useLanguage } from "@/contexts/LanguageContext";

interface SpiderListProps {
    sources?: any[];
    onSync?: () => void;
    onOpenDetail?: (id: number) => void;
    isSyncing?: boolean;
    onRunAll?: () => void;
    isRunningAll?: boolean;
    onRunOne?: (id: number) => void;
    isRunningOne?: boolean;
}

export function SpiderList({ sources = [], onSync, onOpenDetail, isSyncing, onRunAll, isRunningAll, onRunOne, isRunningOne }: SpiderListProps) {
    const { t } = useLanguage();
    const [runningId, setRunningId] = useState<number | null>(null);

    const handleRunOne = (id: number) => {
        if (!onRunOne || isRunningOne) return;
        setRunningId(id);
        onRunOne(id);
        // Auto-clear the per-spider indicator after 5s
        setTimeout(() => setRunningId(null), 5000);
    };

    return (
        <div className="p-4 space-y-3">
            {/* Header row with title + action buttons */}
            <div className="flex items-center justify-between mb-2 gap-2 flex-wrap">
                <h2 className="font-bold text-lg">{t('spiders.connected_spiders')}</h2>
                <div className="flex items-center gap-2">
                    {/* Sync button */}
                    {onSync && (
                        <button
                            onClick={onSync}
                            disabled={isSyncing}
                            className={`text-xs font-bold px-3 py-1.5 rounded-full border border-[var(--tg-theme-button-color)] text-[var(--tg-theme-button-color)] flex items-center gap-1.5 transition-all active:scale-95 ${isSyncing ? 'opacity-50' : ''}`}
                        >
                            <RefreshCcw size={12} className={isSyncing ? 'animate-spin' : ''} />
                            {isSyncing ? t('spiders.syncing') : t('spiders.sync_now')}
                        </button>
                    )}

                    {/* Run All button */}
                    {onRunAll && (
                        <button
                            onClick={() => onRunAll()}
                            disabled={isRunningAll}
                            className={`text-xs font-bold px-3 py-1.5 rounded-full bg-[var(--tg-theme-button-color)] text-white flex items-center gap-1.5 transition-all active:scale-95 shadow-md ${isRunningAll ? 'opacity-60' : 'hover:brightness-110'}`}
                        >
                            {isRunningAll
                                ? <Loader2 size={12} className="animate-spin" />
                                : <PlayCircle size={12} />
                            }
                            {isRunningAll ? 'Running…' : 'Run All'}
                        </button>
                    )}
                </div>
            </div>

            {/* Spider rows */}
            <div className="space-y-2">
                {(() => {
                    const uniqueSites = sources.reduce((acc: any[], current) => {
                        const existing = acc.find(s => s.site_key === current.site_key);
                        if (!existing) {
                            acc.push(current);
                        } else if (current.type === 'hub') {
                            const index = acc.indexOf(existing);
                            acc[index] = current;
                        }
                        return acc;
                    }, []);

                    return uniqueSites.length > 0 ? (
                        uniqueSites.map((spider) => {
                            const isThisRunning = runningId === spider.id;
                            return (
                                <div key={spider.id} className="card flex items-center justify-between py-3 gap-2">
                                    {/* Status icon + info */}
                                    <div className="flex items-center gap-3 flex-1 min-w-0">
                                        <div className={`p-2 rounded-lg flex-shrink-0 ${spider.status === 'running' || isThisRunning
                                            ? 'bg-[#5288c1] bg-opacity-20 text-[#5288c1]'
                                            : spider.status === 'broken' || spider.config?.fix_required
                                                ? 'bg-[#ff3b30] bg-opacity-20 text-[#ff3b30]'
                                                : 'bg-[#999999] bg-opacity-20 text-[#999999]'
                                            }`}>
                                            {spider.status === 'running' || isThisRunning
                                                ? <RefreshCcw size={20} className="animate-spin" />
                                                : spider.status === 'broken' || spider.config?.fix_required
                                                    ? <AlertTriangle size={20} />
                                                    : <CheckCircle2 size={20} />}
                                        </div>
                                        <div className="min-w-0">
                                            <p className="font-bold text-sm leading-tight truncate">{spider.site_key || spider.name}</p>
                                            <p className="text-[10px] text-[var(--tg-theme-hint-color)]">
                                                {(spider.total_items || 0).toLocaleString()} {t('spiders.items')} • {spider.last_synced_at ? t('spiders.synced') : t('spiders.new')}
                                            </p>
                                        </div>
                                    </div>

                                    {/* Action buttons */}
                                    <div className="flex items-center gap-1.5 flex-shrink-0">
                                        {/* Per-spider Run button */}
                                        {onRunOne && (
                                            <button
                                                onClick={() => handleRunOne(spider.id)}
                                                disabled={isThisRunning || !!isRunningAll}
                                                title={`Run ${spider.site_key}`}
                                                className={`p-2 rounded-lg transition-all active:scale-95 flex items-center justify-center
                                                    ${isThisRunning
                                                        ? 'bg-[#5288c1] bg-opacity-20 text-[#5288c1]'
                                                        : 'bg-[#34c759] bg-opacity-15 text-[#34c759] hover:bg-opacity-30'
                                                    } ${(isThisRunning || isRunningAll) ? 'opacity-60' : ''}`}
                                            >
                                                {isThisRunning
                                                    ? <Loader2 size={15} className="animate-spin" />
                                                    : <Play size={15} fill="currentColor" />
                                                }
                                            </button>
                                        )}

                                        {/* Open detail button */}
                                        <button
                                            onClick={() => onOpenDetail?.(spider.id)}
                                            className="p-2 rounded-lg bg-[var(--tg-theme-secondary-bg-color)] group hover:bg-[var(--tg-theme-button-color)] transition-colors active:scale-95"
                                        >
                                            <ExternalLink size={16} className="text-[var(--tg-theme-hint-color)] group-hover:text-white" />
                                        </button>
                                    </div>
                                </div>
                            );
                        })
                    ) : (
                        <div className="card py-10 text-center opacity-50">
                            <p className="text-sm">{t('spiders.no_spiders')}</p>
                            <p className="text-[10px] mt-1">{t('spiders.click_sync')}</p>
                        </div>
                    );
                })()}
            </div>
        </div>
    );
}
