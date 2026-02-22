"use client";

import { useLanguage } from "@/contexts/LanguageContext";
import { ExternalLink, Tag, Package, Clock, Globe, Loader2 } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { ru, enUS } from "date-fns/locale";

interface ProductsTableProps {
    products: any[];
    total: number;
    isLoading: boolean;
    onLoadMore: () => void;
    hasMore: boolean;
}

export function ProductsTable({ products, total, isLoading, onLoadMore, hasMore }: ProductsTableProps) {
    const { t, language } = useLanguage();
    const dateLocale = language === 'ru' ? ru : enUS;

    const formatPrice = (price?: number, currency?: string) => {
        if (price === undefined || price === null) return "--";
        return new Intl.NumberFormat(language === 'ru' ? 'ru-RU' : 'en-US', {
            style: 'currency',
            currency: currency || 'RUB',
        }).format(price);
    };

    if (isLoading && (!products || products.length === 0)) {
        return (
            <div className="flex flex-col items-center justify-center py-12 space-y-4">
                <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                <p className="text-xs text-[var(--tg-theme-hint-color)]">Loading products...</p>
            </div>
        );
    }

    if (!products || products.length === 0) {
        return (
            <div className="text-center py-12 glass card">
                <Package size={48} className="mx-auto mb-3 opacity-20" />
                <p className="text-sm font-medium">{t('categories.no_data') || "No products found"}</p>
                <p className="text-[10px] text-[var(--tg-theme-hint-color)] mt-1">This parser hasn't successfully ingested items yet.</p>
            </div>
        );
    }

    return (
        <div className="space-y-4 pb-20">
            <div className="flex justify-between items-center px-1">
                <span className="text-[10px] font-bold text-[var(--tg-theme-hint-color)] uppercase tracking-widest">
                    {t('dashboard.user_activity') || "Total"}: {total}
                </span>
            </div>

            <div className="space-y-3">
                {products.map((product) => (
                    <div key={product.gift_id} className="glass card p-3 flex gap-4 group hover:border-blue-500/30 transition-all">
                        {/* Image */}
                        <div className="w-16 h-16 rounded-xl bg-[var(--tg-theme-secondary-bg-color)] overflow-hidden flex-shrink-0 relative border border-white/5 shadow-inner">
                            {product.image_url ? (
                                <img
                                    src={product.image_url}
                                    alt={product.title}
                                    className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500"
                                    onError={(e) => {
                                        (e.target as HTMLImageElement).src = "https://placehold.co/100x100?text=No+Image";
                                    }}
                                />
                            ) : (
                                <div className="w-full h-full flex items-center justify-center opacity-20">
                                    <Package size={24} />
                                </div>
                            )}
                        </div>

                        {/* Info */}
                        <div className="flex-1 min-w-0 flex flex-col justify-between py-0.5">
                            <div className="space-y-1">
                                <div className="flex items-start justify-between gap-2">
                                    <h4 className="text-xs font-bold leading-tight line-clamp-2 pr-4">{product.title}</h4>
                                    <a
                                        href={product.product_url}
                                        target="_blank"
                                        className="p-1.5 rounded-lg bg-[var(--tg-theme-secondary-bg-color)] text-[var(--tg-theme-hint-color)] hover:text-blue-500 active:scale-95 transition-all"
                                    >
                                        <ExternalLink size={12} />
                                    </a>
                                </div>

                                <div className="flex flex-wrap gap-2 items-center">
                                    <span className="text-sm font-black text-blue-500">
                                        {formatPrice(product.price, product.currency)}
                                    </span>
                                    {product.category && (
                                        <div className="flex items-center gap-1 text-[8px] px-1.5 py-0.5 rounded-md bg-blue-500/10 text-blue-500 font-bold uppercase tracking-wider">
                                            <Tag size={8} />
                                            {product.category}
                                        </div>
                                    )}
                                </div>
                            </div>

                            <div className="flex items-center justify-between text-[8px] text-[var(--tg-theme-hint-color)] font-medium">
                                <div className="flex items-center gap-1">
                                    <Clock size={8} />
                                    <span>{product.updated_at ? formatDistanceToNow(new Date(product.updated_at), { addSuffix: true, locale: dateLocale }) : '--'}</span>
                                </div>
                                <div className="flex items-center gap-1">
                                    <Globe size={8} />
                                    <span className="truncate max-w-[60px]">{product.merchant || product.gift_id.split(':')[0]}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {hasMore && (
                <button
                    onClick={onLoadMore}
                    disabled={isLoading}
                    className="w-full py-3 rounded-xl border-2 border-[var(--tg-theme-button-color)]/20 text-[var(--tg-theme-button-color)] font-bold text-xs active:scale-95 transition-all flex items-center justify-center gap-2"
                >
                    {isLoading ? <Loader2 size={14} className="animate-spin" /> : null}
                    {t('common.load_more') || "Load More"}
                </button>
            )}
        </div>
    );
}
