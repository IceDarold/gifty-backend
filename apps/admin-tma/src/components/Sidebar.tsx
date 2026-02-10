"use client";

import Link from "next/link";
import {
    LayoutDashboard,
    RefreshCcw,
    Bell,
    Settings,
    ShieldCheck,
    Activity,
    Database
} from "lucide-react";
import { usePathname } from "next/navigation";

interface SidebarProps {
    activeTab: string;
    onTabChange: (tab: string) => void;
}

export function Sidebar({ activeTab, onTabChange }: SidebarProps) {
    const menuItems = [
        { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
        { id: "scrapers", label: "Scrapers", icon: RefreshCcw },
        { id: "alerts", label: "System Alerts", icon: Bell },
        { id: "settings", label: "Settings", icon: Settings },
    ];

    return (
        <aside className="hidden lg:flex flex-col w-64 bg-[var(--tg-theme-bg-color)] border-r border-[var(--tg-theme-secondary-bg-color)] h-screen sticky top-0">
            <div className="p-6 flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-[var(--tg-theme-button-color)] flex items-center justify-center text-white">
                    <ShieldCheck size={20} />
                </div>
                <h1 className="font-bold text-xl tracking-tight">Gifty Admin</h1>
            </div>

            <nav className="flex-1 px-4 space-y-1">
                <p className="text-[10px] font-bold text-[var(--tg-theme-hint-color)] uppercase tracking-wider px-2 mb-2">Main Menu</p>
                {menuItems.map((item) => (
                    <button
                        key={item.id}
                        onClick={() => onTabChange(item.id)}
                        className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all ${activeTab === item.id
                            ? "bg-[var(--tg-theme-button-color)] text-white shadow-md shadow-blue-500/20"
                            : "text-[var(--tg-theme-hint-color)] hover:bg-[var(--tg-theme-secondary-bg-color)] hover:text-[var(--tg-theme-text-color)]"
                            }`}
                    >
                        <item.icon size={20} />
                        <span className="font-medium text-sm">{item.label}</span>
                    </button>
                ))}

                <div className="pt-8 space-y-1">
                    <p className="text-[10px] font-bold text-[var(--tg-theme-hint-color)] uppercase tracking-wider px-2 mb-2">System Resources</p>
                    <button className="w-full flex items-center gap-3 px-3 py-2 text-[var(--tg-theme-hint-color)] hover:text-[var(--tg-theme-text-color)] transition-colors">
                        <Activity size={18} />
                        <span className="text-sm font-medium">Health Monitor</span>
                    </button>
                    <button className="w-full flex items-center gap-3 px-3 py-2 text-[var(--tg-theme-hint-color)] hover:text-[var(--tg-theme-text-color)] transition-colors">
                        <Database size={18} />
                        <span className="text-sm font-medium">Database</span>
                    </button>
                </div>
            </nav>
        </aside>
    );
}
