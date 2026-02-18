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
    onSendTestNotification: (topic: string) => void;
    isSendingTest: boolean;
}


const TOPIC_ICONS = {
    investors: ShieldCheck,
    partners: Users,
    newsletter: Mail,
    monitoring: Bell,
    scraping: Activity,
    global: Bell,
    system: ShieldCheck,
};

export function SettingsView({
    chatId,
    subscriber,
    onConnectWeeek,
    isConnectingWeeek,
    toggleSubscription,
    setBackendLanguage,
    onSendTestNotification,
    isSendingTest
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
        { id: 'system', label: "System Core", icon: TOPIC_ICONS.system },
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

                {!subscriber && (
                    <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-500 text-[10px] leading-relaxed">
                        ⚠️ <b>Subscriber not found.</b> Please make sure you have started the bot by sending <code>/start</code> in Telegram.
                    </div>
                )}
                <div className="grid grid-cols-2 gap-3">
                    {topics.map((topic) => {
                        const active = isSubscribed(topic.id);
                        return (
                            <div key={topic.id} className="space-y-2">
                                <button
                                    onClick={() => toggleSubscription(topic.id, !active)}
                                    className={`w-full p-4 rounded-2xl border transition-all flex flex-col items-center gap-3 active:scale-95 group relative overflow-hidden ${active
                                        ? "bg-blue-500/10 border-blue-500/30 text-blue-500 shadow-inner"
                                        : "bg-[var(--tg-theme-secondary-bg-color)] border-transparent text-[var(--tg-theme-hint-color)] hover:border-blue-500/20"
                                        }`}
                                >
                                    <div className={`p-2 rounded-xl transition-all ${active ? "bg-blue-500 text-white shadow-lg" : "bg-black/5"}`}>
                                        <topic.icon size={20} className={active ? "animate-pulse" : ""} />
                                    </div>
                                    <span className="text-[10px] font-bold text-center leading-tight">{topic.label}</span>

                                    {active && (
                                        <div className="absolute top-2 right-2">
                                            <div className="w-2 h-2 rounded-full bg-blue-500 animate-ping absolute"></div>
                                            <div className="w-2 h-2 rounded-full bg-blue-500 relative"></div>
                                        </div>
                                    )}
                                </button>

                                {active && (
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            onSendTestNotification(topic.id);
                                        }}
                                        disabled={isSendingTest}
                                        className="w-full py-2.5 rounded-xl bg-blue-500 text-white text-[10px] font-bold uppercase tracking-wider shadow-lg shadow-blue-500/20 active:scale-95 transition-all flex items-center justify-center gap-2"
                                    >
                                        {isSendingTest ? <Loader2 size={12} className="animate-spin" /> : <Bell size={12} fill="white" />}
                                        {t('common.alerts') || "Test Notification"}
                                    </button>
                                )}
                            </div>
                        );
                    })}
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
