"use client";

import { useState } from "react";
import { useLanguage } from "@/contexts/LanguageContext";
import { ChevronRight, TrendingUp, Clock, Calendar, AlertCircle, CheckCircle2, Loader2 } from "lucide-react";
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
}

export function CategoriesTable({ sources, onOpenDetail, onOpenChart }: CategoriesTableProps) {
    const { t, language } = useLanguage();
    const locale = language === 'ru' ? ru : enUS;

    if (!sources || sources.length === 0) {
        return (
            <div className="p-8 text-center">
                <p className="text-[var(--tg-theme-hint-color)]">{t('common.no_data')}</p>
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
                return <AlertCircle size={16} className="text-red-500" />;
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
            const now = new Date();

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
        <div className="px-4 pb-4">
            <div className="card overflow-hidden">
                <div className="p-4 border-b border-[var(--tg-theme-hint-color)]/10">
                    <h3 className="font-bold text-lg">{t('categories.title')}</h3>
                    <p className="text-xs text-[var(--tg-theme-hint-color)] mt-1">
                        {t('categories.subtitle', { count: sources.length })}
                    </p>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead className="bg-[var(--tg-theme-secondary-bg-color)] text-xs">
                            <tr>
                                <th className="text-left p-3 font-semibold">{t('categories.category')}</th>
                                <th className="text-center p-3 font-semibold">{t('categories.products')}</th>
                                <th className="text-center p-3 font-semibold">{t('categories.status')}</th>
                                <th className="text-left p-3 font-semibold">{t('categories.last_run')}</th>
                                <th className="text-left p-3 font-semibold">{t('categories.next_run')}</th>
                                <th className="text-center p-3 font-semibold">{t('categories.actions')}</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-[var(--tg-theme-hint-color)]/10">
                            {sources.map((source) => (
                                <tr
                                    key={source.id}
                                    className="hover:bg-[var(--tg-theme-secondary-bg-color)]/50 transition-colors cursor-pointer group"
                                    onClick={() => onOpenDetail(source.id)}
                                >
                                    <td className="p-3">
                                        <div className="flex flex-col gap-1">
                                            <span className="font-medium text-sm">
                                                {source.config?.discovery_name || source.site_key}
                                            </span>
                                            <span className="text-xs text-[var(--tg-theme-hint-color)] truncate max-w-[200px]">
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
                                            <span className="text-xs">
                                                {getStatusText(source.status, source.is_active)}
                                            </span>
                                        </div>
                                    </td>

                                    <td className="p-3">
                                        <div className="flex flex-col gap-1">
                                            <span className="text-xs text-[var(--tg-theme-hint-color)]">
                                                {formatTimeAgo(source.last_synced_at)}
                                            </span>
                                            {source.last_synced_at && (
                                                <span className="text-[10px] text-[var(--tg-theme-hint-color)]/60">
                                                    {new Date(source.last_synced_at).toLocaleString(language)}
                                                </span>
                                            )}
                                        </div>
                                    </td>

                                    <td className="p-3">
                                        <div className="flex flex-col gap-1">
                                            <span className="text-xs font-medium">
                                                {formatNextRun(source.next_sync_at)}
                                            </span>
                                            <span className="text-[10px] text-[var(--tg-theme-hint-color)]/60">
                                                {new Date(source.next_sync_at).toLocaleString(language)}
                                            </span>
                                        </div>
                                    </td>

                                    <td className="p-3">
                                        <div className="flex items-center justify-center gap-2">
                                            <button
                                                onClick={() => onOpenChart(source.id)}
                                                className="p-2 rounded-lg hover:bg-[var(--tg-theme-button-color)]/10 transition-colors"
                                                title={t('categories.view_chart')}
                                            >
                                                <TrendingUp size={16} className="text-[var(--tg-theme-button-color)]" />
                                            </button>
                                            <button
                                                onClick={() => onOpenDetail(source.id)}
                                                className="p-2 rounded-lg hover:bg-[var(--tg-theme-button-color)]/10 transition-colors"
                                                title={t('categories.view_details')}
                                            >
                                                <ChevronRight size={16} className="text-[var(--tg-theme-button-color)]" />
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
