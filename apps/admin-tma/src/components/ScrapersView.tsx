"use client";

import { useState } from "react";
import { useLanguage } from "@/contexts/LanguageContext";
import { ChevronRight, TrendingUp, Clock, AlertCircle, CheckCircle2, Loader2, Play, Trash2, RefreshCcw, PlayCircle } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { ru, enUS } from "date-fns/locale";

interface ScraperData {
    id: number;
    site_key: string;
    url: string;
    status: string;
    last_synced_at: string | null;
    next_sync_at: string;
    total_items: number;
    is_active: boolean;
    config?: {
        discovery_name?: string;
    };
}

interface ScrapersViewProps {
    sources?: ScraperData[];
    onOpenDetail: (id: number) => void;
    onRunOne: (id: number) => void;
    onDeleteData: (id: number) => void;
    onRunAll: () => void;
    onSync: () => void;
    isSyncing: boolean;
    isRunningAll: boolean;
    isRunningOne: boolean;
    isDeleting: boolean;
}

export function ScrapersView({
    sources,
    onOpenDetail,
    onRunOne,
    onDeleteData,
    onRunAll,
    onSync,
    isSyncing,
    isRunningAll,
    isRunningOne,
    isDeleting
}: ScrapersViewProps) {
    const { t, language } = useLanguage();
    const locale = language === 'ru' ? ru : enUS;
    const [actionId, setActionId] = useState<number | null>(null);

    if (!sources || sources.length === 0) {
        return (
            <div className="p-8 text-center space-y-4">
                <p className="text-[var(--tg-theme-hint-color)]">{t('spiders.no_spiders')}</p>
                <button
                    onClick={onSync}
                    disabled={isSyncing}
                    className="button-primary px-6 py-2 rounded-xl text-sm font-bold flex items-center gap-2 mx-auto"
                >
                    <RefreshCcw size={16} className={isSyncing ? 'animate-spin' : ''} />
                    {t('spiders.sync_now')}
                </button>
            </div>
        );
    }

    // Filter to show only unique sites (hubs preferred)
    const uniqueSites = sources.reduce((acc: ScraperData[], current) => {
        const existing = acc.find(s => s.site_key === current.site_key);
        if (!existing) {
            acc.push(current);
        } else if (current.status !== 'discovered') {
            const index = acc.indexOf(existing);
            acc[index] = current;
        }
        return acc;
    }, []);

    const getStatusIcon = (status: string, isActive: boolean) => {
        if (!isActive) return <AlertCircle size={14} className="text-gray-400" />;
        switch (status) {
            case "running": return <Loader2 size={14} className="text-blue-500 animate-spin" />;
            case "waiting": return <CheckCircle2 size={14} className="text-green-500" />;
            case "error":
            case "broken": return <AlertCircle size={14} className="text-red-500" />;
            default: return <Clock size={14} className="text-gray-400" />;
        }
    };

    const formatTimeAgo = (dateString: string | null) => {
        if (!dateString) return t('categories.never');
        try {
            return formatDistanceToNow(new Date(dateString), {
                addSuffix: true,
                locale
            });
        } catch {
            return t('categories.unknown');
        }
    };

    const handleRunClick = (e: React.MouseEvent, id: number) => {
        e.stopPropagation();
        onRunOne(id);
    };

    const handleDeleteClick = (e: React.MouseEvent, id: number) => {
        e.stopPropagation();
        if (confirm(t('common.confirm_delete_data') || 'Are you sure you want to delete all scraped data for this site?')) {
            onDeleteData(id);
        }
    };

    return (
        <div className="px-4 pb-24 space-y-4">
            {/* Header Actions */}
            <div className="flex items-center justify-between gap-3 pt-2">
                <div className="flex items-center gap-2">
                    <button
                        onClick={onSync}
                        disabled={isSyncing}
                        className="glass px-3 py-2 rounded-xl text-xs font-bold flex items-center gap-2 active:scale-95 transition-all text-[var(--tg-theme-button-color)]"
                    >
                        <RefreshCcw size={14} className={isSyncing ? 'animate-spin' : ''} />
                        {isSyncing ? t('spiders.syncing') : t('spiders.sync_now')}
                    </button>
                </div>

                <button
                    onClick={onRunAll}
                    disabled={isRunningAll}
                    className="bg-[var(--tg-theme-button-color)] text-white px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-2 active:scale-95 transition-all shadow-lg shadow-[var(--tg-theme-button-color)]/20"
                >
                    {isRunningAll ? <Loader2 size={14} className="animate-spin" /> : <PlayCircle size={14} />}
                    {isRunningAll ? 'Running...' : 'Run All'}
                </button>
            </div>

            <div className="card overflow-hidden border border-white/5 shadow-xl">
                <div className="p-4 border-b border-white/5 bg-white/5 flex items-center justify-between">
                    <div>
                        <h3 className="font-black text-sm uppercase tracking-wider">{t('common.scrapers')}</h3>
                        <p className="text-[10px] opacity-50">{uniqueSites.length} {t('spiders.connected_spiders')}</p>
                    </div>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                        <thead className="bg-white/5 text-[10px] uppercase font-black text-[var(--tg-theme-hint-color)]">
                            <tr>
                                <th className="p-4">{t('categories.category')}</th>
                                <th className="p-4 text-center">{t('categories.products')}</th>
                                <th className="p-4 text-center">{t('categories.status')}</th>
                                <th className="p-4">{t('categories.last_run')}</th>
                                <th className="p-4 text-center">{t('categories.actions')}</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5">
                            {uniqueSites.map((source) => (
                                <tr
                                    key={source.id}
                                    className="hover:bg-white/5 transition-colors cursor-pointer group"
                                    onClick={() => onOpenDetail(source.id)}
                                >
                                    <td className="p-4">
                                        <div className="flex flex-col gap-1">
                                            <span className="font-bold text-sm group-hover:text-[var(--tg-theme-button-color)] transition-colors">
                                                {source.config?.discovery_name || source.site_key}
                                            </span>
                                            <span className="text-[10px] opacity-40 uppercase font-bold letter-spacing-wider">
                                                {source.site_key}
                                            </span>
                                        </div>
                                    </td>

                                    <td className="p-4 text-center">
                                        <span className="bg-[var(--tg-theme-button-color)]/10 text-[var(--tg-theme-button-color)] px-2 py-1 rounded-lg font-black text-xs">
                                            {(source.total_items || 0).toLocaleString()}
                                        </span>
                                    </td>

                                    <td className="p-4">
                                        <div className="flex items-center justify-center">
                                            {getStatusIcon(source.status, source.is_active)}
                                        </div>
                                    </td>

                                    <td className="p-4">
                                        <span className="text-xs opacity-70 whitespace-nowrap">
                                            {formatTimeAgo(source.last_synced_at)}
                                        </span>
                                    </td>

                                    <td className="p-4">
                                        <div className="flex items-center justify-center gap-2">
                                            <button
                                                onClick={(e) => handleRunClick(e, source.id)}
                                                disabled={isRunningOne || isRunningAll || !source.is_active}
                                                className="p-2 rounded-lg bg-green-500/10 text-green-500 hover:bg-green-500/20 active:scale-95 transition-all disabled:opacity-30"
                                                title="Run Now"
                                            >
                                                <Play size={14} fill="currentColor" />
                                            </button>
                                            <button
                                                onClick={(e) => handleDeleteClick(e, source.id)}
                                                disabled={isDeleting}
                                                className="p-2 rounded-lg bg-red-500/10 text-red-500 hover:bg-red-500/20 active:scale-95 transition-all disabled:opacity-30"
                                                title="Clear Data"
                                            >
                                                <Trash2 size={14} />
                                            </button>
                                            <button
                                                onClick={() => onOpenDetail(source.id)}
                                                className="p-2 rounded-lg bg-white/5 group-hover:bg-[var(--tg-theme-button-color)] group-hover:text-white transition-all active:scale-95"
                                            >
                                                <ChevronRight size={14} />
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
