import api from './api';
import { ArrowLeft, Play, ToggleLeft, History, FileText, ExternalLink, ChevronRight, Settings as SettingsIcon } from 'lucide-react';
import ConfigEditor from './ConfigEditor';
import { useState, useEffect } from 'react';

const SpiderDetail = ({ sourceId, onBack }) => {
    const [source, setSource] = useState(null);
    const [loading, setLoading] = useState(true);
    const [showConfig, setShowConfig] = useState(false);
    const [actionLoading, setActionLoading] = useState(false);
    const [message, setMessage] = useState(null);

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

    useEffect(() => {
        fetchDetail();
    }, [sourceId]);

    const handleRun = async () => {
        setActionLoading(true);
        try {
            await api.post(`/internal/sources/${sourceId}/force-run`);
            setMessage({ type: 'success', text: 'Task queued successfully' });
            fetchDetail();
        } catch (err) {
            setMessage({ type: 'error', text: 'Failed to run spider' });
        } finally {
            setActionLoading(false);
            setTimeout(() => setMessage(null), 3000);
        }
    };

    const handleToggle = async () => {
        setActionLoading(true);
        try {
            await api.post(`/internal/sources/${sourceId}/toggle`, { is_active: !source.is_active });
            setMessage({ type: 'success', text: source.is_active ? 'Spider disabled' : 'Spider enabled' });
            fetchDetail();
        } catch (err) {
            setMessage({ type: 'error', text: 'Action failed' });
        } finally {
            setActionLoading(false);
            setTimeout(() => setMessage(null), 3000);
        }
    };

    if (loading) return <div className="p-4 text-slate-400">Loading details...</div>;
    if (!source) return <div className="p-4 text-red-400">Source not found</div>;

    return (
        <div className="space-y-6">
            <header className="flex items-center gap-4">
                <button onClick={onBack} className="p-2 hover:bg-slate-900 rounded-xl transition-colors">
                    <ArrowLeft size={20} />
                </button>
                <div>
                    <h2 className="text-xl font-bold capitalize">{source.site_key}</h2>
                    <div className="text-xs text-slate-500 truncate max-w-[200px]">{source.url}</div>
                </div>
            </header>

            {/* Main Stats Card */}
            <div className="bg-gradient-to-br from-slate-900 to-slate-950 border border-slate-800 rounded-3xl p-6 shadow-xl">
                <div className="flex justify-between items-start mb-6">
                    <div>
                        <div className="text-[10px] uppercase font-bold text-slate-500 tracking-widest mb-1">Status</div>
                        <div className="flex items-center gap-2">
                            <div className={`w-2.5 h-2.5 rounded-full ${source.is_active ? 'bg-emerald-500' : 'bg-slate-600'}`} />
                            <span className="font-bold">{source.status || 'Active'}</span>
                        </div>
                    </div>
                    <div className="text-right">
                        <div className="text-[10px] uppercase font-bold text-slate-500 tracking-widest mb-1">Items Scraped</div>
                        <div className="text-2xl font-black text-blue-400">
                            {source.total_items?.toLocaleString() || 0}
                        </div>
                    </div>
                </div>

                <div className="grid grid-cols-2 gap-4 pt-4 border-t border-slate-800/50">
                    <div>
                        <div className="text-[10px] text-slate-500 mb-1">Last Run</div>
                        <div className="text-xs font-semibold">{source.last_synced_at ? new Date(source.last_synced_at).toLocaleDateString() : 'Never'}</div>
                    </div>
                    <div className="text-right">
                        <div className="text-[10px] text-slate-500 mb-1">Next Sync</div>
                        <div className="text-xs font-semibold text-amber-500">In 2h 15m</div>
                    </div>
                </div>
            </div>

            {/* Actions */}
            {message && (
                <div className={`p-3 rounded-xl text-xs font-bold text-center ${message.type === 'error' ? 'bg-red-500/10 text-red-500 border border-red-500/20' : 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20'}`}>
                    {message.text}
                </div>
            )}

            <div className="flex gap-3">
                <button
                    onClick={handleRun}
                    disabled={actionLoading}
                    className="flex-1 bg-blue-600 active:bg-blue-700 p-4 rounded-2xl flex flex-col items-center justify-center gap-2 shadow-lg shadow-blue-500/20 active:scale-[0.98] transition-all disabled:opacity-50"
                >
                    <Play size={20} fill="currentColor" />
                    <span className="text-[10px] font-black uppercase">Run Now</span>
                </button>
                <button
                    onClick={handleToggle}
                    disabled={actionLoading}
                    className="flex-1 bg-slate-900 border border-slate-800 active:bg-slate-850 p-4 rounded-2xl flex flex-col items-center justify-center gap-2 active:scale-[0.98] transition-all disabled:opacity-50"
                >
                    <ToggleLeft size={20} className={source.is_active ? 'text-emerald-500' : 'text-slate-500'} />
                    <span className="text-[10px] font-black uppercase">{source.is_active ? 'Disable' : 'Enable'}</span>
                </button>
                <button
                    onClick={() => setShowConfig(true)}
                    className="flex-1 bg-slate-900 border border-slate-800 active:bg-slate-850 p-4 rounded-2xl flex flex-col items-center justify-center gap-2 active:scale-[0.98] transition-all"
                >
                    <SettingsIcon size={20} className="text-slate-400" />
                    <span className="text-[10px] font-black uppercase">Config</span>
                </button>
            </div>

            {showConfig && (
                <ConfigEditor
                    source={source}
                    onSave={() => { setShowConfig(false); fetchDetail(); }}
                    onCancel={() => setShowConfig(false)}
                />
            )}

            {/* Log Preview */}
            <section className="bg-slate-900/50 rounded-2xl border border-slate-800">
                <div className="p-4 border-b border-slate-800 flex justify-between items-center">
                    <h3 className="text-sm font-bold flex items-center gap-2">
                        <FileText size={16} className="text-slate-400" />
                        Execution Logs
                    </h3>
                    <span className="text-[10px] text-slate-500 font-mono italic">latest session</span>
                </div>
                <div className="p-4 bg-black/40 font-mono text-[10px] text-slate-400 max-h-48 overflow-y-auto whitespace-pre-wrap">
                    {source.config?.last_logs ? (
                        source.config.last_logs
                    ) : (
                        <div className="text-slate-600 italic">No logs available for this spider.</div>
                    )}
                </div>
            </section>
        </div>
    );
};

export default SpiderDetail;
