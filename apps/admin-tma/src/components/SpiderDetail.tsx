import { useState, useEffect, useMemo } from "react";
import { X, Power, Package, TrendingUp, Loader2, Clock, AlertCircle, CheckCircle2, List, Settings2, Pencil } from "lucide-react";
import { useSourceDetails } from "@/hooks/useDashboard";
import { fetchOpsDiscoveryCategoryDetails, fetchOpsSites, fetchOpsSourceItemsTrend, promoteOpsDiscovery, reactivateOpsDiscovery, rejectOpsDiscovery, runOpsDiscoveryAllForSite, runOpsDiscoveryCategoryNow, runOpsSiteDiscovery } from "@/lib/api";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { useLanguage } from "@/contexts/LanguageContext";
import { SourceConfigEditor } from "./SourceConfigEditor";
import { formatDistanceToNow } from "date-fns";
import { ru, enUS } from "date-fns/locale";
import { ApiServerErrorBanner } from "@/components/ApiServerErrorBanner";
import { useQuery } from "@tanstack/react-query";
import { useOpsRuntimeSettings } from "@/contexts/OpsRuntimeSettingsContext";

interface SpiderDetailProps {
    sourceId: number;
    initialSource?: { name?: string; slug?: string; url?: string };
    onClose: () => void;
    onForceRun: (id: number, strategy: string) => void;
    onToggleActive?: (id: number, active: boolean) => void;
    onUpdateSource?: (id: number, payload: Record<string, any>) => Promise<any> | void;
    onOpenSource?: (id: number) => void;
    isForceRunning: boolean;
    isUpdatingSource?: boolean;
}

export function SpiderDetail({ sourceId, initialSource, onClose, onForceRun: _onForceRun, onToggleActive, onUpdateSource, onOpenSource: _onOpenSource, isForceRunning: _isForceRunning, isUpdatingSource }: SpiderDetailProps) {
    const CATEGORY_PAGE_SIZE = 20;
    const { data: source, isLoading, error: sourceError, refetch: refetchSource } = useSourceDetails(sourceId);

    const [activeTab, setActiveTab] = useState<'overview' | 'categories'>('overview');
    const [trendGranularity, setTrendGranularity] = useState<'week' | 'day' | 'hour' | 'minute'>('day');
    const [showConfigEditor, setShowConfigEditor] = useState(false);
    const [categorySearch, setCategorySearch] = useState("");
    const [categoryPage, setCategoryPage] = useState(0);
    const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
    const [runningDiscovery, setRunningDiscovery] = useState(false);
    const [categoryActionPending, setCategoryActionPending] = useState(false);
    const [runningCategoryIds, setRunningCategoryIds] = useState<Record<number, boolean>>({});
    const [runningAllCategories, setRunningAllCategories] = useState(false);
    const [approvingAllCategories, setApprovingAllCategories] = useState(false);
    const [isEditingName, setIsEditingName] = useState(false);
    const [isEditingUrl, setIsEditingUrl] = useState(false);
    const [nameDraft, setNameDraft] = useState("");
    const [urlDraft, setUrlDraft] = useState("");
    const [inlineSaving, setInlineSaving] = useState<"name" | "url" | null>(null);
    const [notifications, setNotifications] = useState<
        { id: string; status: "running" | "success" | "error"; title: string; message: string }[]
    >([]);
    const categoryDetails = useQuery({
        queryKey: ['ops-discovery-category', selectedCategoryId],
        queryFn: () => fetchOpsDiscoveryCategoryDetails(selectedCategoryId as number),
        enabled: !!selectedCategoryId,
    });

    useEffect(() => {
        setCategoryPage(0);
        setCategorySearch("");
    }, [sourceId]);

    const { t, language } = useLanguage();
    const { getIntervalMs } = useOpsRuntimeSettings();
    const locale = language === 'ru' ? ru : enUS;

    const sourceData = source ?? {
        id: sourceId,
        site_key: `source-${sourceId}`,
        name: `Source #${sourceId}`,
        status: "waiting",
        total_items: 0,
        last_run_new: 0,
        is_active: false,
        config: {},
        history: [],
        aggregate_history: [],
        related_sources: [],
    };
    const parserSlug = String(sourceData.site_key || initialSource?.slug || `source-${sourceId}`);
    const parserDisplayName = String(
        sourceData?.config?.site_name ||
        sourceData?.name ||
        initialSource?.name ||
        parserSlug
    ).trim() || parserSlug;
    const parserUrl = String(sourceData?.url || initialSource?.url || "").trim();

    const runHistory = sourceData.history || [];
    const trendBuckets = useMemo(() => {
        if (trendGranularity === 'week') return 12;
        if (trendGranularity === 'day') return 30;
        if (trendGranularity === 'hour') return 72;
        return 180;
    }, [trendGranularity]);
    const sourceTrend = useQuery({
        queryKey: ['ops-source-items-trend', sourceId, trendGranularity, trendBuckets],
        queryFn: () => fetchOpsSourceItemsTrend(sourceId, { granularity: trendGranularity, buckets: trendBuckets }),
        enabled: !!sourceId,
        refetchInterval: (query) => (query.state.error ? false : getIntervalMs("ops.source_trend_ms", 30000)),
    });
    const trendData = sourceTrend.data?.items || [];
    const relatedSources = useMemo(() => sourceData.related_sources || [], [sourceData.related_sources]);
    const hasAnyCategories = relatedSources.length > 0;
    const filteredRelatedSources = useMemo(() => {
        const query = categorySearch.trim().toLowerCase();
        if (!query) return relatedSources;
        return relatedSources.filter((rel: any) => {
            const name = String(rel?.config?.discovery_name || "").toLowerCase();
            const siteKey = String(rel?.site_key || "").toLowerCase();
            const url = String(rel?.url || "").toLowerCase();
            return name.includes(query) || siteKey.includes(query) || url.includes(query);
        });
    }, [relatedSources, categorySearch]);
    const categoryTotalPages = Math.max(1, Math.ceil(filteredRelatedSources.length / CATEGORY_PAGE_SIZE));
    const safeCategoryPage = Math.min(categoryPage, Math.max(0, categoryTotalPages - 1));
    const pagedRelatedSources = useMemo(() => {
        const start = safeCategoryPage * CATEGORY_PAGE_SIZE;
        return filteredRelatedSources.slice(start, start + CATEGORY_PAGE_SIZE);
    }, [filteredRelatedSources, safeCategoryPage, CATEGORY_PAGE_SIZE]);
    useEffect(() => {
        if (categoryPage !== safeCategoryPage) {
            setCategoryPage(safeCategoryPage);
        }
    }, [categoryPage, safeCategoryPage]);
    const categoryItem = categoryDetails.data?.item;

    useEffect(() => {
        setNameDraft(parserDisplayName);
        setUrlDraft(parserUrl);
    }, [parserDisplayName, parserUrl, sourceId]);

    const statusBadgeClass = (status?: string) => {
        switch (status) {
            case "running":
                return "bg-blue-500/20 text-blue-300 border-blue-400/35";
            case "completed":
                return "bg-emerald-500/20 text-emerald-300 border-emerald-400/35";
            case "error":
            case "rejected":
                return "bg-rose-500/20 text-rose-300 border-rose-400/35";
            case "queued":
                return "bg-amber-500/20 text-amber-300 border-amber-400/35";
            case "promoted":
                return "bg-violet-500/20 text-violet-300 border-violet-400/35";
            default:
                return "bg-white/10 text-white/85 border-white/20";
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

    const formatTrendLabel = (value?: string | null) => {
        if (!value) return "-";
        const date = new Date(value);
        if (!Number.isFinite(date.getTime())) return value;
        if (trendGranularity === 'week') {
            return `Wk ${date.toLocaleDateString(undefined, { month: "short", day: "numeric" })}`;
        }
        if (trendGranularity === 'day') {
            return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
        }
        return date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
    };

    const upsertNotification = (next: { id: string; status: "running" | "success" | "error"; title: string; message: string }) => {
        setNotifications((prev) => {
            const idx = prev.findIndex((n) => n.id === next.id);
            if (idx >= 0) {
                const copy = [...prev];
                copy[idx] = next;
                return copy;
            }
            return [...prev, next];
        });
    };

    const dismissNotification = (id: string) => {
        setNotifications((prev) => prev.filter((n) => n.id !== id));
    };

    const commitInlineName = async () => {
        if (!source || !onUpdateSource) return;
        const nextName = nameDraft.trim() || parserSlug;
        if (nextName === parserDisplayName) return;
        const cfg = { ...(sourceData.config || {}), site_name: nextName };
        try {
            setInlineSaving("name");
            await Promise.resolve(onUpdateSource(sourceId, { config: cfg }));
            await refetchSource();
        } catch (error: any) {
            const notifId = `spider-inline-name-${sourceId}`;
            upsertNotification({
                id: notifId,
                status: "error",
                title: "Name update failed",
                message: String(error?.response?.data?.detail || error?.message || "Unknown error"),
            });
            window.setTimeout(() => dismissNotification(notifId), 7000);
            setNameDraft(parserDisplayName);
        } finally {
            setInlineSaving(null);
        }
    };

    const commitInlineUrl = async () => {
        if (!source || !onUpdateSource) return;
        const nextUrl = urlDraft.trim();
        if (!nextUrl || nextUrl === parserUrl) return;
        try {
            setInlineSaving("url");
            await Promise.resolve(onUpdateSource(sourceId, { url: nextUrl }));
            await refetchSource();
        } catch (error: any) {
            const notifId = `spider-inline-url-${sourceId}`;
            upsertNotification({
                id: notifId,
                status: "error",
                title: "URL update failed",
                message: String(error?.response?.data?.detail || error?.message || "Unknown error"),
            });
            window.setTimeout(() => dismissNotification(notifId), 7000);
            setUrlDraft(parserUrl);
        } finally {
            setInlineSaving(null);
        }
    };

    const handleRunDiscovery = async () => {
        const siteKey = String(sourceData.site_key || "");
        if (!siteKey || runningDiscovery) return;
        const notifId = `spider-discovery-${siteKey}`;
        let beforeTotal = 0;
        setRunningDiscovery(true);
        upsertNotification({
            id: notifId,
            status: "running",
            title: `${siteKey} · Discovery`,
            message: "Discovery started...",
        });
        try {
            try {
                const initial = await fetchOpsSites();
                const initialSite = (initial?.items || []).find((s: any) => s.site_key === siteKey);
                beforeTotal = initialSite
                    ? Number(initialSite?.counters?.discovered_new || 0) + Number(initialSite?.counters?.discovered_promoted || 0)
                    : 0;
            } catch {
                beforeTotal = 0;
            }
            await runOpsSiteDiscovery(siteKey);
            let finalSite: any = null;
            let finalStatus = "queued";
            for (let i = 0; i < 120; i += 1) {
                await new Promise((resolve) => window.setTimeout(resolve, 1500));
                const fresh = await fetchOpsSites();
                const current = (fresh?.items || []).find((s: any) => s.site_key === siteKey);
                if (!current) continue;
                finalSite = current;
                finalStatus = String(current.status || "").toLowerCase();
                if (["error", "broken", "failed"].includes(finalStatus)) break;
                if (!["queued", "running", "processing"].includes(finalStatus)) break;
            }
            const afterTotal = finalSite
                ? Number(finalSite?.counters?.discovered_new || 0) + Number(finalSite?.counters?.discovered_promoted || 0)
                : beforeTotal;
            const foundDelta = Math.max(0, afterTotal - beforeTotal);
            if (["error", "broken", "failed"].includes(finalStatus)) {
                upsertNotification({
                    id: notifId,
                    status: "error",
                    title: `${siteKey} · Discovery failed`,
                    message: `Status: ${finalStatus}`,
                });
            } else {
                upsertNotification({
                    id: notifId,
                    status: "success",
                    title: `${siteKey} · Discovery finished`,
                    message: `Found categories: ${foundDelta}`,
                });
            }
            await Promise.allSettled([refetchSource(), categoryDetails.refetch()]);
        } catch (error: any) {
            upsertNotification({
                id: notifId,
                status: "error",
                title: `${siteKey} · Discovery failed`,
                message: String(error?.response?.data?.detail || error?.message || "Unknown error"),
            });
        } finally {
            setRunningDiscovery(false);
            window.setTimeout(() => dismissNotification(notifId), 10000);
        }
    };

    const queueCategoryNow = async (categoryId?: number, categoryLabel?: string) => {
        if (!categoryId) return;
        if (runningCategoryIds[categoryId]) return;
        const notifId = `cat-run-inline-${categoryId}`;
        setRunningCategoryIds((prev) => ({ ...prev, [categoryId]: true }));
        upsertNotification({
            id: notifId,
            status: "running",
            title: "Queueing category",
            message: categoryLabel || `Category #${categoryId}`,
        });
        try {
            await runOpsDiscoveryCategoryNow(categoryId);
            upsertNotification({
                id: notifId,
                status: "success",
                title: "Category queued",
                message: categoryLabel || `Category #${categoryId}`,
            });
            await Promise.allSettled([refetchSource(), categoryDetails.refetch()]);
        } catch (error: any) {
            upsertNotification({
                id: notifId,
                status: "error",
                title: "Queue failed",
                message: String(error?.response?.data?.detail || error?.message || "Unknown error"),
            });
        } finally {
            setRunningCategoryIds((prev) => ({ ...prev, [categoryId]: false }));
            window.setTimeout(() => dismissNotification(notifId), 7000);
        }
    };

    const queueAllCategoriesNow = async () => {
        const siteKey = String(sourceData.site_key || "");
        if (!siteKey || runningAllCategories) return;
        const notifId = `cat-run-all-${sourceData.site_key || sourceId}`;
        setRunningAllCategories(true);
        upsertNotification({
            id: notifId,
            status: "running",
            title: "Queueing all categories",
            message: "Processing request...",
        });
        try {
            const result = await runOpsDiscoveryAllForSite(siteKey, {
                limit: 10000,
                states: ["promoted"],
                q: categorySearch.trim() || undefined,
            });
            const queued = Number(result?.queued || 0);
            const skipped = Number(result?.skipped || 0);
            const failed = Number(result?.failed || 0);
            upsertNotification({
                id: notifId,
                status: failed > 0 ? "error" : "success",
                title: failed > 0 ? "Queue all completed with errors" : "All categories queued",
                message: `queued ${queued}, skipped ${skipped}, failed ${failed}`,
            });
            await Promise.allSettled([refetchSource(), categoryDetails.refetch()]);
        } catch (error: any) {
            upsertNotification({
                id: notifId,
                status: "error",
                title: "Queue all failed",
                message: String(error?.response?.data?.detail || error?.message || "Unknown error"),
            });
        } finally {
            setRunningAllCategories(false);
            window.setTimeout(() => dismissNotification(notifId), 10000);
        }
    };

    const approveAllCategories = async () => {
        if (approvingAllCategories) return;
        const candidateIds = filteredRelatedSources
            .filter((rel: any) => rel?.category_id && rel?.config?.category_state !== "promoted")
            .map((rel: any) => Number(rel.category_id))
            .filter((id: number) => Number.isFinite(id));

        if (!candidateIds.length) {
            const notifId = `cat-approve-all-${sourceData.site_key || sourceId}`;
            upsertNotification({
                id: notifId,
                status: "success",
                title: "No categories to approve",
                message: "All visible categories are already approved.",
            });
            window.setTimeout(() => dismissNotification(notifId), 5000);
            return;
        }

        const notifId = `cat-approve-all-${sourceData.site_key || sourceId}`;
        setApprovingAllCategories(true);
        upsertNotification({
            id: notifId,
            status: "running",
            title: "Approving categories",
            message: `Selected ${candidateIds.length} categories`,
        });

        try {
            let updated = 0;
            const chunkSize = 500;
            for (let i = 0; i < candidateIds.length; i += chunkSize) {
                const chunk = candidateIds.slice(i, i + chunkSize);
                const result = await promoteOpsDiscovery(chunk);
                updated += Number(result?.updated || 0);
            }

            upsertNotification({
                id: notifId,
                status: "success",
                title: "Approve all completed",
                message: `Approved ${updated} categories`,
            });
            await Promise.allSettled([refetchSource(), categoryDetails.refetch()]);
        } catch (error: any) {
            upsertNotification({
                id: notifId,
                status: "error",
                title: "Approve all failed",
                message: String(error?.response?.data?.detail || error?.message || "Unknown error"),
            });
        } finally {
            setApprovingAllCategories(false);
            window.setTimeout(() => dismissNotification(notifId), 9000);
        }
    };

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

    if (isLoading && !source) {
        return (
            <div className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-300">
                <div className="bg-[var(--tg-theme-bg-color)] w-full max-w-lg rounded-t-3xl sm:rounded-3xl overflow-hidden shadow-2xl animate-in slide-in-from-bottom duration-300">
                    <div className="min-h-[42vh] flex items-center justify-center">
                        <Loader2 className="animate-spin text-[var(--tg-theme-button-color)]" size={30} />
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-300">
            <div className="bg-[var(--tg-theme-bg-color)] w-full max-w-lg rounded-t-3xl sm:rounded-3xl overflow-hidden shadow-2xl animate-in slide-in-from-bottom duration-300">
                {/* Header */}
                <div className="p-5 border-b border-[var(--tg-theme-secondary-bg-color)] flex items-center justify-between bg-gradient-to-r from-[var(--tg-theme-secondary-bg-color)] to-[var(--tg-theme-bg-color)]">
                    <div>
                        <div className="flex items-center gap-2">
                            {isEditingName ? (
                                <input
                                    value={nameDraft}
                                    onChange={(e) => setNameDraft(e.target.value)}
                                    onBlur={() => {
                                        setIsEditingName(false);
                                        void commitInlineName();
                                    }}
                                    onKeyDown={(e) => {
                                        if (e.key === "Enter") {
                                            (e.currentTarget as HTMLInputElement).blur();
                                        }
                                        if (e.key === "Escape") {
                                            setNameDraft(parserDisplayName);
                                            setIsEditingName(false);
                                        }
                                    }}
                                    autoFocus
                                    className="rounded-md border border-white/20 bg-black/20 px-2 py-1 font-bold text-xl text-white outline-none focus:border-sky-300/50"
                                />
                            ) : (
                                <h2 className="font-bold text-xl">{parserDisplayName}</h2>
                            )}
                            <button
                                className="rounded-md border border-white/20 bg-black/20 p-1 text-white/80 hover:bg-white/10 disabled:opacity-50"
                                onClick={() => setIsEditingName(true)}
                                disabled={!source || inlineSaving === "name"}
                                title="Edit parser name"
                            >
                                {inlineSaving === "name" ? <Loader2 size={13} className="animate-spin" /> : <Pencil size={13} />}
                            </button>
                        </div>
                        <p className="text-xs text-[var(--tg-theme-hint-color)]">{parserSlug}</p>
                        <div className="mt-1 flex items-center gap-2">
                            {isEditingUrl ? (
                                <input
                                    value={urlDraft}
                                    onChange={(e) => setUrlDraft(e.target.value)}
                                    onBlur={() => {
                                        setIsEditingUrl(false);
                                        void commitInlineUrl();
                                    }}
                                    onKeyDown={(e) => {
                                        if (e.key === "Enter") {
                                            (e.currentTarget as HTMLInputElement).blur();
                                        }
                                        if (e.key === "Escape") {
                                            setUrlDraft(parserUrl);
                                            setIsEditingUrl(false);
                                        }
                                    }}
                                    autoFocus
                                    className="w-full max-w-[360px] rounded-md border border-white/20 bg-black/20 px-2 py-1 text-xs text-white outline-none focus:border-sky-300/50"
                                />
                            ) : (
                                <p className="text-xs text-white/75 truncate max-w-[360px]">{parserUrl || "URL not set"}</p>
                            )}
                            <button
                                className="rounded-md border border-white/20 bg-black/20 p-1 text-white/80 hover:bg-white/10 disabled:opacity-50"
                                onClick={() => setIsEditingUrl(true)}
                                disabled={!source || inlineSaving === "url"}
                                title="Edit parser URL"
                            >
                                {inlineSaving === "url" ? <Loader2 size={13} className="animate-spin" /> : <Pencil size={13} />}
                            </button>
                        </div>
                        <div className="mt-1 flex items-center gap-1.5 flex-wrap">
                            <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full ${sourceData.status === 'running' ? 'bg-blue-500/20 text-blue-500' :
                                sourceData.status === 'broken' ? 'bg-red-500/20 text-red-500' :
                                    'bg-green-500/20 text-green-500'
                                }`}>
                                {isLoading ? "loading" : sourceData.status}
                            </span>
                            {sourceData.aggregate_history?.length > 0 ? (
                                <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-400/30">
                                    Hub Aggregate
                                </span>
                            ) : null}
                            {sourceData.history?.length > 0 ? (
                                <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-400/30">
                                    Run History
                                </span>
                            ) : null}
                        </div>
                    </div>
                    <button onClick={onClose} className="p-2 rounded-full hover:bg-black/5 transition-colors">
                        <X size={20} />
                    </button>
                </div>

                <div className="overflow-y-auto max-h-[85vh] p-5 space-y-6 pb-24">
                    {isLoading ? (
                        <div className="rounded-xl border border-white/15 bg-white/[0.04] p-3 text-sm text-white/80 flex items-center gap-2">
                            <Loader2 className="animate-spin text-[var(--tg-theme-button-color)]" size={16} />
                            {t('spiders.loading_details')}
                        </div>
                    ) : null}
                    <ApiServerErrorBanner
                        errors={[sourceError]}
                        onRetry={async () => {
                            await refetchSource();
                        }}
                        title="Parser API временно недоступен"
                    />
                    {sourceError ? (
                        <div className="rounded-xl border border-red-400/40 bg-red-500/10 p-3 text-xs text-red-100">
                            <p className="font-semibold">Не удалось загрузить карточку парсера</p>
                            <p className="mt-1 break-words opacity-90">
                                {String((sourceError as any)?.response?.data?.detail || (sourceError as any)?.message || "Unknown API error")}
                            </p>
                        </div>
                    ) : null}
                    <div>
                        <div className="flex flex-wrap items-center gap-2">
                            <button
                                onClick={() => void handleRunDiscovery()}
                                disabled={runningDiscovery}
                                className="inline-flex items-center gap-2 rounded-lg border border-emerald-400/45 bg-emerald-500/20 px-3 py-1.5 text-xs font-semibold text-emerald-100 disabled:opacity-50"
                            >
                                {runningDiscovery ? <Loader2 size={14} className="animate-spin" /> : <TrendingUp size={14} />}
                                Run discovery
                            </button>
                            <button
                                onClick={() => void approveAllCategories()}
                                disabled={approvingAllCategories || !hasAnyCategories}
                                className="inline-flex items-center gap-2 rounded-lg border border-violet-400/45 bg-violet-500/20 px-3 py-1.5 text-xs font-semibold text-violet-100 disabled:opacity-50"
                            >
                                {approvingAllCategories ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
                                Approve all
                            </button>
                            <button
                                onClick={() => void queueAllCategoriesNow()}
                                disabled={runningAllCategories || !hasAnyCategories}
                                className="inline-flex items-center gap-2 rounded-lg border border-sky-400/45 bg-sky-500/20 px-3 py-1.5 text-xs font-semibold text-sky-100 disabled:opacity-50"
                            >
                                {runningAllCategories ? <Loader2 size={14} className="animate-spin" /> : null}
                                Run all
                            </button>
                            <button
                                onClick={() => onToggleActive?.(sourceId, !sourceData.is_active)}
                                disabled={!source}
                                className={`inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-semibold disabled:opacity-50 ${
                                    sourceData.is_active
                                        ? "border border-rose-400/45 bg-rose-500/20 text-rose-100"
                                        : "border border-emerald-400/45 bg-emerald-500/20 text-emerald-100"
                                }`}
                                title={sourceData.is_active ? "Disable parser" : "Enable parser"}
                            >
                                <Power size={14} />
                                {sourceData.is_active ? "Disable parser" : "Enable parser"}
                            </button>
                        </div>
                    </div>

                    {/* Tabs */}
                    <div className="flex bg-[var(--tg-theme-secondary-bg-color)] p-1 rounded-xl">
                        {[
                            { id: 'overview', label: t('dashboard.stats'), icon: TrendingUp },
                            { id: 'categories', label: 'Категории', icon: List },
                        ].map((tab) => (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id as any)}
                                className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-bold transition-all ${activeTab === tab.id
                                    ? "bg-[var(--tg-theme-bg-color)] text-[var(--tg-theme-button-color)] shadow-sm"
                                    : "text-[var(--tg-theme-hint-color)] opacity-60 hover:opacity-100"
                                    }`}
                            >
                                <tab.icon size={14} />
                                {tab.label}
                            </button>
                        ))}
                    </div>

                    {activeTab === 'overview' && (
                        <div className="space-y-6 animate-in fade-in slide-in-from-top-2 duration-300">
                            {/* Stats Grid */}
                            <div className="grid grid-cols-2 gap-3">
                                <div className="card p-3 flex flex-col gap-1">
                                    <div className="flex items-center gap-2 text-[var(--tg-theme-hint-color)]">
                                        <Package size={14} />
                                        <span className="text-[10px] font-bold uppercase">{t('spiders.total_items')}</span>
                                    </div>
                                    <p className="text-xl font-bold">{(sourceData.total_items || 0).toLocaleString()}</p>
                                </div>
                                <div className="card p-3 flex flex-col gap-1">
                                    <div className="flex items-center gap-2 text-[var(--tg-theme-hint-color)]">
                                        <TrendingUp size={14} />
                                        <span className="text-[10px] font-bold uppercase">{t('spiders.last_sync')}</span>
                                    </div>
                                    <p className="text-xl font-bold">+{sourceData.last_run_new || 0}</p>
                                </div>
                            </div>

                            <div className="space-y-3">
                                <div className="flex flex-wrap items-center justify-between gap-2 px-1">
                                    <h3 className="text-sm font-bold flex items-center gap-2">
                                        <TrendingUp size={16} className="text-green-500" />
                                        Parser New Products Trend
                                    </h3>
                                    <span className="text-[11px] text-[var(--tg-theme-hint-color)]">
                                        total: {Number(sourceTrend.data?.totals?.items_new || 0).toLocaleString()}
                                    </span>
                                </div>
                                <div className="flex flex-wrap gap-1.5 px-1">
                                    {([
                                        { key: 'week', label: 'Weeks' },
                                        { key: 'day', label: 'Days' },
                                        { key: 'hour', label: 'Hours' },
                                        { key: 'minute', label: 'Minutes' },
                                    ] as { key: 'week' | 'day' | 'hour' | 'minute'; label: string }[]).map((g) => (
                                        <button
                                            key={g.key}
                                            className={`rounded-md border px-2 py-1 text-[11px] transition ${
                                                trendGranularity === g.key
                                                    ? "border-sky-300/55 bg-sky-500/25 text-sky-100"
                                                    : "border-white/20 bg-white/5 text-white/80 hover:bg-white/10"
                                            }`}
                                            onClick={() => setTrendGranularity(g.key)}
                                        >
                                            {g.label}
                                        </button>
                                    ))}
                                </div>
                                <div className="h-40 w-full card p-2">
                                    {sourceTrend.isLoading ? (
                                        <div className="flex h-full items-center justify-center text-sm text-white/75">
                                            <Loader2 size={16} className="mr-2 animate-spin" />
                                            Loading trend...
                                        </div>
                                    ) : (
                                        <ResponsiveContainer width="100%" height="100%">
                                            <LineChart data={trendData} margin={{ top: 5, right: 5, left: -25, bottom: 20 }}>
                                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--tg-theme-hint-color)" strokeOpacity={0.1} />
                                                <XAxis
                                                    dataKey="date"
                                                    axisLine={false}
                                                    tickLine={false}
                                                    tick={{ fill: 'var(--tg-theme-hint-color)', fontSize: 9 }}
                                                    tickFormatter={(v) => formatTrendLabel(String(v))}
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
                                                    labelFormatter={(v) => formatTrendLabel(String(v))}
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
                                    )}
                                </div>
                            </div>

                            {runHistory.length > 0 && (
                                <div className="space-y-3">
                                    <h3 className="text-sm font-bold flex items-center gap-2 px-1">
                                        <Clock size={16} className="text-blue-500" />
                                        Recent Runs
                                    </h3>
                                    <div className="space-y-2">
                                        {runHistory.slice(0, 6).map((h: any) => (
                                            <div key={h.id} className="card p-3 text-xs">
                                                <div className="flex items-center justify-between">
                                                    <span className="font-bold uppercase">{h.status}</span>
                                                    <span className="text-[10px] text-[var(--tg-theme-hint-color)]">{formatTimeAgo(h.created_at)}</span>
                                                </div>
                                                <div className="mt-1 text-[10px] text-[var(--tg-theme-hint-color)]">
                                                    scraped: {h.items_scraped || 0} • new: {h.items_new || 0}
                                                </div>
                                                {h.error_message ? (
                                                    <div className="mt-1 text-[10px] text-red-400 line-clamp-2">{h.error_message}</div>
                                                ) : null}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                        </div>
                    )}

                    {activeTab === 'categories' && (
                        <div className="animate-in fade-in slide-in-from-top-2 duration-300 min-h-[40vh] space-y-3">
                            <div className="card p-2.5 space-y-2 border border-white/5">
                                <div className="flex items-center gap-2">
                                    <input
                                        value={categorySearch}
                                        onChange={(e) => {
                                            setCategorySearch(e.target.value);
                                            setCategoryPage(0);
                                        }}
                                        placeholder="Search category / url"
                                        className="w-full rounded-lg border border-white/15 bg-black/20 px-3 py-2 text-xs text-white placeholder:text-white/45 outline-none focus:border-sky-300/50"
                                    />
                                </div>
                                <div className="flex items-center justify-between text-[10px] text-[var(--tg-theme-hint-color)]">
                                    <span>Showing {pagedRelatedSources.length} of {filteredRelatedSources.length}</span>
                                    <span>Page {safeCategoryPage + 1} / {categoryTotalPages}</span>
                                </div>
                            </div>
                            <div className="card overflow-hidden border border-white/5 shadow-inner">
                                <div className="max-h-[420px] overflow-auto">
                                    <table className="w-full text-left border-collapse">
                                        <thead className="sticky top-0 z-[1] bg-[var(--tg-theme-secondary-bg-color)] text-[10px] uppercase text-[var(--tg-theme-hint-color)] font-bold">
                                            <tr>
                                                <th className="p-3">{t('categories.category')}</th>
                                                <th className="p-3 text-center">{t('categories.products')}</th>
                                                <th className="p-3 text-center">{t('categories.status')}</th>
                                                <th className="p-3">{t('categories.last_run')}</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-white/5">
                                            {pagedRelatedSources.map((rel: any) => (
                                                <tr
                                                    key={rel.id || rel.category_id || rel.url}
                                                    className={`text-xs transition-colors group ${(rel.category_id || rel.id) ? "hover:bg-[var(--tg-theme-button-color)]/5 cursor-pointer" : "opacity-80"}`}
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        if (rel.category_id) {
                                                            setSelectedCategoryId(rel.category_id);
                                                        }
                                                    }}
                                                >
                                                    <td className="p-3 font-medium">
                                                        <div className="flex flex-col">
                                                            <span className="group-hover:text-[var(--tg-theme-button-color)] transition-colors">
                                                                {rel.config?.discovery_name || rel.site_key}
                                                            </span>
                                                            <span className="text-[8px] opacity-50 truncate max-w-[120px]">
                                                                {rel.url.split('/').pop() || rel.site_key}
                                                            </span>
                                                        </div>
                                                    </td>
                                                    <td className="p-3 text-center">
                                                        <span className="bg-[var(--tg-theme-button-color)]/10 text-[var(--tg-theme-button-color)] px-1.5 py-0.5 rounded-md font-black">
                                                            {rel.total_items || 0}
                                                        </span>
                                                    </td>
                                                    <td className="p-3">
                                                        <div className="flex justify-center">
                                                            {getStatusIcon(rel.status, rel.is_active)}
                                                        </div>
                                                    </td>
                                                    <td className="p-3">
                                                        <div className="flex items-center gap-2">
                                                            <span className="whitespace-nowrap">{formatTimeAgo(rel.last_synced_at)}</span>
                                                            {rel.category_id ? (
                                                                <button
                                                                    className="rounded-md border border-sky-400/45 bg-sky-500/15 px-1.5 py-0.5 text-[10px] text-sky-100 disabled:opacity-50"
                                                                    disabled={!!runningCategoryIds[rel.category_id] || rel?.config?.category_state !== "promoted"}
                                                                    title={rel?.config?.category_state === "promoted" ? "Queue approved category" : "Approve category first"}
                                                                    onClick={(e) => {
                                                                        e.stopPropagation();
                                                                        void queueCategoryNow(rel.category_id, rel.config?.discovery_name || rel.site_key);
                                                                    }}
                                                                >
                                                                    {runningCategoryIds[rel.category_id] ? (
                                                                        <span className="inline-flex items-center gap-1">
                                                                            <Loader2 size={10} className="animate-spin" />
                                                                            queue...
                                                                        </span>
                                                                    ) : (
                                                                        "Run now"
                                                                    )}
                                                                </button>
                                                            ) : null}
                                                        </div>
                                                    </td>
                                                </tr>
                                            ))}
                                            {!pagedRelatedSources.length ? (
                                                <tr>
                                                    <td colSpan={4} className="p-3 text-xs text-white/70">
                                                        No categories found.
                                                    </td>
                                                </tr>
                                            ) : null}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                            <div className="flex items-center justify-end gap-2">
                                <button
                                    className="rounded-md border border-white/20 bg-black/20 px-2 py-1 text-[11px] text-white/85 disabled:opacity-40"
                                    disabled={safeCategoryPage <= 0}
                                    onClick={() => setCategoryPage((prev) => Math.max(0, prev - 1))}
                                >
                                    Prev
                                </button>
                                <button
                                    className="rounded-md border border-white/20 bg-black/20 px-2 py-1 text-[11px] text-white/85 disabled:opacity-40"
                                    disabled={safeCategoryPage >= categoryTotalPages - 1}
                                    onClick={() => setCategoryPage((prev) => Math.min(categoryTotalPages - 1, prev + 1))}
                                >
                                    Next
                                </button>
                            </div>
                        </div>
                    )}

                    <button
                        onClick={() => setShowConfigEditor(true)}
                        className="w-full py-3 rounded-xl border border-[var(--tg-theme-secondary-bg-color)] text-[var(--tg-theme-hint-color)] font-bold flex items-center justify-center gap-2"
                        disabled={!source}
                    >
                        <Settings2 size={16} />
                        Edit Source Config
                    </button>
                </div>
            </div>

            {showConfigEditor && source && (
                <SourceConfigEditor
                    source={source}
                    onClose={() => setShowConfigEditor(false)}
                    onSave={(id, payload) => onUpdateSource?.(id, payload)}
                    isSaving={isUpdatingSource}
                />
            )}

            {selectedCategoryId ? (
                <div className="fixed inset-0 z-[70] flex items-end sm:items-center justify-center bg-black/65 p-2 sm:p-4">
                    <div className="w-full max-w-3xl rounded-2xl border border-white/20 bg-[#0a1322] shadow-2xl overflow-hidden">
                        <div className="flex items-center justify-between border-b border-white/12 px-4 py-3">
                            <div>
                                <h3 className="text-lg font-semibold text-white">Category Card</h3>
                                <p className="text-xs text-white/70">{categoryItem?.site_key || sourceData.site_key}</p>
                            </div>
                            <button
                                className="rounded-lg border border-white/25 px-2 py-1 text-xs text-white/85 hover:bg-white/10"
                                onClick={() => setSelectedCategoryId(null)}
                            >
                                <X size={14} />
                            </button>
                        </div>
                        <div className="max-h-[78vh] overflow-y-auto p-4 space-y-3">
                            <ApiServerErrorBanner
                                errors={[categoryDetails.error]}
                                onRetry={async () => {
                                    await categoryDetails.refetch();
                                }}
                                title="Category API временно недоступен"
                            />
                            {categoryDetails.isLoading ? (
                                <div className="flex items-center justify-center py-12 text-sm text-white/80">
                                    <Loader2 size={16} className="animate-spin mr-2" />
                                    Loading category details...
                                </div>
                            ) : categoryItem ? (
                                <>
                                    <div className="rounded-xl border border-white/12 bg-white/[0.03] p-3">
                                        <div className="flex items-start justify-between gap-2">
                                            <div>
                                                <p className="text-base font-semibold text-white">{categoryItem.name || categoryItem.url}</p>
                                                <p className="text-xs text-white/70 mt-0.5">{categoryItem.url}</p>
                                            </div>
                                            <span className={`rounded-full border px-2 py-0.5 text-[10px] ${statusBadgeClass(categoryItem.state)}`}>
                                                {categoryItem.state === "promoted" ? "approved" : categoryItem.state}
                                            </span>
                                        </div>
                                        <div className="mt-3 grid gap-2 sm:grid-cols-4">
                                            <div className="rounded-lg border border-white/12 bg-black/20 p-2">
                                                <p className="text-[11px] text-white/70">Products in DB</p>
                                                <p className="text-lg font-semibold text-white">{Number(categoryItem.products_total || 0)}</p>
                                            </div>
                                            <div className="rounded-lg border border-white/12 bg-black/20 p-2">
                                                <p className="text-[11px] text-white/70">Last run</p>
                                                <p className="text-sm font-medium text-white">{categoryItem.last_run_at ? formatTimeAgo(categoryItem.last_run_at) : "-"}</p>
                                            </div>
                                            <div className="rounded-lg border border-white/12 bg-black/20 p-2">
                                                <p className="text-[11px] text-white/70">Last new</p>
                                                <p className="text-lg font-semibold text-white">{Number(categoryItem.last_run_new || 0)}</p>
                                            </div>
                                            <div className="rounded-lg border border-white/12 bg-black/20 p-2">
                                                <p className="text-[11px] text-white/70">Last scraped</p>
                                                <p className="text-lg font-semibold text-white">{Number(categoryItem.last_run_scraped || 0)}</p>
                                            </div>
                                        </div>
                                        <div className="mt-3 flex flex-wrap gap-2">
                                            <button
                                                className="rounded-md border border-sky-400/45 bg-sky-500/15 px-2 py-1 text-[11px] text-sky-100 disabled:opacity-50"
                                                disabled={categoryActionPending || categoryItem.state !== "promoted"}
                                                title={categoryItem.state === "promoted" ? "Queue approved category" : "Approve category first"}
                                                onClick={async () => {
                                                    setCategoryActionPending(true);
                                                    try {
                                                        await runOpsDiscoveryCategoryNow(categoryItem.id);
                                                        upsertNotification({ id: `cat-run-${categoryItem.id}`, status: "success", title: "Category queued", message: categoryItem.name || categoryItem.url });
                                                        await Promise.allSettled([categoryDetails.refetch(), refetchSource()]);
                                                    } catch (error: any) {
                                                        upsertNotification({ id: `cat-run-${categoryItem.id}`, status: "error", title: "Queue failed", message: String(error?.response?.data?.detail || error?.message || "Unknown error") });
                                                    } finally {
                                                        setCategoryActionPending(false);
                                                        window.setTimeout(() => dismissNotification(`cat-run-${categoryItem.id}`), 7000);
                                                    }
                                                }}
                                            >
                                                Run now
                                            </button>
                                            {categoryItem.state === "new" ? (
                                                <>
                                                    <button
                                                        className="rounded-md border border-emerald-400/45 bg-emerald-500/15 px-2 py-1 text-[11px] text-emerald-100 disabled:opacity-50"
                                                        disabled={categoryActionPending}
                                                        onClick={async () => {
                                                            setCategoryActionPending(true);
                                                            try {
                                                                await promoteOpsDiscovery([categoryItem.id]);
                                                                upsertNotification({ id: `cat-${categoryItem.id}`, status: "success", title: "Category approved", message: categoryItem.name || categoryItem.url });
                                                                await Promise.allSettled([categoryDetails.refetch(), refetchSource()]);
                                                            } catch (error: any) {
                                                                upsertNotification({ id: `cat-${categoryItem.id}`, status: "error", title: "Approve failed", message: String(error?.response?.data?.detail || error?.message || "Unknown error") });
                                                            } finally {
                                                                setCategoryActionPending(false);
                                                                window.setTimeout(() => dismissNotification(`cat-${categoryItem.id}`), 7000);
                                                            }
                                                        }}
                                                    >
                                                        Approve
                                                    </button>
                                                    <button
                                                        className="rounded-md border border-rose-400/45 bg-rose-500/15 px-2 py-1 text-[11px] text-rose-100 disabled:opacity-50"
                                                        disabled={categoryActionPending}
                                                        onClick={async () => {
                                                            setCategoryActionPending(true);
                                                            try {
                                                                await rejectOpsDiscovery([categoryItem.id]);
                                                                upsertNotification({ id: `cat-${categoryItem.id}`, status: "success", title: "Category rejected", message: categoryItem.name || categoryItem.url });
                                                                await Promise.allSettled([categoryDetails.refetch(), refetchSource()]);
                                                            } catch (error: any) {
                                                                upsertNotification({ id: `cat-${categoryItem.id}`, status: "error", title: "Reject failed", message: String(error?.response?.data?.detail || error?.message || "Unknown error") });
                                                            } finally {
                                                                setCategoryActionPending(false);
                                                                window.setTimeout(() => dismissNotification(`cat-${categoryItem.id}`), 7000);
                                                            }
                                                        }}
                                                    >
                                                        Reject
                                                    </button>
                                                </>
                                            ) : null}
                                            {(categoryItem.state === "rejected" || categoryItem.state === "inactive") ? (
                                                <button
                                                    className="rounded-md border border-violet-400/45 bg-violet-500/15 px-2 py-1 text-[11px] text-violet-100 disabled:opacity-50"
                                                    disabled={categoryActionPending}
                                                    onClick={async () => {
                                                        setCategoryActionPending(true);
                                                        try {
                                                            await reactivateOpsDiscovery([categoryItem.id]);
                                                            upsertNotification({ id: `cat-${categoryItem.id}`, status: "success", title: "Category re-activated", message: categoryItem.name || categoryItem.url });
                                                            await Promise.allSettled([categoryDetails.refetch(), refetchSource()]);
                                                        } catch (error: any) {
                                                            upsertNotification({ id: `cat-${categoryItem.id}`, status: "error", title: "Re-activate failed", message: String(error?.response?.data?.detail || error?.message || "Unknown error") });
                                                        } finally {
                                                            setCategoryActionPending(false);
                                                            window.setTimeout(() => dismissNotification(`cat-${categoryItem.id}`), 7000);
                                                        }
                                                    }}
                                                >
                                                    Re-activate
                                                </button>
                                            ) : null}
                                        </div>
                                    </div>

                                    <div className="rounded-xl border border-white/12 bg-white/[0.03] p-3">
                                        <p className="text-sm font-semibold text-white mb-2">Items Trend</p>
                                        {Array.isArray(categoryItem.trend) && categoryItem.trend.length > 0 ? (
                                            <div className="h-48 w-full">
                                                <ResponsiveContainer width="100%" height="100%">
                                                    <LineChart data={categoryItem.trend} margin={{ top: 8, right: 8, left: -18, bottom: 20 }}>
                                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.12)" />
                                                        <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: "#cbd5e1", fontSize: 11 }} />
                                                        <YAxis axisLine={false} tickLine={false} tick={{ fill: "#cbd5e1", fontSize: 11 }} />
                                                        <Tooltip
                                                            contentStyle={{ backgroundColor: "#0f172a", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 10, fontSize: 12 }}
                                                        />
                                                        <Line type="monotone" dataKey="items_new" stroke="#38bdf8" strokeWidth={2.5} dot={false} name="new" />
                                                        <Line type="monotone" dataKey="items_scraped" stroke="#34d399" strokeWidth={2} dot={false} name="scraped" />
                                                    </LineChart>
                                                </ResponsiveContainer>
                                            </div>
                                        ) : (
                                            <div className="rounded-lg border border-dashed border-white/20 p-3 text-sm text-white/70">
                                                No run trend yet.
                                            </div>
                                        )}
                                    </div>
                                </>
                            ) : (
                                <div className="rounded-lg border border-dashed border-white/20 p-3 text-sm text-white/70">
                                    Category not found.
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            ) : null}
            <div className="fixed bottom-4 right-4 z-[90] flex w-[320px] max-w-[calc(100vw-2rem)] flex-col gap-2">
                {notifications.map((n) => (
                    <div
                        key={n.id}
                        className={`rounded-xl border p-3 shadow-xl ${
                            n.status === "running"
                                ? "border-sky-300/45 bg-sky-500/15 text-sky-100"
                                : n.status === "success"
                                    ? "border-emerald-300/45 bg-emerald-500/15 text-emerald-100"
                                    : "border-rose-300/45 bg-rose-500/15 text-rose-100"
                        }`}
                    >
                        <div className="flex items-start gap-2">
                            {n.status === "running" ? (
                                <Loader2 size={14} className="mt-0.5 animate-spin" />
                            ) : n.status === "success" ? (
                                <CheckCircle2 size={14} className="mt-0.5" />
                            ) : (
                                <AlertCircle size={14} className="mt-0.5" />
                            )}
                            <div className="min-w-0 flex-1">
                                <p className="text-sm font-semibold leading-tight">{n.title}</p>
                                <p className="mt-0.5 text-xs opacity-90">{n.message}</p>
                            </div>
                            <button className="text-xs opacity-80 hover:opacity-100" onClick={() => dismissNotification(n.id)}>
                                x
                            </button>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
