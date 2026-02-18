"use client";

import { CheckCircle2, AlertTriangle, RefreshCcw, ExternalLink } from "lucide-react";
import { useLanguage } from "@/contexts/LanguageContext";

interface SpiderListProps {
    sources?: any[];
    onSync?: () => void;
    onOpenDetail?: (id: number) => void;
    isSyncing?: boolean;
}

export function SpiderList({ sources = [], onSync, onOpenDetail, isSyncing }: SpiderListProps) {
    const { t } = useLanguage();

    return (
        <div className="p-4 space-y-3">
            <div className="flex items-center justify-between mb-2">
                <h2 className="font-bold text-lg">{t('spiders.connected_spiders')}</h2>
                {onSync && (
                    <button
                        onClick={onSync}
                        disabled={isSyncing}
                        className={`text-xs font-bold px-3 py-1.5 rounded-full bg-[var(--tg-theme-button-color)] text-white flex items-center gap-1.5 transition-all active:scale-95 ${isSyncing ? 'opacity-50 grayscale' : ''}`}
                    >
                        <RefreshCcw size={12} className={isSyncing ? 'animate-spin' : ''} />
                        {isSyncing ? t('spiders.syncing') : t('spiders.sync_now')}
                    </button>
                )}
            </div>
            <div className="space-y-2">
                {(() => {
                    const uniqueSites = sources.reduce((acc: any[], current) => {
                        const existing = acc.find(s => s.site_key === current.site_key);
                        if (!existing) {
                            acc.push(current);
                        } else if (current.type === 'hub') {
                            // Prefer hub type for the main list
                            const index = acc.indexOf(existing);
                            acc[index] = current;
                        }
                        return acc;
                    }, []);

                    return uniqueSites.length > 0 ? (
                        uniqueSites.map((spider) => (
                            <div key={spider.id} className="card flex items-center justify-between py-3">
                                <div className="flex items-center gap-3">
                                    <div className={`p-2 rounded-lg ${spider.status === 'running' ? 'bg-[#5288c1] bg-opacity-20 text-[#5288c1]' :
                                        spider.status === 'broken' || spider.config?.fix_required ? 'bg-[#ff3b30] bg-opacity-20 text-[#ff3b30]' :
                                            'bg-[#999999] bg-opacity-20 text-[#999999]'
                                        }`}>
                                        {spider.status === 'running' ? <RefreshCcw size={20} className="animate-spin" /> :
                                            spider.status === 'broken' || spider.config?.fix_required ? <AlertTriangle size={20} /> :
                                                <CheckCircle2 size={20} />}
                                    </div>
                                    <div>
                                        <p className="font-bold text-sm leading-tight">{spider.site_key || spider.name}</p>
                                        <p className="text-[10px] text-[var(--tg-theme-hint-color)]">
                                            {(spider.total_items || 0).toLocaleString()} {t('spiders.items')} • {spider.last_synced_at ? t('spiders.synced') : t('spiders.new')}
                                        </p>
                                    </div>
                                </div>
                                <button
                                    onClick={() => onOpenDetail?.(spider.id)}
                                    className="p-2 rounded-lg bg-[var(--tg-theme-secondary-bg-color)] group hover:bg-[var(--tg-theme-button-color)] transition-colors active:scale-95"
                                >
                                    <ExternalLink size={16} className="text-[var(--tg-theme-hint-color)] group-hover:text-white" />
                                </button>

                            </div>
                        ))
                    ) : (
                        <div className="card py-10 text-center opacity-50">
                            <p className="text-sm">{t('spiders.no_spiders')}</p>
                            <p className="text-[10px] mt-1">{t('spiders.click_sync')}</p>
                        </div>
                    );
                })()}
            </div>
        </div>
    );
}
