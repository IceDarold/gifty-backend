"use client";

import { ArrowUpRight, ExternalLink, Package, RefreshCcw, Search } from "lucide-react";

interface CatalogViewProps {
    data?: { items?: any[]; total?: number };
    isLoading: boolean;
    pendingNewItems?: number;
    search: string;
    page: number;
    pageSize?: number;
    onSearchChange: (value: string) => void;
    onPageChange: (value: number) => void;
    onRefresh: () => void;
    onApplyNewItems?: () => void;
}

export function CatalogView({
    data,
    isLoading,
    pendingNewItems = 0,
    search,
    page,
    pageSize = 20,
    onSearchChange,
    onPageChange,
    onRefresh,
    onApplyNewItems,
}: CatalogViewProps) {
    const items = data?.items || [];
    const total = data?.total || 0;
    const totalPages = Math.max(1, Math.ceil(total / pageSize));

    return (
        <div className="p-4 pb-24 space-y-4">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-lg font-bold">Global Catalog</h2>
                    <p className="text-xs text-[var(--tg-theme-hint-color)]">{total.toLocaleString()} items</p>
                </div>
                <div className="flex items-center gap-2">
                    {pendingNewItems > 0 ? (
                        <button
                            onClick={() => onApplyNewItems?.()}
                            className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-400/45 bg-emerald-500/15 px-3 py-2 text-xs font-semibold text-emerald-100 active:scale-95 transition-all"
                            title="Load new items"
                        >
                            <ArrowUpRight size={14} />
                            {pendingNewItems} new items
                        </button>
                    ) : null}
                    <button
                        onClick={onRefresh}
                        className="p-2 rounded-xl glass text-[var(--tg-theme-button-color)] active:scale-95 transition-all"
                    >
                        <RefreshCcw size={16} />
                    </button>
                </div>
            </div>

            <div className="relative">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--tg-theme-hint-color)]" />
                <input
                    value={search}
                    onChange={(e) => onSearchChange(e.target.value)}
                    placeholder="Search by title..."
                    className="w-full pl-10 pr-3 py-2.5 rounded-xl border border-[var(--tg-theme-secondary-bg-color)] bg-[var(--tg-theme-section-bg-color)] text-sm outline-none focus:border-[var(--tg-theme-button-color)]"
                />
            </div>

            <div className="space-y-2">
                {isLoading ? (
                    <div className="card text-center text-sm text-[var(--tg-theme-hint-color)]">Loading catalog...</div>
                ) : items.length === 0 ? (
                    <div className="card text-center py-10">
                        <Package size={34} className="mx-auto mb-2 opacity-20" />
                        <p className="text-sm text-[var(--tg-theme-hint-color)]">No products found</p>
                    </div>
                ) : (
                    items.map((item: any) => (
                        <div key={item.product_id ?? item.gift_id} className="card flex gap-3">
                            <div className="w-14 h-14 rounded-lg bg-[var(--tg-theme-secondary-bg-color)] overflow-hidden">
                                {item.image_url ? (
                                    // eslint-disable-next-line @next/next/no-img-element
                                    <img src={item.image_url} alt={item.title} className="w-full h-full object-cover" />
                                ) : null}
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="text-xs font-bold line-clamp-2">{item.title}</div>
                                <div className="mt-1 text-[10px] text-[var(--tg-theme-hint-color)]">
                                    {item.merchant || "unknown"} •{" "}
                                    {item.scraped_category?.name
                                        ? `${item.scraped_category.name}${item.scraped_categories_count > 1 ? ` +${item.scraped_categories_count - 1}` : ""}`
                                        : (item.category || "uncategorized")}
                                </div>
                                <div className="mt-1 text-sm font-black text-[var(--tg-theme-button-color)]">
                                    {item.price ? `${Number(item.price).toLocaleString()} ${item.currency || "RUB"}` : "N/A"}
                                </div>
                            </div>
                            {item.product_url && (
                                <a
                                    href={item.product_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="self-center p-2 rounded-lg bg-[var(--tg-theme-secondary-bg-color)] text-[var(--tg-theme-hint-color)] hover:text-[var(--tg-theme-button-color)]"
                                >
                                    <ExternalLink size={14} />
                                </a>
                            )}
                        </div>
                    ))
                )}
            </div>

            <div className="flex items-center justify-center gap-4 pt-2">
                <button
                    onClick={() => onPageChange(Math.max(0, page - 1))}
                    disabled={page === 0}
                    className="px-3 py-2 rounded-lg border border-[var(--tg-theme-secondary-bg-color)] disabled:opacity-40"
                >
                    Prev
                </button>
                <span className="text-xs text-[var(--tg-theme-hint-color)]">
                    {page + 1} / {totalPages}
                </span>
                <button
                    onClick={() => onPageChange(Math.min(totalPages - 1, page + 1))}
                    disabled={page >= totalPages - 1}
                    className="px-3 py-2 rounded-lg border border-[var(--tg-theme-secondary-bg-color)] disabled:opacity-40"
                >
                    Next
                </button>
            </div>
        </div>
    );
}
