"use client";

import { useState } from "react";
import {
    Link2,
    Globe,
    Bell,
    CheckCircle2,
    Loader2,
    ShieldCheck,
    ExternalLink,
    Mail,
    Users,
    Activity
} from "lucide-react";

interface SettingsViewProps {
    chatId?: number;
    subscriber: any;
    onConnectWeeek: (token: string) => Promise<any>;
    isConnectingWeeek: boolean;
    toggleSubscription: (topic: string, active: boolean) => void;
    setLanguage: (lang: string) => void;
}

const TOPICS = [
    { id: 'investors', label: 'Investors', icon: ShieldCheck },
    { id: 'partners', label: 'Partners', icon: Users },
    { id: 'newsletter', label: 'Newsletter', icon: Mail },
    { id: 'monitoring', label: 'Monitoring', icon: Bell },
    { id: 'scraping', label: 'Scraping Status', icon: Activity },
    { id: 'global', label: 'Global Notifications', icon: Bell },
];

export function SettingsView({
    chatId,
    subscriber,
    onConnectWeeek,
    isConnectingWeeek,
    toggleSubscription,
    setLanguage
}: SettingsViewProps) {
    const [weeekToken, setWeeekToken] = useState("");
    const [weeekStatus, setWeeekStatus] = useState<"idle" | "success" | "error">("idle");

    const handleConnectWeeek = async () => {
        if (!weeekToken) return;
        try {
            await onConnectWeeek(weeekToken);
            setWeeekStatus("success");
            setWeeekToken("");
        } catch (e) {
            setWeeekStatus("error");
        }
    };

    const isSubscribed = (topic: string) => {
        return subscriber?.subscriptions?.includes(topic) || subscriber?.subscriptions?.includes("all");
    };

    return (
        <div className="p-4 space-y-6 animate-in slide-in-from-bottom-5 duration-500">
            {/* Weeek Connection */}
            <section className="space-y-3">
                <h3 className="text-xs font-bold text-[var(--tg-theme-hint-color)] uppercase tracking-wider px-1">Integrations</h3>
                <div className="glass card p-4 space-y-4">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white shadow-lg">
                            <Link2 size={22} />
                        </div>
                        <div>
                            <h4 className="font-bold text-sm">Weeek Projects</h4>
                            <p className="text-[10px] text-[var(--tg-theme-hint-color)]">Sync tasks and project updates</p>
                        </div>
                    </div>

                    <div className="space-y-2">
                        <input
                            type="password"
                            placeholder="Enter Weeek API Token"
                            className="w-full bg-[var(--tg-theme-secondary-bg-color)] border border-[var(--tg-theme-secondary-bg-color)] rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tg-theme-button-color)] transition-all"
                            value={weeekToken}
                            onChange={(e) => setWeeekToken(e.target.value)}
                        />
                        <button
                            onClick={handleConnectWeeek}
                            disabled={isConnectingWeeek || !weeekToken}
                            className="w-full bg-[var(--tg-theme-button-color)] text-[var(--tg-theme-button-text-color)] py-3 rounded-xl font-bold text-sm shadow-lg shadow-blue-500/20 active:scale-95 transition-all flex items-center justify-center gap-2 hover:brightness-110"
                        >
                            {isConnectingWeeek ? <Loader2 size={18} className="animate-spin" /> : <CheckCircle2 size={18} />}
                            {weeekStatus === "success" ? "Connected!" : "Connect Weeek"}
                        </button>
                    </div>

                    <div className="flex items-center gap-2 text-[10px] text-[var(--tg-theme-hint-color)] justify-center">
                        <ExternalLink size={12} />
                        <a href="https://app.weeek.net/settings/api" target="_blank" className="hover:underline">Get your token from Weeek settings</a>
                    </div>
                </div>
            </section>

            {/* Subscriptions */}
            <section className="space-y-3">
                <div className="flex items-center justify-between px-1">
                    <h3 className="text-xs font-bold text-[var(--tg-theme-hint-color)] uppercase tracking-wider">Notifications</h3>
                    <span className="text-[10px] text-blue-500 font-bold">Bot Updates</span>
                </div>
                <div className="grid grid-cols-2 gap-3">
                    {TOPICS.map((topic) => (
                        <button
                            key={topic.id}
                            onClick={() => toggleSubscription(topic.id, !isSubscribed(topic.id))}
                            className={`p-4 rounded-2xl border transition-all flex flex-col items-center gap-3 active:scale-95 ${isSubscribed(topic.id)
                                    ? "bg-blue-500/10 border-blue-500/30 text-blue-500"
                                    : "bg-[var(--tg-theme-secondary-bg-color)] border-transparent text-[var(--tg-theme-hint-color)]"
                                }`}
                        >
                            <topic.icon size={24} className={isSubscribed(topic.id) ? "animate-pulse" : ""} />
                            <span className="text-[10px] font-bold text-center leading-tight">{topic.label}</span>
                            {isSubscribed(topic.id) && <div className="w-1.5 h-1.5 rounded-full bg-blue-500 shadow-sm shadow-blue-500"></div>}
                        </button>
                    ))}
                </div>
            </section>

            {/* Language Selection */}
            <section className="space-y-3 pb-8">
                <h3 className="text-xs font-bold text-[var(--tg-theme-hint-color)] uppercase tracking-wider px-1">Language / Язык</h3>
                <div className="glass card overflow-hidden">
                    <div className="divide-y divide-[var(--tg-theme-secondary-bg-color)]">
                        {[
                            { id: 'en', label: 'English', flag: '🇺🇸' },
                            { id: 'ru', label: 'Русский', flag: '🇷🇺' }
                        ].map((lang) => (
                            <button
                                key={lang.id}
                                onClick={() => setLanguage(lang.id)}
                                className="w-full px-4 py-4 flex items-center justify-between active:bg-[var(--tg-theme-secondary-bg-color)] transition-colors"
                            >
                                <div className="flex items-center gap-3">
                                    <span className="text-xl">{lang.flag}</span>
                                    <span className="text-sm font-medium">{lang.label}</span>
                                </div>
                                {subscriber?.language === lang.id && (
                                    <CheckCircle2 size={18} className="text-blue-500" />
                                )}
                            </button>
                        ))}
                    </div>
                </div>
            </section>
        </div>
    );
}
