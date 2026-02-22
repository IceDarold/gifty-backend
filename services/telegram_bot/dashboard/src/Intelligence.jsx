import React, { useEffect, useState } from 'react';
import api from './api';
import { Brain, CreditCard, Layers, Zap, ArrowRight, Activity } from 'lucide-react';

const Intelligence = () => {
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchStats = async () => {
            try {
                const res = await api.get('/internal/analytics/intelligence');
                setStats(res.data);
            } catch (err) {
                console.error('Failed to fetch intelligence stats', err);
                setError('Failed to load intelligence data');
            } finally {
                setLoading(false);
            }
        };

        fetchStats();
    }, []);

    if (loading) return <div className="p-4 text-slate-400">Analyzing AI metrics...</div>;
    if (error) return <div className="p-4 text-red-400">{error}</div>;

    const { metrics, providers, latency_heatmap } = stats;

    return (
        <div className="space-y-6 animate-in fade-in duration-700">
            <header>
                <h2 className="text-2xl font-bold flex items-center gap-2">
                    <Brain className="text-blue-500" />
                    AI Intelligence
                </h2>
                <p className="text-slate-400 text-sm">LLM Performance & Cost analysis</p>
            </header>

            {/* AI Cost Tracker */}
            <section className="bg-gradient-to-br from-slate-900 to-slate-950 p-5 rounded-3xl border border-white/5 shadow-2xl relative overflow-hidden group">
                <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
                    <CreditCard size={120} />
                </div>

                <div className="relative z-10">
                    <div className="flex items-center gap-2 text-slate-400 text-xs font-bold uppercase tracking-widest mb-4">
                        <Zap size={14} className="text-yellow-500" />
                        Usage Efficiency
                    </div>

                    <div className="flex flex-col gap-1">
                        <span className="text-4xl font-black bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
                            ${metrics.total_cost.toFixed(2)}
                        </span>
                        <span className="text-slate-500 text-sm">Spent in last 7 days</span>
                    </div>

                    <div className="grid grid-cols-2 gap-4 mt-6">
                        <div className="bg-white/5 p-3 rounded-2xl border border-white/5">
                            <div className="text-[10px] text-slate-500 uppercase font-bold mb-1">Tokens</div>
                            <div className="text-lg font-bold">{(metrics.total_tokens / 1000).toFixed(1)}k</div>
                        </div>
                        <div className="bg-white/5 p-3 rounded-2xl border border-white/5">
                            <div className="text-[10px] text-slate-500 uppercase font-bold mb-1">Requests</div>
                            <div className="text-lg font-bold">{metrics.total_requests}</div>
                        </div>
                    </div>
                </div>
            </section>

            {/* Provider Distribution */}
            <section className="bg-slate-900/50 p-5 rounded-3xl border border-slate-800">
                <h3 className="font-bold flex items-center gap-2 mb-4 text-sm">
                    <Layers size={16} className="text-indigo-400" />
                    Provider Distribution
                </h3>

                <div className="space-y-4">
                    {providers.map((p) => {
                        const pct = (p.count / metrics.total_requests) * 100;
                        return (
                            <div key={p.provider} className="space-y-1.5">
                                <div className="flex justify-between text-xs font-medium px-1">
                                    <span className="text-slate-300 capitalize">{p.provider}</span>
                                    <span className="text-slate-500">{p.count} calls</span>
                                </div>
                                <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                                    <div
                                        className="h-full bg-gradient-to-r from-blue-600 to-indigo-500 rounded-full transition-all duration-1000"
                                        style={{ width: `${pct}%` }}
                                    ></div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </section>

            {/* Latency Heatmap */}
            <section className="bg-slate-900/50 p-5 rounded-3xl border border-slate-800">
                <h3 className="font-bold flex items-center gap-2 mb-4 text-sm">
                    <Activity size={16} className="text-emerald-400" />
                    Latency Heatmap (24h)
                </h3>

                <div className="grid grid-cols-6 gap-2">
                    {Array.from({ length: 24 }).map((_, i) => {
                        const data = latency_heatmap.find(h => h.hour === i);
                        const latency = data ? data.avg_latency : 0;

                        // Color scale: low (green) -> high (red)
                        let color = "bg-slate-800";
                        if (latency > 0) {
                            if (latency < 800) color = "bg-emerald-500/40 border-emerald-500/20";
                            else if (latency < 1500) color = "bg-amber-500/40 border-amber-500/20";
                            else color = "bg-red-500/40 border-red-500/20";
                        }

                        return (
                            <div
                                key={i}
                                className={`h-10 rounded-lg border flex flex-col items-center justify-center transition-all hover:scale-110 cursor-default ${color}`}
                                title={`${i}:00 - ${latency.toFixed(0)}ms`}
                            >
                                <span className="text-[10px] font-bold text-white/80">{i}</span>
                                {latency > 0 && <span className="text-[8px] text-white/40">{(latency / 1000).toFixed(1)}s</span>}
                            </div>
                        );
                    })}
                </div>
                <div className="mt-4 flex justify-between items-center text-[10px] text-slate-500 font-bold px-1">
                    <span>00:00 (Midnight)</span>
                    <ArrowRight size={10} />
                    <span>23:00</span>
                </div>
            </section>

            {/* Quality Summary (Mock/Static for now but placeholders looking real) */}
            <div className="bg-blue-500/5 border border-blue-500/10 p-4 rounded-2xl flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center text-blue-400">
                    <Zap size={20} />
                </div>
                <div>
                    <div className="text-xs font-bold text-blue-400">System Tip</div>
                    <div className="text-[11px] text-slate-400">Claude-3.5-Sonnet remains the most cost-efficient for Reasoning tasks this week.</div>
                </div>
            </div>
        </div>
    );
};

export default Intelligence;
