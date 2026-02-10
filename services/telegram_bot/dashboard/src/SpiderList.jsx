import React, { useEffect, useState } from 'react';
import api from './api';
import { Search, Globe, ChevronRight, Bug } from 'lucide-react';

const SpiderList = ({ onSelectSpider }) => {
    const [monitoring, setMonitoring] = useState([]);
    const [search, setSearch] = useState('');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchMon = async () => {
            try {
                const res = await api.get('/internal/monitoring');
                setMonitoring(res.data);
            } catch (err) {
                console.error('Failed to fetch monitoring', err);
            } finally {
                setLoading(false);
            }
        };
        fetchMon();
    }, []);

    const filtered = monitoring.filter(m =>
        m.site_key.toLowerCase().includes(search.toLowerCase())
    );

    if (loading) return <div className="p-4 text-slate-400">Loading spiders...</div>;

    return (
        <div className="space-y-4">
            <header className="flex justify-between items-end">
                <div>
                    <h2 className="text-2xl font-bold">Spiders</h2>
                    <p className="text-slate-400 text-sm">Monitor crawl performance</p>
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
                        className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex items-center justify-between active:scale-[0.98] transition-transform cursor-pointer"
                    >
                        <div className="flex items-center gap-3">
                            <div className={`w-2.5 h-2.5 rounded-full ${s.status === 'broken' ? 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]' : 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]'}`} />
                            <div>
                                <div className="font-semibold capitalize">{s.site_key}</div>
                                <div className="text-[10px] text-slate-500 flex items-center gap-1 mt-0.5">
                                    <Globe size={10} />
                                    {s.url ? new URL(s.url).hostname : 'N/A'}
                                </div>
                            </div>
                        </div>

                        <div className="flex items-center gap-3 text-right">
                            <div>
                                <div className="text-xs font-bold">{s.total_items} items</div>
                                <div className="text-[10px] text-slate-500">+{s.scraped_last_run || 0} today</div>
                            </div>
                            <ChevronRight size={18} className="text-slate-600" />
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default SpiderList;
