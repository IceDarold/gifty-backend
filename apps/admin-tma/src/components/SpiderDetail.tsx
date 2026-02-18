import { useState, useEffect, useRef } from "react";
import { X, Play, Power, Terminal, Calendar, Package, TrendingUp, Loader2, ChevronRight, Clock, AlertCircle, CheckCircle2, List, Filter } from "lucide-react";
import { useSourceDetails, useSourceProducts } from "@/hooks/useDashboard";
import { getSourceLogStreamUrl } from "@/lib/api";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { useLanguage } from "@/contexts/LanguageContext";
import { ProductsTable } from "./ProductsTable";
import { formatDistanceToNow } from "date-fns";
import { ru, enUS } from "date-fns/locale";

interface SpiderDetailProps {
    sourceId: number;
    onClose: () => void;
    onForceRun: (id: number, strategy: string) => void;
    onToggleActive?: (id: number, active: boolean) => void;
    onOpenSource?: (id: number) => void;
    isForceRunning: boolean;
}

export function SpiderDetail({ sourceId, onClose, onForceRun, onToggleActive, onOpenSource, isForceRunning }: SpiderDetailProps) {
    const [browsingSourceId, setBrowsingSourceId] = useState<number>(sourceId);
    const { data: source, isLoading } = useSourceDetails(sourceId);
    const [offset, setOffset] = useState(0);
    const { data: productsData, isLoading: isLoadingProducts } = useSourceProducts(browsingSourceId, 50, offset);

    const [activeTab, setActiveTab] = useState<'overview' | 'products' | 'logs'>('overview');
    const [allProducts, setAllProducts] = useState<any[]>([]);

    // Live Logs state
    const [liveLogs, setLiveLogs] = useState<string[]>([]);
    const [logFilter, setLogFilter] = useState<'all' | 'progress'>('progress');
    const logsEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (activeTab === 'logs') {
            logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }
    }, [liveLogs, activeTab]);

    useEffect(() => {
        setOffset(0);
        setAllProducts([]);
    }, [browsingSourceId]);

    useEffect(() => {
        setBrowsingSourceId(sourceId);
    }, [sourceId]);

    useEffect(() => {
        if (productsData?.items) {
            if (offset === 0) {
                setAllProducts(productsData.items);
            } else {
                setAllProducts(prev => [...prev, ...productsData.items]);
            }
        }
    }, [productsData, offset]);

    useEffect(() => {
        if (activeTab === 'logs' && sourceId) {
            setLiveLogs([]); // Clear logs when switching to tab
            const url = getSourceLogStreamUrl(sourceId);
            const eventSource = new EventSource(url);

            eventSource.onopen = () => {
                setLiveLogs(prev => [...prev, "[CONNECTED] Real-time log stream started..."]);
            };

            eventSource.onmessage = (event) => {
                if (event.data === ':ping') return;

                setLiveLogs(prev => {
                    const newLogs = [...prev, event.data];
                    // Keep only last 200 lines to avoid UI lag
                    return newLogs.slice(-200);
                });
            };

            eventSource.onerror = (err) => {
                console.error("SSE Error:", err);
                eventSource.close();
            };

            return () => {
                eventSource.close();
            };
        }
    }, [activeTab, sourceId]);

    const handleLoadMore = () => {
        setOffset(prev => prev + 50);
    };

    const { t, language } = useLanguage();
    const locale = language === 'ru' ? ru : enUS;

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
    const relatedSources = source.related_sources || [];

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

                <div className="overflow-y-auto max-h-[85vh] p-5 space-y-6 pb-24">
                    {/* Tabs */}
                    <div className="flex bg-[var(--tg-theme-secondary-bg-color)] p-1 rounded-xl">
                        {[
                            { id: 'overview', label: t('dashboard.stats'), icon: TrendingUp },
                            { id: 'products', label: t('stats.live_sources'), icon: Package },
                            { id: 'logs', label: t('spiders.logs'), icon: Terminal },
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
                                    <p className="text-xl font-bold">{(source.total_items || 0).toLocaleString()}</p>
                                </div>
                                <div className="card p-3 flex flex-col gap-1">
                                    <div className="flex items-center gap-2 text-[var(--tg-theme-hint-color)]">
                                        <TrendingUp size={14} />
                                        <span className="text-[10px] font-bold uppercase">{t('spiders.last_sync')}</span>
                                    </div>
                                    <p className="text-xl font-bold">+{source.last_run_new || 0}</p>
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

                            {/* Categories Table */}
                            {relatedSources.length > 0 && (
                                <div className="space-y-3">
                                    <h3 className="text-sm font-bold flex items-center justify-between px-1">
                                        <div className="flex items-center gap-2">
                                            <List size={16} className="text-orange-500" />
                                            {t('categories.title')}
                                        </div>
                                        <span className="text-[10px] bg-[var(--tg-theme-secondary-bg-color)] px-2 py-0.5 rounded-full">
                                            {relatedSources.length}
                                        </span>
                                    </h3>
                                    <div className="card overflow-hidden border border-white/5 shadow-inner">
                                        <div className="overflow-x-auto">
                                            <table className="w-full text-left border-collapse">
                                                <thead className="bg-[var(--tg-theme-secondary-bg-color)] text-[10px] uppercase text-[var(--tg-theme-hint-color)] font-bold">
                                                    <tr>
                                                        <th className="p-3">{t('categories.category')}</th>
                                                        <th className="p-3 text-center">{t('categories.products')}</th>
                                                        <th className="p-3 text-center">{t('categories.status')}</th>
                                                        <th className="p-3">{t('categories.last_run')}</th>
                                                    </tr>
                                                </thead>
                                                <tbody className="divide-y divide-white/5">
                                                    {relatedSources.map((rel: any) => (
                                                        <tr
                                                            key={rel.id}
                                                            className="text-xs hover:bg-[var(--tg-theme-button-color)]/5 transition-colors cursor-pointer group"
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                onOpenSource?.(rel.id);
                                                            }}
                                                        >
                                                            <td className="p-3 font-medium">
                                                                <div className="flex flex-col">
                                                                    <span className="group-hover:text-[var(--tg-theme-button-color)] transition-colors">
                                                                        {rel.config?.discovery_name || rel.site_key}
                                                                    </span>
                                                                    <span className="text-[8px] opacity-50 truncate max-w-[80px]">
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
                                                                <span className="whitespace-nowrap">{formatTimeAgo(rel.last_synced_at)}</span>
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {activeTab === 'products' && (
                        <div className="animate-in fade-in slide-in-from-top-2 duration-300 min-h-[40vh] space-y-4">
                            <div className="flex items-center justify-between px-1">
                                <h3 className="text-sm font-bold flex items-center gap-2">
                                    <Package size={16} className="text-blue-500" />
                                    {browsingSourceId !== sourceId ?
                                        source.related_sources?.find((r: any) => r.id === browsingSourceId)?.config?.discovery_name || t('stats.live_sources')
                                        : t('stats.live_sources')}
                                </h3>
                                {browsingSourceId !== sourceId && (
                                    <button
                                        onClick={() => setBrowsingSourceId(sourceId)}
                                        className="text-[10px] font-bold text-[var(--tg-theme-button-color)] flex items-center gap-1"
                                    >
                                        <ChevronRight size={12} className="rotate-180" />
                                        {t('common.main')}
                                    </button>
                                )}
                            </div>

                            {/* Show Categories if we are at root and have them */}
                            {browsingSourceId === sourceId && relatedSources.length > 0 ? (
                                <div className="grid grid-cols-1 gap-2">
                                    {relatedSources.map((rel: any) => (
                                        <button
                                            key={rel.id}
                                            onClick={() => setBrowsingSourceId(rel.id)}
                                            className="card p-4 flex items-center justify-between group active:scale-[0.98] transition-all hover:border-[var(--tg-theme-button-color)]/30"
                                        >
                                            <div className="flex flex-col items-start gap-1">
                                                <span className="font-bold text-sm group-hover:text-[var(--tg-theme-button-color)] transition-colors">
                                                    {rel.config?.discovery_name || rel.site_key}
                                                </span>
                                                <span className="text-[10px] opacity-60">
                                                    {rel.total_items || 0} {t('spiders.items')}
                                                </span>
                                            </div>
                                            <ChevronRight size={16} className="opacity-30 group-hover:translate-x-1 transition-transform" />
                                        </button>
                                    ))}
                                </div>
                            ) : (
                                <ProductsTable
                                    products={allProducts}
                                    total={productsData?.total || 0}
                                    isLoading={isLoadingProducts}
                                    onLoadMore={handleLoadMore}
                                    hasMore={allProducts.length < (productsData?.total || 0)}
                                />
                            )}
                        </div>
                    )}

                    {activeTab === 'logs' && (
                        <div className="space-y-3 animate-in fade-in slide-in-from-top-2 duration-300">
                            <div className="flex items-center justify-between px-1">
                                <h3 className="text-sm font-bold flex items-center gap-2">
                                    <Terminal size={16} className="text-blue-500" />
                                    {t('spiders.live_logs')}
                                </h3>
                                <button
                                    onClick={() => setLogFilter(prev => prev === 'all' ? 'progress' : 'all')}
                                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[10px] font-bold transition-all ${logFilter === 'progress'
                                        ? "bg-blue-500 text-white shadow-lg shadow-blue-500/20"
                                        : "bg-[var(--tg-theme-secondary-bg-color)] text-[var(--tg-theme-hint-color)]"
                                        }`}
                                >
                                    <Filter size={12} />
                                    {logFilter === 'progress' ? "PARSE ONLY" : "FULL LOGS"}
                                </button>
                            </div>

                            <div className="bg-black text-[#00ff00] font-mono text-[10px] p-4 rounded-xl overflow-x-auto h-80 border border-white/5 shadow-inner relative group">
                                <div className="absolute top-2 right-2 flex gap-1">
                                    <div className="w-2 h-2 rounded-full bg-red-500/50"></div>
                                    <div className="w-2 h-2 rounded-full bg-yellow-500/50"></div>
                                    <div className="w-2 h-2 rounded-full bg-green-500/50"></div>
                                </div>

                                <div className="space-y-1">
                                    {liveLogs.length === 0 && (
                                        <div className="opacity-50 italic">
                                            {source.status === 'running'
                                                ? "> Connecting to container stream..."
                                                : `> ${lastLogs}`}
                                        </div>
                                    )}
                                    {liveLogs
                                        .filter(log => logFilter === 'all' || log.includes('[PROGRESS]') || log.includes('[CONNECTED]'))
                                        .map((log, i) => (
                                            <div key={i} className={`whitespace-pre-wrap animate-in fade-in slide-in-from-left-1 duration-200 ${log.includes('[PROGRESS]') ? "text-blue-400 font-bold" :
                                                log.includes('[CONNECTED]') ? "text-green-400 font-bold" : ""
                                                }`}>
                                                <span className="opacity-30 mr-2">{i + 1}</span>
                                                {log.replace('[PROGRESS] ', '').replace('[CONNECTED] ', '')}
                                            </div>
                                        ))}
                                    <div ref={logsEndRef} />
                                </div>
                            </div>

                            {source.status === 'running' && (
                                <div className="flex items-center gap-2 px-2">
                                    <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></div>
                                    <span className="text-[10px] font-bold text-blue-500/80 uppercase tracking-widest animate-pulse">
                                        Live Streaming Active
                                    </span>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Actions */}
                    <div className="flex gap-2 pt-2 sticky bottom-0 bg-[var(--tg-theme-bg-color)] pb-4 mt-auto">
                        <button
                            onClick={() => onToggleActive?.(sourceId, !source.is_active)}
                            className={`p-3 rounded-xl font-bold flex items-center justify-center transition-all active:scale-95 ${source.is_active
                                ? "bg-red-500/10 text-red-500 border border-red-500/20"
                                : "bg-green-500/10 text-green-500 border border-green-500/20"
                                }`}
                            title={source.is_active ? "Disable" : "Enable"}
                        >
                            <Power size={20} />
                        </button>
                        <button
                            onClick={() => onForceRun(sourceId, "deep")}
                            disabled={isForceRunning || !source.is_active}
                            className="flex-[2] bg-[var(--tg-theme-button-color)] text-white py-3 rounded-xl font-bold flex items-center justify-center gap-2 active:scale-95 transition-all disabled:opacity-50"
                        >
                            <Play size={18} fill="white" />
                            {t('spiders.run_deep')}
                        </button>
                        <button
                            onClick={() => onForceRun(sourceId, "discovery")}
                            disabled={isForceRunning || !source.is_active}
                            className="flex-[2] border-2 border-[var(--tg-theme-button-color)] text-[var(--tg-theme-button-color)] py-3 rounded-xl font-bold flex items-center justify-center gap-2 active:scale-95 transition-all disabled:opacity-50"
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
