import React, { useState, useEffect } from 'react';
import { Search, ExternalLink, Tag, Package, RefreshCw } from 'lucide-react';

const Catalog = ({ data, onRefresh, search: initialSearch, page: initialPage, onSearchChange, onPageChange }) => {
    const [refreshing, setRefreshing] = useState(false);

    const handleRefresh = async () => {
        setRefreshing(true);
        await onRefresh(true);
        setRefreshing(false);
    };

    if (!data && !refreshing) return <div className="p-4 text-slate-400">Loading catalog...</div>;

    const products = data?.items || [];
    const total = data?.total || 0;
    const limit = 20;
    const totalPages = Math.ceil(total / limit);

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <header className="flex justify-between items-end">
                <div>
                    <h2 className="text-2xl font-bold">Product Catalog</h2>
                    <p className="text-slate-400 text-sm">Browse and manage scraped items</p>
                </div>
                <div className="flex items-center gap-4">
                    <button
                        onClick={handleRefresh}
                        className={`p-3 bg-slate-900 border border-slate-800 rounded-2xl text-slate-400 hover:text-white transition-all active:scale-90 ${refreshing ? 'animate-spin' : ''}`}
                    >
                        <RefreshCw size={20} />
                    </button>
                    <div className="text-right">
                        <span className="text-[10px] font-mono text-slate-500 uppercase tracking-widest leading-none">Total Items</span>
                        <div className="text-xl font-bold text-blue-400 leading-tight">{total.toLocaleString()}</div>
                    </div>
                </div>
            </header>

            {/* Search bar */}
            <div className="relative group">
                <div className="absolute -inset-0.5 bg-gradient-to-r from-blue-500/20 to-purple-500/20 rounded-2xl blur opacity-0 group-focus-within:opacity-100 transition duration-500"></div>
                <div className="relative">
                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" size={18} />
                    <input
                        type="text"
                        placeholder="Search items by title..."
                        className="w-full bg-slate-900/80 backdrop-blur-xl border border-slate-800 rounded-2xl py-4 pl-12 pr-4 text-sm focus:outline-none focus:border-blue-500/50 transition-all shadow-xl"
                        value={initialSearch}
                        onChange={(e) => onSearchChange(e.target.value)}
                    />
                </div>
            </div>

            {/* Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {refreshing ? (
                    <div className="col-span-full py-20 text-center">
                        <div className="inline-block animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500 mb-4"></div>
                        <div className="text-slate-500 text-sm">Updating catalog...</div>
                    </div>
                ) : products.length === 0 ? (
                    <div className="col-span-full py-20 text-center text-slate-500 bg-slate-900/30 rounded-3xl border border-dashed border-slate-800">
                        <Package size={32} className="mx-auto mb-3 opacity-20" />
                        No products found matching your search
                    </div>
                ) : (
                    products.map(p => (
                        <div key={p.gift_id} className="bg-slate-900/50 backdrop-blur-sm border border-slate-800/50 rounded-2xl overflow-hidden flex h-32 group hover:border-blue-500/30 hover:bg-slate-800/50 transition-all duration-300">
                            <div className="w-32 bg-slate-800 flex-shrink-0 relative overflow-hidden">
                                {p.image_url ? (
                                    <img src={p.image_url} alt="" className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
                                ) : (
                                    <div className="w-full h-full flex items-center justify-center text-slate-600">
                                        <Package size={24} />
                                    </div>
                                )}
                                {p.merchant && (
                                    <div className="absolute top-2 left-2 px-2 py-0.5 bg-black/60 backdrop-blur-md rounded text-[9px] font-bold text-blue-300 uppercase tracking-tighter border border-white/5">
                                        {p.merchant}
                                    </div>
                                )}
                            </div>
                            <div className="p-3 flex flex-col justify-between flex-grow min-w-0">
                                <div>
                                    <h3 className="text-sm font-semibold truncate leading-tight mb-1 group-hover:text-blue-400 transition-colors">{p.title}</h3>
                                    <div className="flex items-center gap-2">
                                        <span className="text-[10px] text-slate-500 flex items-center gap-1 bg-slate-800/50 px-2 py-0.5 rounded-full">
                                            <Tag size={10} className="text-slate-400" /> {p.category || 'Uncategorized'}
                                        </span>
                                    </div>
                                </div>
                                <div className="flex justify-between items-end">
                                    <div>
                                        <div className="text-[9px] text-slate-500 uppercase font-bold tracking-widest mb-0.5">Price</div>
                                        <div className="text-md font-bold text-emerald-400">
                                            {p.price ? `${Number(p.price).toLocaleString()} ${p.currency || 'RUB'}` : 'Contact Us'}
                                        </div>
                                    </div>
                                    <a href={p.product_url} target="_blank" rel="noopener noreferrer" className="p-2.5 bg-slate-800 rounded-xl hover:bg-blue-500 hover:text-white transition-all transform hover:scale-105 shadow-lg border border-white/5">
                                        <ExternalLink size={14} />
                                    </a>
                                </div>
                            </div>
                        </div>
                    ))
                )}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
                <div className="flex justify-center items-center gap-6 py-8 border-t border-slate-800/50">
                    <button
                        onClick={() => { onPageChange(Math.max(0, initialPage - 1)); window.scrollTo(0, 0); }}
                        disabled={initialPage === 0}
                        className="w-10 h-10 flex items-center justify-center bg-slate-900 border border-slate-800 rounded-xl text-sm disabled:opacity-30 disabled:cursor-not-allowed hover:border-blue-500/50 transition-all font-bold"
                    >
                        ←
                    </button>
                    <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-blue-400">{initialPage + 1}</span>
                        <span className="text-[10px] text-slate-500 uppercase font-bold tracking-widest">of</span>
                        <span className="text-xs font-bold text-slate-400">{totalPages}</span>
                    </div>
                    <button
                        onClick={() => { onPageChange(Math.min(totalPages - 1, initialPage + 1)); window.scrollTo(0, 0); }}
                        disabled={initialPage === totalPages - 1}
                        className="w-10 h-10 flex items-center justify-center bg-slate-900 border border-slate-800 rounded-xl text-sm disabled:opacity-30 disabled:cursor-not-allowed hover:border-blue-500/50 transition-all font-bold"
                    >
                        →
                    </button>
                </div>
            )}
        </div>
    );
};

export default Catalog;
