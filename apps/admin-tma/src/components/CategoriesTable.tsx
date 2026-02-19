"use client";

import { useState } from "react";
import { useLanguage } from "@/contexts/LanguageContext";
import { ChevronRight, TrendingUp, Clock, Calendar, AlertCircle, CheckCircle2, Loader2, Play, PlayCircle, RefreshCcw } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { ru, enUS } from "date-fns/locale";

interface CategoryData {
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

interface CategoriesTableProps {
    sources?: CategoryData[];
    onOpenDetail: (id: number) => void;
    onOpenChart: (id: number) => void;
    // Scraper control props
    onSync?: () => void;
    isSyncing?: boolean;
    onRunAll?: () => void;
    isRunningAll?: boolean;
    onRunOne?: (id: number) => void;
    isRunningOne?: boolean;
}

export function CategoriesTable({
    sources,
    onOpenDetail,
    onOpenChart,
    onSync,
    isSyncing,
    onRunAll,
    isRunningAll,
    onRunOne,
    isRunningOne
}: CategoriesTableProps) {
    const { t, language } = useLanguage();
    const locale = language === 'ru' ? ru : enUS;
    const [runningId, setRunningId] = useState<number | null>(null);

    const handleRunOne = (id: number) => {
        if (!onRunOne || isRunningOne) return;
        setRunningId(id);
        onRunOne(id);
        setTimeout(() => setRunningId(null), 5000);
    };

    if (!sources || sources.length === 0) {
        return (
            <div className="p-8 text-center bg-card rounded-lg border border-[var(--tg-theme-hint-color)]/10">
                <p className="text-[var(--tg-theme-hint-color)] mb-4">{t('common.no_data')}</p>
                {onSync && (
                    <button
                        onClick={onSync}
                        disabled={isSyncing}
                        className={`text-sm font-bold px-4 py-2 rounded-full border border-[var(--tg-theme-button-color)] text-[var(--tg-theme-button-color)] inline-flex items-center gap-2 transition-all active:scale-95 ${isSyncing ? 'opacity-50' : ''}`}
                    >
                        <RefreshCcw size={14} className={isSyncing ? 'animate-spin' : ''} />
                        {isSyncing ? t('spiders.syncing') : t('spiders.sync_now')}
                    </button>
                )}
            </div>
        );
    }

    const getStatusIcon = (status: string, isActive: boolean) => {
        if (!isActive) {
            return <AlertCircle size={16} className="text-gray-400" />;
        }

        switch (status) {
            case "running":
                return <Loader2 size={16} className="text-blue-500 animate-spin" />;
            case "waiting":
                return <CheckCircle2 size={16} className="text-green-500" />;
            case "error":
            case "broken":
                return <AlertCircle size={16} className="text-red-500 animate-pulse" />;
            default:
                return <Clock size={16} className="text-gray-400" />;
        }
    };

    const getStatusText = (status: string, isActive: boolean) => {
        if (!isActive) return t('categories.status_disabled');

        switch (status) {
            case "running":
                return t('categories.status_running');
            case "waiting":
                return t('categories.status_waiting');
            case "error":
                return t('categories.status_error');
            case "broken":
                return t('categories.status_broken');
            default:
                return status;
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

    const formatNextRun = (dateString: string) => {
        try {
            const date = new Date(dateString);
            const now = new Date(); // Use local time comparison

            // If date is invalid
            if (isNaN(date.getTime())) return t('categories.unknown');

            if (date < now) {
                return t('categories.scheduled_now');
            }

            return formatDistanceToNow(date, {
                addSuffix: true,
                locale
            });
        } catch {
            return t('categories.unknown');
        }
    };

    return (
        <div className="px-4 pb-4 space-y-4">
            {/* Header with Run All/Sync Controls */}
            <div className="flex items-center justify-between">
                <div>
                    {/* Renamed to Parsers per request */}
                    <h3 className="font-bold text-lg">Parsers</h3>
                    <p className="text-xs text-[var(--tg-theme-hint-color)] mt-1">
                        {t('categories.subtitle', { count: sources.length })}
                    </p>
                </div>
                <div className="flex items-center gap-2">
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

            <div className="card overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead className="bg-[var(--tg-theme-secondary-bg-color)] text-xs">
                            <tr>
                                <th className="text-left p-3 font-semibold">{t('categories.category')}</th>
                                <th className="text-center p-3 font-semibold">{t('categories.products')}</th>
                                <th className="text-center p-3 font-semibold">{t('categories.status')}</th>
                                <th className="text-left p-3 font-semibold hidden sm:table-cell">{t('categories.last_run')}</th>
                                <th className="text-center p-3 font-semibold">{t('categories.actions')}</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-[var(--tg-theme-hint-color)]/10">
                            {sources.map((source) => {
                                const isThisRunning = runningId === source.id;
                                const hasError = source.status === 'error' || source.status === 'broken';

                                return (
                                    <tr
                                        key={source.id}
                                        className={`hover:bg-[var(--tg-theme-secondary-bg-color)]/50 transition-colors cursor-pointer group ${hasError ? 'bg-red-500/5' : ''}`}
                                        onClick={() => onOpenDetail(source.id)}
                                    >
                                        <td className="p-3">
                                            <div className="flex flex-col gap-1">
                                                <span className="font-medium text-sm">
                                                    {source.config?.discovery_name || source.site_key}
                                                </span>
                                                <span className="text-xs text-[var(--tg-theme-hint-color)] truncate max-w-[150px]">
                                                    {source.site_key}
                                                </span>
                                            </div>
                                        </td>

                                        <td className="p-3 text-center">
                                            <div className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-[var(--tg-theme-button-color)]/10">
                                                <span className="font-bold text-sm text-[var(--tg-theme-button-color)]">
                                                    {source.total_items?.toLocaleString() || 0}
                                                </span>
                                            </div>
                                        </td>

                                        <td className="p-3">
                                            <div className="flex items-center justify-center gap-2">
                                                {getStatusIcon(source.status, source.is_active)}
                                                <span className={`text-xs ${hasError ? 'text-red-500 font-medium' : ''}`}>
                                                    {getStatusText(source.status, source.is_active)}
                                                </span>
                                            </div>
                                        </td>

                                        <td className="p-3 hidden sm:table-cell">
                                            <div className="flex flex-col gap-1">
                                                <span className="text-xs text-[var(--tg-theme-hint-color)]">
                                                    {formatTimeAgo(source.last_synced_at)}
                                                </span>
                                            </div>
                                        </td>

                                        <td className="p-3">
                                            <div className="flex items-center justify-center gap-1" onClick={(e) => e.stopPropagation()}>
                                                {/* Run Button */}
                                                {onRunOne && (
                                                    <button
                                                        onClick={() => handleRunOne(source.id)}
                                                        disabled={isThisRunning || !!isRunningAll}
                                                        title={`Run ${source.site_key}`}
                                                        className={`p-2 rounded-lg transition-all active:scale-95 flex items-center justify-center hover:bg-[var(--tg-theme-button-color)]/10
                                                        ${isThisRunning ? 'text-[var(--tg-theme-button-color)]' : 'text-green-500'}
                                                        ${(isThisRunning || isRunningAll) ? 'opacity-60' : ''}`}
                                                    >
                                                        {isThisRunning
                                                            ? <Loader2 size={16} className="animate-spin" />
                                                            : <Play size={16} fill="currentColor" />
                                                        }
                                                    </button>
                                                )}

                                                <button
                                                    onClick={() => onOpenChart(source.id)}
                                                    className="p-2 rounded-lg hover:bg-[var(--tg-theme-button-color)]/10 transition-colors hidden sm:block"
                                                    title={t('categories.view_chart')}
                                                >
                                                    <TrendingUp size={16} className="text-[var(--tg-theme-button-color)]" />
                                                </button>
                                                <button
                                                    onClick={() => onOpenDetail(source.id)}
                                                    className="p-2 rounded-lg hover:bg-[var(--tg-theme-button-color)]/10 transition-colors"
                                                >
                                                    <ChevronRight size={16} className="text-[var(--tg-theme-button-color)]" />
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                )
                            })}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
