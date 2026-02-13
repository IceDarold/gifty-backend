"use client";

import { useState } from "react";
import { useLanguage } from "@/contexts/LanguageContext";
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
    setBackendLanguage: (lang: string) => void;
}


const TOPIC_ICONS = {
    investors: ShieldCheck,
    partners: Users,
    newsletter: Mail,
    monitoring: Bell,
    scraping: Activity,
    global: Bell,
};

export function SettingsView({
    chatId,
    subscriber,
    onConnectWeeek,
    isConnectingWeeek,
    toggleSubscription,
    setBackendLanguage
}: SettingsViewProps) {
    const { t, setLanguage: setUiLanguage, language } = useLanguage();
    const [weeekToken, setWeeekToken] = useState("");
    const [weeekStatus, setWeeekStatus] = useState<"idle" | "success" | "error">("idle");

    const topics = [
        { id: 'investors', label: t('settings.topics.investors'), icon: TOPIC_ICONS.investors },
        { id: 'partners', label: t('settings.topics.partners'), icon: TOPIC_ICONS.partners },
        { id: 'newsletter', label: t('settings.topics.newsletter'), icon: TOPIC_ICONS.newsletter },
        { id: 'monitoring', label: t('settings.topics.monitoring'), icon: TOPIC_ICONS.monitoring },
        { id: 'scraping', label: t('settings.topics.scraping'), icon: TOPIC_ICONS.scraping },
        { id: 'global', label: t('settings.topics.global'), icon: TOPIC_ICONS.global },
    ];

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

    const handleLanguageChange = (lang: "en" | "ru") => {
        setUiLanguage(lang);
        setBackendLanguage(lang);
    };

    return (
        <div className="p-4 space-y-6 animate-in slide-in-from-bottom-5 duration-500">
            {/* Weeek Connection */}
            <section className="space-y-3">
                <h3 className="text-xs font-bold text-[var(--tg-theme-hint-color)] uppercase tracking-wider px-1">{t('settings.integrations')}</h3>
                <div className="glass card p-4 space-y-4">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white shadow-lg">
                            <Link2 size={22} />
                        </div>
                        <div>
                            <h4 className="font-bold text-sm">{t('settings.weeek_projects')}</h4>
                            <p className="text-[10px] text-[var(--tg-theme-hint-color)]">{t('settings.weeek_desc')}</p>
                        </div>
                    </div>

                    <div className="space-y-2">
                        <input
                            type="password"
                            placeholder={t('settings.enter_token')}
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
                            {weeekStatus === "success" ? t('settings.connected') : t('settings.connect_weeek')}
                        </button>
                    </div>

                    <div className="flex items-center gap-2 text-[10px] text-[var(--tg-theme-hint-color)] justify-center">
                        <ExternalLink size={12} />
                        <a href="https://app.weeek.net/settings/api" target="_blank" className="hover:underline">{t('settings.get_token')}</a>
                    </div>
                </div>
            </section>

            {/* Subscriptions */}
            <section className="space-y-3">
                <div className="flex items-center justify-between px-1">
                    <h3 className="text-xs font-bold text-[var(--tg-theme-hint-color)] uppercase tracking-wider">{t('settings.notifications')}</h3>
                    <span className="text-[10px] text-blue-500 font-bold">{t('settings.bot_updates')}</span>
                </div>
                <div className="grid grid-cols-2 gap-3">
                    {topics.map((topic) => (
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
                <h3 className="text-xs font-bold text-[var(--tg-theme-hint-color)] uppercase tracking-wider px-1">{t('settings.language')}</h3>
                <div className="glass card overflow-hidden">
                    <div className="divide-y divide-[var(--tg-theme-secondary-bg-color)]">
                        {[
                            { id: 'en', label: t('settings.english'), flag: '🇺🇸' },
                            { id: 'ru', label: t('settings.russian'), flag: '🇷🇺' }
                        ].map((lang) => (
                            <button
                                key={lang.id}
                                onClick={() => handleLanguageChange(lang.id as "en" | "ru")}
                                className="w-full px-4 py-4 flex items-center justify-between active:bg-[var(--tg-theme-secondary-bg-color)] transition-colors"
                            >
                                <div className="flex items-center gap-3">
                                    <span className="text-xl">{lang.flag}</span>
                                    <span className="text-sm font-medium">{lang.label}</span>
                                </div>
                                {language === lang.id && (
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
