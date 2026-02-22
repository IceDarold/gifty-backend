import React, { useState, useEffect } from 'react';
import { Search, Globe, ChevronRight, RefreshCw, Play, Zap, AlertTriangle } from 'lucide-react';
import api from './api';

// Умный polling: 5 секунд если есть активные, иначе 30 секунд
const getPollingInterval = (data) => {
    if (!Array.isArray(data)) return 30000;
    const hasActive = data.some(s => s.status === 'running' || s.status === 'queued');
    return hasActive ? 5000 : 30000;
};

const statusDot = (status) => {
    if (status === 'running') return 'bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.6)] animate-pulse';
    if (status === 'broken') return 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]';
    if (status === 'queued') return 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.5)] animate-pulse';
    if (status === 'idle') return 'bg-slate-600';
    return 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]';
};

const SpiderList = ({ data, onSelectSpider, onRefresh }) => {
    const [search, setSearch] = useState('');
    const [refreshing, setRefreshing] = useState(false);
    const [runningAll, setRunningAll] = useState(false);

    // Smart polling — обновляем данные автоматически
    useEffect(() => {
        const interval = setInterval(() => {
            onRefresh(true);
        }, getPollingInterval(data));
        return () => clearInterval(interval);
    }, [data, onRefresh]);

    const handleRefresh = async () => {
        setRefreshing(true);
        await onRefresh(true);
        setRefreshing(false);
    };

    const handleRunAll = async () => {
        setRunningAll(true);
        try {
            await api.post('/internal/sources/run-all');
            // Через 2 секунды обновим список чтобы увидеть статусы
            setTimeout(() => onRefresh(true), 2000);
        } catch (err) {
            console.error('Failed to run all spiders', err);
        } finally {
            setRunningAll(false);
        }
    };

    if (!data) return <div className="p-4 text-slate-400">Loading spiders...</div>;

    const filtered = Array.isArray(data) ? data.filter(m =>
        m.site_key.toLowerCase().includes(search.toLowerCase())
    ) : [];

    const activeCount = filtered.filter(s => s.status === 'running' || s.status === 'queued').length;

    return (
        <div className="space-y-4">
            <header className="flex justify-between items-center">
                <div>
                    <h2 className="text-2xl font-bold">Spiders</h2>
                    <p className="text-slate-400 text-sm">
                        {activeCount > 0
                            ? <span className="text-blue-400 font-semibold">{activeCount} running</span>
                            : 'Monitor crawl performance'
                        }
                    </p>
                </div>
                <div className="flex gap-2">
                    {/* Run All */}
                    <button
                        onClick={handleRunAll}
                        disabled={runningAll}
                        className="flex items-center gap-1.5 px-3 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-xl text-xs font-bold uppercase transition-all active:scale-90"
                    >
                        <Play size={14} fill="currentColor" className={runningAll ? 'animate-pulse' : ''} />
                        {runningAll ? 'Starting...' : 'Run All'}
                    </button>
                    {/* Refresh */}
                    <button
                        onClick={handleRefresh}
                        className={`p-2.5 bg-slate-900 border border-slate-800 rounded-xl text-slate-400 hover:text-white transition-all active:scale-90`}
                    >
                        <RefreshCw size={18} className={refreshing ? 'animate-spin' : ''} />
                    </button>
                </div>
            </header>

            {/* Search */}
            <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={18} />
                <input
                    type="text"
                    placeholder="Search by site key..."
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl py-2.5 pl-10 pr-4 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none transition-shadow"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                />
            </div>

            {/* List */}
            <div className="space-y-2">
                {filtered.map(s => (
                    <div
                        key={s.site_key}
                        onClick={() => onSelectSpider(s.id)}
                        className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex items-center justify-between active:scale-[0.98] transition-transform cursor-pointer hover:border-slate-700"
                    >
                        <div className="flex items-center gap-3">
                            <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${statusDot(s.status)}`} />
                            <div>
                                <div className="font-semibold capitalize">{s.site_key}</div>
                                <div className="text-[10px] text-slate-500 flex items-center gap-1 mt-0.5">
                                    <Globe size={10} />
                                    {s.url ? (() => { try { return new URL(s.url).hostname; } catch { return s.url; } })() : 'N/A'}
                                </div>
                            </div>
                        </div>

                        <div className="flex items-center gap-3 text-right">
                            <div>
                                <div className="text-xs font-bold">{s.total_items?.toLocaleString() || 0} items</div>
                                <div className={`text-[10px] capitalize ${s.status === 'running' ? 'text-blue-400' :
                                        s.status === 'broken' ? 'text-red-400' :
                                            s.status === 'queued' ? 'text-amber-400' :
                                                'text-slate-500'
                                    }`}>
                                    {s.status || 'idle'}
                                </div>
                            </div>
                            {s.status === 'broken' && <AlertTriangle size={16} className="text-red-400" />}
                            {s.status !== 'broken' && <ChevronRight size={18} className="text-slate-600" />}
                        </div>
                    </div>
                ))}

                {filtered.length === 0 && (
                    <div className="text-center py-12 text-slate-600">
                        <Zap size={32} className="mx-auto mb-3 opacity-20" />
                        <div className="text-sm">No spiders found</div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default SpiderList;
