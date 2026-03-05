"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useTMA } from "@/components/TMAProvider";
import { Bell, Settings, User } from "lucide-react";
import { useLanguage } from "@/contexts/LanguageContext";
import { useNotificationCenter } from "@/contexts/NotificationCenterContext";

export function DashboardHeader() {
    const tma = useTMA();
    const { t } = useLanguage();
    const { events, unreadCount, markAllRead, clear, markRead } = useNotificationCenter();
    const [open, setOpen] = useState(false);
    const anchorRef = useRef<HTMLButtonElement | null>(null);
    const popoverRef = useRef<HTMLDivElement | null>(null);

    const orderedEvents = useMemo(() => [...events].sort((a, b) => b.lastTs - a.lastTs).slice(0, 200), [events]);

    useEffect(() => {
        if (!open) return;
        const handleClick = (evt: MouseEvent) => {
            const target = evt.target as Node | null;
            if (!target) return;
            if (anchorRef.current?.contains(target)) return;
            if (popoverRef.current?.contains(target)) return;
            setOpen(false);
        };
        const handleKeyDown = (evt: KeyboardEvent) => {
            if (evt.key === "Escape") setOpen(false);
        };
        window.addEventListener("mousedown", handleClick);
        window.addEventListener("keydown", handleKeyDown);
        return () => {
            window.removeEventListener("mousedown", handleClick);
            window.removeEventListener("keydown", handleKeyDown);
        };
    }, [open]);

    const formatTs = (ts: number) => {
        try {
            return new Date(ts).toLocaleString(undefined, { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" });
        } catch {
            return "";
        }
    };

    const levelClass = (level: string) => {
        switch (level) {
            case "running":
                return "border-sky-300/35 bg-sky-500/10 text-sky-100";
            case "success":
                return "border-emerald-300/35 bg-emerald-500/10 text-emerald-100";
            case "warn":
                return "border-amber-300/35 bg-amber-500/10 text-amber-100";
            case "error":
                return "border-rose-300/35 bg-rose-500/10 text-rose-100";
            default:
                return "border-white/15 bg-white/[0.04] text-white/90";
        }
    };

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
                <div className="relative">
                    <button
                        ref={anchorRef}
                        className="relative p-2.5 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 active:scale-95 transition-all"
                        onClick={() => setOpen((v) => !v)}
                        aria-label="Notifications"
                        aria-expanded={open}
                    >
                        <Bell size={20} className="text-[var(--tg-theme-hint-color)]" />
                        {unreadCount > 0 ? (
                            <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] rounded-full bg-rose-500 text-[10px] font-bold text-white grid place-items-center px-1 border border-black/30">
                                {unreadCount > 99 ? "99+" : unreadCount}
                            </span>
                        ) : null}
                    </button>
                    {open ? (
                        <div
                            ref={popoverRef}
                            className="absolute right-0 mt-2 w-[420px] max-w-[calc(100vw-2rem)] rounded-2xl border border-white/12 bg-[#0b1220]/95 shadow-2xl backdrop-blur-xl overflow-hidden z-50"
                        >
                            <div className="flex items-center justify-between gap-2 px-4 py-3 border-b border-white/10">
                                <div className="min-w-0">
                                    <p className="text-sm font-black text-white/95 leading-tight">Уведомления</p>
                                    <p className="text-[11px] text-white/60">
                                        {orderedEvents.length ? `${orderedEvents.length} за период · ${unreadCount} непрочитано` : "Пока нет уведомлений"}
                                    </p>
                                </div>
                                <div className="flex items-center gap-2">
                                    <button
                                        className="rounded-lg border border-white/10 bg-white/5 px-2.5 py-1.5 text-[11px] font-semibold text-white/85 hover:bg-white/10 active:scale-95 transition-all"
                                        onClick={markAllRead}
                                        disabled={!unreadCount}
                                    >
                                        Прочитать
                                    </button>
                                    <button
                                        className="rounded-lg border border-white/10 bg-white/5 px-2.5 py-1.5 text-[11px] font-semibold text-white/85 hover:bg-white/10 active:scale-95 transition-all"
                                        onClick={clear}
                                        disabled={!orderedEvents.length}
                                    >
                                        Очистить
                                    </button>
                                </div>
                            </div>
                            <div className="max-h-[58vh] overflow-y-auto p-3 space-y-2">
                                {!orderedEvents.length ? (
                                    <div className="rounded-xl border border-dashed border-white/15 bg-white/[0.03] p-4 text-sm text-white/70">
                                        Здесь будут показываться уведомления за последние 48 часов.
                                    </div>
                                ) : (
                                    orderedEvents.map((e) => (
                                        <button
                                            key={e.id}
                                            className={`w-full text-left rounded-xl border p-3 ${levelClass(e.level)} hover:bg-white/10 transition-all`}
                                            onClick={() => markRead(e.id)}
                                        >
                                            <div className="flex items-start justify-between gap-3">
                                                <div className="min-w-0">
                                                    <p className="text-sm font-bold leading-tight">
                                                        {e.title}
                                                        {!e.readAt ? <span className="ml-2 inline-block align-middle w-1.5 h-1.5 rounded-full bg-white/70" /> : null}
                                                    </p>
                                                    <p className="mt-0.5 text-xs opacity-90 break-words">{e.message}</p>
                                                    <p className="mt-1 text-[10px] opacity-70">
                                                        {formatTs(e.lastTs)}
                                                        {e.count > 1 ? ` · ×${e.count}` : ""}
                                                    </p>
                                                </div>
                                            </div>
                                        </button>
                                    ))
                                )}
                            </div>
                        </div>
                    ) : null}
                </div>
                <button className="p-2.5 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 active:scale-95 transition-all">
                    <Settings size={20} className="text-[var(--tg-theme-hint-color)]" />
                </button>
            </div>
            </div>
        </header>
    );
}
