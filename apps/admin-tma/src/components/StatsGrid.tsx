"use client";

import { Activity, Database, AlertCircle, ShoppingCart, Loader2 } from "lucide-react";

interface StatItemProps {
    label: string;
    value: string;
    subValue: string;
    icon: React.ReactNode;
    color: string;
    testId?: string;
    isLoading?: boolean;
}

function StatItem({ label, value, subValue, icon, color, testId, isLoading }: StatItemProps) {
    return (
        <div className="card flex flex-col gap-2" data-testid={testId}>
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${color} bg-opacity-10 mb-1`}>
                {icon}
            </div>
            <p className="text-[var(--tg-theme-hint-color)] text-[10px] uppercase font-bold tracking-wider">{label}</p>
            <div className="flex flex-col">
                <span className="text-xl font-bold leading-none" data-testid={testId ? `${testId}-value` : undefined}>
                    {isLoading ? <Loader2 size={16} className="animate-spin inline-block" /> : value}
                </span>
                <span className="text-xs text-[var(--tg-theme-accent-text-color)] mt-1" data-testid={testId ? `${testId}-sub` : undefined}>{subValue}</span>
            </div>
        </div>
    );
}

interface StatsGridProps {
    stats?: any;
    health?: any;
    scraping?: any;
    isLoading?: boolean;
}

export function StatsGrid({ stats, health, scraping, isLoading }: StatsGridProps) {
    return (
        <div className="grid grid-cols-2 gap-3 p-4" data-testid="stats-grid">
            <StatItem
                label="Active Spiders"
                value={scraping?.active_sources?.toString() || "0"}
                subValue="Live sources"
                icon={<Activity size={18} className="text-[#5288c1]" />}
                color="bg-[#5288c1]"
                testId="stat-active-spiders"
                isLoading={isLoading}
            />
            <StatItem
                label="Items Scraped"
                value={(scraping?.items_scraped_24h || 0).toLocaleString()}
                subValue="In last 24h"
                icon={<Database size={18} className="text-[#64b5ef]" />}
                color="bg-[#64b5ef]"
                testId="stat-items-scraped"
                isLoading={isLoading}
            />
            <StatItem
                label="Discovery Rate"
                value={`${stats?.quiz_completion_rate || 0}%`}
                subValue="Conversion"
                icon={<ShoppingCart size={18} className="text-[#2481cc]" />}
                color="bg-[#2481cc]"
                testId="stat-discovery-rate"
                isLoading={isLoading}
            />
            <StatItem
                label="Latency"
                value={`${health?.api_latency_ms || 0}ms`}
                subValue="System speed"
                icon={<AlertCircle size={18} className="text-[#ff3b30]" />}
                color="bg-[var(--tg-theme-button-color)]"
                testId="stat-latency"
                isLoading={isLoading}
            />
        </div>
    );
}
