"use client";

import { Activity, Database, AlertCircle, ShoppingCart } from "lucide-react";
import { useLanguage } from "@/contexts/LanguageContext";

interface StatItemProps {
    label: string;
    value: string;
    subValue: string;
    icon: React.ReactNode;
    color: string;
}

function StatItem({ label, value, subValue, icon, color }: StatItemProps) {
    return (
        <div className="card flex flex-col gap-2">
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${color} bg-opacity-10 mb-1`}>
                {icon}
            </div>
            <p className="text-[var(--tg-theme-hint-color)] text-[10px] uppercase font-bold tracking-wider">{label}</p>
            <div className="flex flex-col">
                <span className="text-xl font-bold leading-none">{value}</span>
                <span className="text-xs text-[var(--tg-theme-accent-text-color)] mt-1">{subValue}</span>
            </div>
        </div>
    );
}

interface StatsGridProps {
    stats?: any;
    health?: any;
    scraping?: any;
}

export function StatsGrid({ stats, health, scraping }: StatsGridProps) {
    const { t } = useLanguage();
    const latencyValue = (() => {
        if (typeof health?.api_latency_ms === "number") return health.api_latency_ms;
        const raw = health?.api?.latency;
        if (typeof raw === "string") {
            const parsed = parseInt(raw.replace("ms", ""), 10);
            if (Number.isFinite(parsed)) return parsed;
        }
        return 0;
    })();

    return (
        <div className="grid grid-cols-2 gap-3 p-4">
            <StatItem
                label={t('stats.active_spiders')}
                value={scraping?.active_sources?.toString() || "0"}
                subValue={t('stats.live_sources')}
                icon={<Activity size={18} className="text-[#5288c1]" />}
                color="bg-[#5288c1]"
            />
            <StatItem
                label={t('stats.items_scraped')}
                value={(scraping?.items_scraped_24h || 0).toLocaleString()}
                subValue={t('stats.in_last_24h')}
                icon={<Database size={18} className="text-[#64b5ef]" />}
                color="bg-[#64b5ef]"
            />
            <StatItem
                label={t('stats.discovery_rate')}
                value={`${stats?.quiz_completion_rate || 0}%`}
                subValue={t('stats.conversion')}
                icon={<ShoppingCart size={18} className="text-[#2481cc]" />}
                color="bg-[#2481cc]"
            />
            <StatItem
                label={t('stats.latency')}
                value={`${latencyValue}ms`}
                subValue={t('stats.system_speed')}
                icon={<AlertCircle size={18} className="text-[#ff3b30]" />}
                color="bg-[var(--tg-theme-button-color)]"
            />
        </div>
    );
}
