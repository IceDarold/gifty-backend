"use client";

import { useEffect, useState } from "react";
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
    runtimeSettings?: any;
    runtimeSettingsLoading?: boolean;
    runtimeSettingsError?: unknown;
    onUpdateRuntimeSettings?: (payload: Record<string, unknown>) => Promise<any>;
    onRestoreRuntimeSettingsDefaults?: () => Promise<any>;
    isUpdatingRuntimeSettings?: boolean;
    merchants?: { items?: any[]; total?: number };
    merchantsLoading?: boolean;
    merchantsError?: unknown;
    onUpdateMerchant?: (siteKey: string, payload: { name?: string; base_url?: string }) => Promise<any>;
    isUpdatingMerchant?: boolean;
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
    isSendingTest,
    runtimeSettings,
    runtimeSettingsLoading,
    runtimeSettingsError,
    onUpdateRuntimeSettings,
    onRestoreRuntimeSettingsDefaults,
    isUpdatingRuntimeSettings,
    merchants,
    merchantsLoading,
    merchantsError,
    onUpdateMerchant,
    isUpdatingMerchant,
}: SettingsViewProps) {
    const { t, setLanguage: setUiLanguage, language } = useLanguage();
    const [weeekToken, setWeeekToken] = useState("");
    const [weeekStatus, setWeeekStatus] = useState<"idle" | "success" | "error">("idle");
    const [perfDraft, setPerfDraft] = useState<Record<string, any>>({});
    const [merchantQuery, setMerchantQuery] = useState("");
    const [merchantEditing, setMerchantEditing] = useState<Record<string, { name?: string; base_url?: string; field?: "name" | "base_url" }>>({});

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

    const settingsItem = runtimeSettings?.item;
    const intervalEntries = Object.entries((settingsItem?.ops_client_intervals || {}) as Record<string, number>);

    const merchantItems = (merchants?.items || []) as any[];
    const filteredMerchants = merchantQuery.trim()
        ? merchantItems.filter((m) => {
            const q = merchantQuery.trim().toLowerCase();
            return String(m.site_key || "").toLowerCase().includes(q) || String(m.name || "").toLowerCase().includes(q);
        })
        : merchantItems;

    const startEditMerchant = (siteKey: string, field: "name" | "base_url", currentValue?: string) => {
        setMerchantEditing((prev) => ({
            ...prev,
            [siteKey]: {
                ...(prev[siteKey] || {}),
                field,
                [field]: currentValue ?? "",
            },
        }));
    };

    const commitMerchantEdit = async (siteKey: string) => {
        if (!onUpdateMerchant) return;
        const draft = merchantEditing[siteKey];
        if (!draft?.field) return;
        const payload: { name?: string; base_url?: string } = {};
        if (draft.field === "name") payload.name = String(draft.name ?? "").trim();
        if (draft.field === "base_url") payload.base_url = String(draft.base_url ?? "").trim();
        await onUpdateMerchant(siteKey, payload);
        setMerchantEditing((prev) => {
            const next = { ...prev };
            delete next[siteKey];
            return next;
        });
    };

    useEffect(() => {
        if (!settingsItem) return;
        setPerfDraft({
            ops_aggregator_enabled: !!settingsItem?.ops_aggregator_enabled,
            ops_aggregator_interval_ms: Number(settingsItem?.ops_aggregator_interval_ms ?? 2000),
            ops_snapshot_ttl_ms: Number(settingsItem?.ops_snapshot_ttl_ms ?? 10000),
            ops_stale_max_age_ms: Number(settingsItem?.ops_stale_max_age_ms ?? 60000),
            ops_client_intervals: { ...(settingsItem?.ops_client_intervals || {}) },
        });
    }, [settingsItem]);

    const applyRuntimeSettings = async () => {
        if (!onUpdateRuntimeSettings) return;
        const bounds = settingsItem?.bounds || {};
        const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, Math.trunc(value)));
        const intervalMin = Number(bounds?.ops_client_intervals?.min ?? 1000);
        const intervalMax = Number(bounds?.ops_client_intervals?.max ?? 600000);
        const nextIntervals: Record<string, number> = {};
        for (const [key, value] of Object.entries((perfDraft.ops_client_intervals || {}) as Record<string, number>)) {
            const asNum = Number(value);
            nextIntervals[key] = clamp(Number.isFinite(asNum) ? asNum : intervalMin, intervalMin, intervalMax);
        }
        const nextPayload = {
            ops_aggregator_enabled: !!perfDraft.ops_aggregator_enabled,
            ops_aggregator_interval_ms: clamp(
                Number(perfDraft.ops_aggregator_interval_ms ?? 2000),
                Number(bounds?.ops_aggregator_interval_ms?.min ?? 500),
                Number(bounds?.ops_aggregator_interval_ms?.max ?? 60000),
            ),
            ops_snapshot_ttl_ms: clamp(
                Number(perfDraft.ops_snapshot_ttl_ms ?? 10000),
                Number(bounds?.ops_snapshot_ttl_ms?.min ?? 1000),
                Number(bounds?.ops_snapshot_ttl_ms?.max ?? 300000),
            ),
            ops_stale_max_age_ms: clamp(
                Number(perfDraft.ops_stale_max_age_ms ?? 60000),
                Number(bounds?.ops_stale_max_age_ms?.min ?? 5000),
                Number(bounds?.ops_stale_max_age_ms?.max ?? 600000),
            ),
            ops_client_intervals: nextIntervals,
        };
        await onUpdateRuntimeSettings(nextPayload);
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

            <section className="space-y-3">
                <h3 className="text-xs font-bold text-[var(--tg-theme-hint-color)] uppercase tracking-wider px-1">System / Performance</h3>
                <div className="glass card p-4 space-y-3">
                    {runtimeSettingsLoading ? (
                        <div className="text-xs text-[var(--tg-theme-hint-color)] inline-flex items-center gap-2">
                            <Loader2 size={12} className="animate-spin" /> Loading runtime settings...
                        </div>
                    ) : runtimeSettingsError ? (
                        <div className="text-xs text-rose-300">Failed to load runtime settings.</div>
                    ) : (
                        <>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                <label className="text-[11px] text-[var(--tg-theme-hint-color)]">
                                    Aggregator enabled
                                    <div className="mt-1">
                                        <input
                                            type="checkbox"
                                            checked={!!perfDraft.ops_aggregator_enabled}
                                            onChange={(e) => setPerfDraft((prev) => ({ ...prev, ops_aggregator_enabled: e.target.checked }))}
                                        />
                                    </div>
                                </label>
                                <label className="text-[11px] text-[var(--tg-theme-hint-color)]">
                                    Aggregator interval (ms)
                                    <input
                                        type="number"
                                        className="mt-1 w-full bg-[var(--tg-theme-secondary-bg-color)] border border-[var(--tg-theme-secondary-bg-color)] rounded-lg px-3 py-2 text-sm"
                                        value={Number(perfDraft.ops_aggregator_interval_ms ?? 2000)}
                                        onChange={(e) => setPerfDraft((prev) => ({ ...prev, ops_aggregator_interval_ms: Number(e.target.value || 0) }))}
                                    />
                                </label>
                                <label className="text-[11px] text-[var(--tg-theme-hint-color)]">
                                    Snapshot TTL (ms)
                                    <input
                                        type="number"
                                        className="mt-1 w-full bg-[var(--tg-theme-secondary-bg-color)] border border-[var(--tg-theme-secondary-bg-color)] rounded-lg px-3 py-2 text-sm"
                                        value={Number(perfDraft.ops_snapshot_ttl_ms ?? 10000)}
                                        onChange={(e) => setPerfDraft((prev) => ({ ...prev, ops_snapshot_ttl_ms: Number(e.target.value || 0) }))}
                                    />
                                </label>
                                <label className="text-[11px] text-[var(--tg-theme-hint-color)]">
                                    Stale max age (ms)
                                    <input
                                        type="number"
                                        className="mt-1 w-full bg-[var(--tg-theme-secondary-bg-color)] border border-[var(--tg-theme-secondary-bg-color)] rounded-lg px-3 py-2 text-sm"
                                        value={Number(perfDraft.ops_stale_max_age_ms ?? 60000)}
                                        onChange={(e) => setPerfDraft((prev) => ({ ...prev, ops_stale_max_age_ms: Number(e.target.value || 0) }))}
                                    />
                                </label>
                            </div>

                            <div className="rounded-xl border border-white/10 p-2">
                                <p className="text-[11px] text-[var(--tg-theme-hint-color)] mb-2">Client intervals (ms)</p>
                                <div className="max-h-56 overflow-auto space-y-1 pr-1">
                                    {intervalEntries.map(([key, value]) => (
                                        <label key={key} className="grid grid-cols-[1fr_110px] items-center gap-2 text-[11px] text-white/90">
                                            <span className="truncate">{key}</span>
                                            <input
                                                type="number"
                                                className="w-full bg-[var(--tg-theme-secondary-bg-color)] border border-[var(--tg-theme-secondary-bg-color)] rounded-md px-2 py-1 text-xs"
                                                value={Number((perfDraft.ops_client_intervals || {})[key] ?? value)}
                                                onChange={(e) =>
                                                    setPerfDraft((prev) => ({
                                                        ...prev,
                                                        ops_client_intervals: {
                                                            ...(prev.ops_client_intervals || {}),
                                                            [key]: Number(e.target.value || 0),
                                                        },
                                                    }))
                                                }
                                            />
                                        </label>
                                    ))}
                                </div>
                            </div>

                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => void applyRuntimeSettings()}
                                    disabled={!onUpdateRuntimeSettings || !!isUpdatingRuntimeSettings}
                                    className="px-4 py-2 rounded-lg bg-[var(--tg-theme-button-color)] text-[var(--tg-theme-button-text-color)] text-xs font-semibold disabled:opacity-50"
                                >
                                    {isUpdatingRuntimeSettings ? "Applying..." : "Apply"}
                                </button>
                                <button
                                    onClick={() => void onRestoreRuntimeSettingsDefaults?.()}
                                    disabled={!onRestoreRuntimeSettingsDefaults || !!isUpdatingRuntimeSettings}
                                    className="px-4 py-2 rounded-lg border border-white/20 text-xs font-semibold disabled:opacity-50"
                                >
                                    Restore defaults
                                </button>
                                <span className="text-[10px] text-[var(--tg-theme-hint-color)]">
                                    v{settingsItem?.settings_version || 1}
                                    {settingsItem?.updated_at ? ` · ${new Date(settingsItem.updated_at).toLocaleString()}` : ""}
                                </span>
                            </div>
                        </>
                    )}
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

            <section className="space-y-3">
                <h3 className="text-xs font-bold text-[var(--tg-theme-hint-color)] uppercase tracking-wider px-1">Merchants</h3>
                <div className="glass card p-4 space-y-3">
                    {merchantsLoading ? (
                        <div className="text-xs text-[var(--tg-theme-hint-color)] inline-flex items-center gap-2">
                            <Loader2 size={12} className="animate-spin" /> Loading merchants...
                        </div>
                    ) : merchantsError ? (
                        <div className="text-xs text-rose-300">Failed to load merchants.</div>
                    ) : (
                        <>
                            <div className="flex items-center gap-2">
                                <input
                                    value={merchantQuery}
                                    onChange={(e) => setMerchantQuery(e.target.value)}
                                    placeholder="Search site_key/name..."
                                    className="flex-1 rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-xs outline-none focus:border-sky-400/40"
                                />
                                <div className="text-[10px] text-[var(--tg-theme-hint-color)]">
                                    {(merchants?.total ?? merchantItems.length) || 0}
                                </div>
                            </div>

                            <div className="space-y-2">
                                {filteredMerchants.length === 0 ? (
                                    <div className="text-xs text-[var(--tg-theme-hint-color)]">No merchants.</div>
                                ) : (
                                    filteredMerchants.map((m) => {
                                        const siteKey = String(m.site_key || "");
                                        const edit = merchantEditing[siteKey];
                                        const editingField = edit?.field;
                                        const isEditingName = editingField === "name";
                                        const isEditingBase = editingField === "base_url";

                                        return (
                                            <div key={siteKey} className="rounded-2xl border border-white/10 bg-black/15 p-3">
                                                <div className="flex items-start justify-between gap-3">
                                                    <div className="min-w-0 flex-1">
                                                        <div className="text-[10px] uppercase tracking-[0.14em] text-[var(--tg-theme-hint-color)]">
                                                            {siteKey}
                                                        </div>
                                                        <div className="mt-1 flex items-center gap-2">
                                                            {isEditingName ? (
                                                                <input
                                                                    autoFocus
                                                                    value={String(edit?.name ?? "")}
                                                                    onChange={(e) =>
                                                                        setMerchantEditing((prev) => ({
                                                                            ...prev,
                                                                            [siteKey]: { ...(prev[siteKey] || {}), field: "name", name: e.target.value },
                                                                        }))
                                                                    }
                                                                    onBlur={() => void commitMerchantEdit(siteKey)}
                                                                    onKeyDown={(e) => {
                                                                        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
                                                                        if (e.key === "Escape") setMerchantEditing((prev) => {
                                                                            const next = { ...prev };
                                                                            delete next[siteKey];
                                                                            return next;
                                                                        });
                                                                    }}
                                                                    className="w-full rounded-xl border border-sky-400/30 bg-black/25 px-2.5 py-2 text-xs outline-none focus:border-sky-400/60"
                                                                />
                                                            ) : (
                                                                <>
                                                                    <div className="text-sm font-semibold truncate">{m.name || siteKey}</div>
                                                                    <button
                                                                        onClick={() => startEditMerchant(siteKey, "name", m.name || siteKey)}
                                                                        className="rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-[10px] text-[var(--tg-theme-hint-color)] hover:text-white"
                                                                        title="Edit name"
                                                                    >
                                                                        ✎
                                                                    </button>
                                                                </>
                                                            )}
                                                        </div>

                                                        <div className="mt-2 flex items-center gap-2">
                                                            <span className="text-[10px] text-[var(--tg-theme-hint-color)]">Base URL</span>
                                                            {isEditingBase ? (
                                                                <input
                                                                    autoFocus
                                                                    value={String(edit?.base_url ?? "")}
                                                                    onChange={(e) =>
                                                                        setMerchantEditing((prev) => ({
                                                                            ...prev,
                                                                            [siteKey]: { ...(prev[siteKey] || {}), field: "base_url", base_url: e.target.value },
                                                                        }))
                                                                    }
                                                                    onBlur={() => void commitMerchantEdit(siteKey)}
                                                                    onKeyDown={(e) => {
                                                                        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
                                                                        if (e.key === "Escape") setMerchantEditing((prev) => {
                                                                            const next = { ...prev };
                                                                            delete next[siteKey];
                                                                            return next;
                                                                        });
                                                                    }}
                                                                    className="w-full rounded-xl border border-sky-400/30 bg-black/25 px-2.5 py-2 text-xs outline-none focus:border-sky-400/60"
                                                                />
                                                            ) : (
                                                                <>
                                                                    <div className="text-[11px] text-[var(--tg-theme-hint-color)] truncate">
                                                                        {m.base_url || "--"}
                                                                    </div>
                                                                    <button
                                                                        onClick={() => startEditMerchant(siteKey, "base_url", m.base_url || "")}
                                                                        className="rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-[10px] text-[var(--tg-theme-hint-color)] hover:text-white"
                                                                        title="Edit base url"
                                                                    >
                                                                        ✎
                                                                    </button>
                                                                </>
                                                            )}
                                                        </div>
                                                    </div>

                                                    {isUpdatingMerchant ? (
                                                        <div className="text-[10px] text-[var(--tg-theme-hint-color)] inline-flex items-center gap-1.5">
                                                            <Loader2 size={12} className="animate-spin" /> saving
                                                        </div>
                                                    ) : null}
                                                </div>
                                            </div>
                                        );
                                    })
                                )}
                            </div>
                        </>
                    )}
                </div>
            </section>
        </div>
    );
}
