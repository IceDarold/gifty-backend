"use client";

import { useTMA } from "@/components/TMAProvider";
import { Bell, Settings, User } from "lucide-react";
import { useLanguage } from "@/contexts/LanguageContext";

export function DashboardHeader() {
    const tma = useTMA();
    const { t } = useLanguage();

    return (
        <header className="sticky top-0 z-20 px-4 pt-4">
            <div className="glass rounded-2xl px-4 py-3.5 flex items-center justify-between border border-white/10">
            <div className="flex items-center gap-3">
                <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-[#68d2ff] to-[#1599de] flex items-center justify-center text-[#03263d] font-black text-lg shadow-lg shadow-[#0f9ce0]/30">
                    {tma?.user?.first_name?.[0] || <User size={20} />}
                </div>
                <div>
                    <h1 className="font-black text-[15px] leading-tight">
                        {tma?.user?.first_name || "Admin"} {tma?.user?.last_name || ""}
                    </h1>
                    <p className="text-[10px] uppercase tracking-[0.14em] text-[var(--tg-theme-subtitle-text-color)]">{t('common.superadmin_panel')}</p>
                </div>
            </div>
            <div className="flex items-center gap-2.5">
                <button className="p-2.5 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 active:scale-95 transition-all">
                    <Bell size={20} className="text-[var(--tg-theme-hint-color)]" />
                </button>
                <button className="p-2.5 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 active:scale-95 transition-all">
                    <Settings size={20} className="text-[var(--tg-theme-hint-color)]" />
                </button>
            </div>
            </div>
        </header>
    );
}
