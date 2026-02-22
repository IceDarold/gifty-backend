import api from './api';
import { ArrowLeft, Play, ToggleLeft, ToggleRight, History, FileText, Settings as SettingsIcon, Loader2, Sparkles, Trash2, TrendingUp, Terminal, Radio } from 'lucide-react';
import ConfigEditor from './ConfigEditor';
import { useState, useEffect, useRef } from 'react';

// Умный polling: активные скраперы обновляются каждые 5 сек
const FAST_POLL = 5000;
const SLOW_POLL = 30000;

const SpiderDetail = ({ sourceId, onBack }) => {
    const [source, setSource] = useState(null);
    const [loading, setLoading] = useState(true);
    const [showConfig, setShowConfig] = useState(false);
    const [actionLoading, setActionLoading] = useState(false);
    const [message, setMessage] = useState(null);

    // Live Logs
    const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'logs'
    const [liveLogs, setLiveLogs] = useState([]);
    const logsEndRef = useRef(null);
    const eventSourceRef = useRef(null);

    const showMessage = (type, text) => {
        setMessage({ type, text });
        setTimeout(() => setMessage(null), 3000);
    };

    const fetchDetail = async () => {
        try {
            const res = await api.get(`/internal/sources/${sourceId}`);
            setSource(res.data);
        } catch (err) {
            console.error('Failed to fetch source detail', err);
        } finally {
            setLoading(false);
        }
    };

    // Начальная загрузка и smart polling
    useEffect(() => {
        setLoading(true);
        fetchDetail();
    }, [sourceId]);

    useEffect(() => {
        if (!source) return;
        const isActive = source.status === 'running' || source.status === 'queued';
        const interval = setInterval(fetchDetail, isActive ? FAST_POLL : SLOW_POLL);
        return () => clearInterval(interval);
    }, [source?.status, sourceId]);

    // SSE лог-стрим
    useEffect(() => {
        if (activeTab !== 'logs') {
            // Закрываем стрим при переключении на другой таб
            if (eventSourceRef.current) {
                eventSourceRef.current.close();
                eventSourceRef.current = null;
            }
            return;
        }

        setLiveLogs([]); // очищаем при открытии
        const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1';
        const url = `${baseUrl}/internal/sources/${sourceId}/logs`;
        const es = new EventSource(url);
        eventSourceRef.current = es;

        es.onopen = () => {
            setLiveLogs(['[CONNECTED] Live log stream started...']);
        };
        es.onmessage = (e) => {
            if (e.data === ':ping') return;
            setLiveLogs(prev => {
                const next = [...prev, e.data];
                return next.slice(-200); // не больше 200 строк
            });
        };
        es.onerror = () => {
            es.close();
            setLiveLogs(prev => [...prev, '[DISCONNECTED] Log stream ended.']);
        };

        return () => {
            es.close();
            eventSourceRef.current = null;
        };
    }, [activeTab, sourceId]);

    // Авто-скролл вниз
    useEffect(() => {
        if (activeTab === 'logs') {
            logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }
    }, [liveLogs, activeTab]);

    const handleRun = async (strategy = 'deep') => {
        setActionLoading(true);
        try {
            await api.post(`/internal/sources/${sourceId}/force-run`, { strategy });
            showMessage('success', `${strategy === 'deep' ? 'Deep run' : 'Discovery run'} queued!`);
            setTimeout(fetchDetail, 1500);
        } catch (err) {
            showMessage('error', 'Failed to run spider');
        } finally {
            setActionLoading(false);
        }
    };

    const handleToggle = async () => {
        setActionLoading(true);
        try {
            await api.post(`/internal/sources/${sourceId}/toggle`, { is_active: !source.is_active });
            showMessage('success', source.is_active ? 'Spider disabled' : 'Spider enabled');
            fetchDetail();
        } catch (err) {
            showMessage('error', 'Action failed');
        } finally {
            setActionLoading(false);
        }
    };

    const handleClearData = async () => {
        if (!window.confirm(`Clear all scraped data for "${source?.site_key}"? This cannot be undone.`)) return;
        setActionLoading(true);
        try {
            await api.delete(`/internal/sources/${sourceId}/data`);
            showMessage('success', 'All data cleared successfully');
            fetchDetail();
        } catch (err) {
            showMessage('error', 'Failed to clear data');
        } finally {
            setActionLoading(false);
        }
    };

    if (loading) return (
        <div className="flex flex-col items-center justify-center py-20 animate-in fade-in zoom-in duration-700">
            <div className="relative mb-8">
                <div className="absolute inset-0 bg-blue-500/20 blur-3xl rounded-full animate-pulse"></div>
                <div className="relative bg-slate-900 border border-slate-800 p-6 rounded-full shadow-2xl">
                    <Loader2 className="animate-spin text-blue-400" size={48} />
                </div>
                <div className="absolute -top-2 -right-2">
                    <div className="bg-slate-900 border border-slate-800 p-2 rounded-full animate-bounce">
                        <Sparkles className="text-amber-400" size={16} />
                    </div>
                </div>
            </div>
            <h3 className="text-xl font-bold bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">Loading...</h3>
        </div>
    );

    if (!source) return <div className="p-4 text-red-400">Source not found</div>;

    const isRunning = source.status === 'running' || source.status === 'queued';

    return (
        <div className="space-y-4 animate-in slide-in-from-bottom-4 fade-in duration-500">
            {/* Header */}
            <header className="flex items-center gap-4">
                <button onClick={onBack} className="p-2 hover:bg-slate-900 rounded-xl transition-colors">
                    <ArrowLeft size={20} />
                </button>
                <div className="flex-1 min-w-0">
                    <h2 className="text-xl font-bold capitalize">{source.site_key}</h2>
                    <div className="text-xs text-slate-500 truncate">{source.url || 'No URL configured'}</div>
                </div>
                {isRunning && (
                    <div className="flex items-center gap-1.5 px-2.5 py-1 bg-blue-500/10 border border-blue-500/20 rounded-full">
                        <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse" />
                        <span className="text-[10px] font-bold uppercase text-blue-400">
                            {source.status}
                        </span>
                    </div>
                )}
            </header>

            {/* Stats Card */}
            <div className="bg-gradient-to-br from-slate-900 to-slate-950 border border-slate-800 rounded-3xl p-5 shadow-xl relative overflow-hidden">
                <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/5 blur-3xl -mr-16 -mt-16"></div>
                <div className="flex justify-between items-start mb-5 relative">
                    <div>
                        <div className="text-[10px] uppercase font-bold text-slate-500 tracking-widest mb-1">Status</div>
                        <div className="flex items-center gap-2">
                            <div className={`w-2.5 h-2.5 rounded-full ${isRunning ? 'bg-blue-500 animate-pulse shadow-[0_0_8px_rgba(59,130,246,0.6)]' :
                                    source.is_active ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' :
                                        'bg-slate-600'
                                }`} />
                            <span className="font-bold capitalize">{source.status || (source.is_active ? 'active' : 'disabled')}</span>
                        </div>
                    </div>
                    <div className="text-right">
                        <div className="text-[10px] uppercase font-bold text-slate-500 tracking-widest mb-1">Items Scraped</div>
                        <div className="text-2xl font-black bg-gradient-to-br from-blue-400 to-indigo-400 bg-clip-text text-transparent">
                            {source.total_items?.toLocaleString() || 0}
                        </div>
                    </div>
                </div>
                <div className="grid grid-cols-2 gap-4 pt-4 border-t border-slate-800/50 relative">
                    <div>
                        <div className="text-[10px] text-slate-500 mb-1">Last Run</div>
                        <div className="text-xs font-semibold">
                            {source.last_synced_at
                                ? new Date(source.last_synced_at).toLocaleString()
                                : 'Never'
                            }
                        </div>
                    </div>
                    <div className="text-right">
                        <div className="text-[10px] text-slate-500 mb-1">Source ID</div>
                        <div className="text-xs font-mono text-slate-400">#{sourceId}</div>
                    </div>
                </div>
            </div>

            {/* Message */}
            {message && (
                <div className={`p-3 rounded-xl text-xs font-bold text-center animate-in slide-in-from-top-2 fade-in ${message.type === 'error'
                        ? 'bg-red-500/10 text-red-500 border border-red-500/20'
                        : 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20'
                    }`}>
                    {message.text}
                </div>
            )}

            {/* Action Buttons */}
            <div className="grid grid-cols-4 gap-2">
                <button
                    onClick={() => handleRun('deep')}
                    disabled={actionLoading || !source.is_active}
                    className="col-span-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 p-3.5 rounded-2xl flex flex-col items-center justify-center gap-1.5 shadow-lg shadow-blue-500/20 active:scale-[0.98] transition-all"
                >
                    <Play size={18} fill="currentColor" />
                    <span className="text-[10px] font-black uppercase">Run Deep</span>
                </button>

                <button
                    onClick={() => handleRun('discovery')}
                    disabled={actionLoading || !source.is_active}
                    className="bg-indigo-600/30 border border-indigo-500/30 hover:bg-indigo-600/50 disabled:opacity-50 p-3.5 rounded-2xl flex flex-col items-center justify-center gap-1.5 active:scale-[0.98] transition-all"
                >
                    <TrendingUp size={18} className="text-indigo-400" />
                    <span className="text-[10px] font-black uppercase text-indigo-300">Discov.</span>
                </button>

                <button
                    onClick={handleToggle}
                    disabled={actionLoading}
                    className="bg-slate-900 border border-slate-800 hover:border-slate-700 p-3.5 rounded-2xl flex flex-col items-center justify-center gap-1.5 active:scale-[0.98] transition-all disabled:opacity-50"
                >
                    {source.is_active
                        ? <ToggleRight size={18} className="text-emerald-500" />
                        : <ToggleLeft size={18} className="text-slate-500" />
                    }
                    <span className="text-[10px] font-black uppercase text-slate-400">
                        {source.is_active ? 'Disable' : 'Enable'}
                    </span>
                </button>
            </div>

            {/* Secondary actions row */}
            <div className="grid grid-cols-3 gap-2">
                <button
                    onClick={() => setShowConfig(true)}
                    className="bg-slate-900 border border-slate-800 hover:border-slate-700 p-3 rounded-xl flex items-center justify-center gap-2 text-slate-400 text-xs font-bold active:scale-95 transition-all"
                >
                    <SettingsIcon size={15} /> Config
                </button>
                <button
                    onClick={() => setActiveTab(activeTab === 'logs' ? 'overview' : 'logs')}
                    className={`border p-3 rounded-xl flex items-center justify-center gap-2 text-xs font-bold active:scale-95 transition-all ${activeTab === 'logs'
                            ? 'bg-green-500/10 border-green-500/30 text-green-400'
                            : 'bg-slate-900 border-slate-800 hover:border-slate-700 text-slate-400'
                        }`}
                >
                    <Terminal size={15} /> {activeTab === 'logs' ? 'Hide Logs' : 'Live Logs'}
                </button>
                <button
                    onClick={handleClearData}
                    disabled={actionLoading}
                    className="bg-orange-500/10 border border-orange-500/20 hover:bg-orange-500/20 text-orange-400 disabled:opacity-50 p-3 rounded-xl flex items-center justify-center gap-2 text-xs font-bold active:scale-95 transition-all"
                >
                    <Trash2 size={15} /> Clear
                </button>
            </div>

            {/* Config Editor */}
            {showConfig && (
                <ConfigEditor
                    source={source}
                    onSave={() => { setShowConfig(false); fetchDetail(); }}
                    onCancel={() => setShowConfig(false)}
                />
            )}

            {/* Live Logs Terminal */}
            {activeTab === 'logs' && (
                <section className="bg-black rounded-2xl border border-slate-800 overflow-hidden shadow-inner">
                    <div className="p-3 border-b border-slate-800 flex justify-between items-center bg-slate-900/50">
                        <h3 className="text-xs font-bold flex items-center gap-2">
                            <Radio size={12} className="text-green-400 animate-pulse" />
                            Live Stream
                        </h3>
                        <div className="flex gap-1">
                            <div className="w-2 h-2 rounded-full bg-red-500/40"></div>
                            <div className="w-2 h-2 rounded-full bg-amber-500/40"></div>
                            <div className="w-2 h-2 rounded-full bg-green-500/40"></div>
                        </div>
                    </div>
                    <div className="p-3 font-mono text-[10px] text-green-400/80 max-h-72 overflow-y-auto whitespace-pre-wrap leading-relaxed space-y-0.5">
                        {liveLogs.length === 0 && (
                            <div className="text-slate-600 italic py-4 text-center">Connecting to log stream...</div>
                        )}
                        {liveLogs.map((line, i) => (
                            <div key={i} className={`${line.includes('ERROR') ? 'text-red-400' :
                                    line.includes('WARN') ? 'text-amber-400' :
                                        line.includes('[CONNECTED]') ? 'text-emerald-400' :
                                            line.includes('[DISCONNECTED]') ? 'text-slate-500 italic' :
                                                'text-green-400/70'
                                }`}>
                                {line}
                            </div>
                        ))}
                        <div ref={logsEndRef} />
                    </div>
                </section>
            )}

            {/* Static Log Preview (когда лайв-стрим закрыт) */}
            {activeTab === 'overview' && (
                <section className="bg-slate-900/50 rounded-2xl border border-slate-800 overflow-hidden shadow-inner">
                    <div className="p-4 border-b border-slate-800 flex justify-between items-center bg-slate-900/50">
                        <h3 className="text-sm font-bold flex items-center gap-2">
                            <FileText size={16} className="text-slate-400" />
                            Last Execution Log
                        </h3>
                        <div className="flex gap-1">
                            <div className="w-2 h-2 rounded-full bg-red-500/20"></div>
                            <div className="w-2 h-2 rounded-full bg-amber-500/20"></div>
                            <div className="w-2 h-2 rounded-full bg-emerald-500/20"></div>
                        </div>
                    </div>
                    <div className="p-4 bg-black/40 font-mono text-[10px] text-slate-400 max-h-48 overflow-y-auto whitespace-pre-wrap leading-relaxed">
                        {source.config?.last_logs ? (
                            source.config.last_logs
                        ) : (
                            <div className="text-slate-600 italic py-4 text-center">No logs available.</div>
                        )}
                    </div>
                </section>
            )}
        </div>
    );
};

export default SpiderDetail;
