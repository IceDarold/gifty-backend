"use client";

import { useTMA } from "@/components/TMAProvider";
import { Bell, Settings, User } from "lucide-react";

export function DashboardHeader() {
    const tma = useTMA();

    return (
        <header className="flex items-center justify-between p-4 sticky top-0 bg-[var(--tg-theme-bg-color)] z-10 border-b border-[var(--tg-theme-secondary-bg-color)]">
            <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#5288c1] to-[#2481cc] flex items-center justify-center text-white font-bold text-lg shadow-lg">
                    {tma?.user?.first_name?.[0] || <User size={20} />}
                </div>
                <div>
                    <h1 className="font-bold text-sm leading-tight">
                        {tma?.user?.first_name || "Admin"} {tma?.user?.last_name || ""}
                    </h1>
                    <p className="text-xs text-[var(--tg-theme-hint-color)]">Superadmin Panel</p>
                </div>
            </div>
            <div className="flex items-center gap-2">
                <button className="p-2 rounded-full active:bg-[var(--tg-theme-secondary-bg-color)] transition-colors">
                    <Bell size={20} className="text-[var(--tg-theme-hint-color)]" />
                </button>
                <button className="p-2 rounded-full active:bg-[var(--tg-theme-secondary-bg-color)] transition-colors">
                    <Settings size={20} className="text-[var(--tg-theme-hint-color)]" />
                </button>
            </div>
        </header>
    );
}
