"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Brain, HeartPulse, LayoutDashboard, Loader2, Package, ScrollText, Settings, Workflow, Zap } from "lucide-react";
import { DashboardHeader } from "@/components/DashboardHeader";
import { StatsGrid } from "@/components/StatsGrid";
import { SpiderList } from "@/components/SpiderList";
import { SpiderDetail } from "@/components/SpiderDetail";
import { UsageChart } from "@/components/UsageChart";
import { SettingsView } from "@/components/SettingsView";
import { Intelligence } from "@/components/Intelligence";
import { InfraPanel } from "@/components/InfraPanel";
import { HealthView } from "@/components/HealthView";
import { CatalogView } from "@/components/CatalogView";
import { LogsView } from "@/components/LogsView";
import { ApiServerErrorBanner } from "@/components/ApiServerErrorBanner";
import { FrontendRoutingView } from "@/components/frontend/FrontendRoutingView";
import { useCatalogProducts, useDashboardData } from "@/hooks/useDashboard";
import { OperationsView } from "@/components/operations/OperationsView";
import { useLanguage } from "@/contexts/LanguageContext";
import { useTMA } from "@/components/TMAProvider";
import { getOpsStreamUrl } from "@/lib/api";
import { useOpsRuntimeSettings } from "@/contexts/OpsRuntimeSettingsContext";

const AVAILABLE_SPIDERS = [
    "detmir", "group_price", "inteltoys", "kassir",
    "letu", "mrgeek", "mvideo", "nashi_podarki", "vseigrushki"
];
const SIDEBAR_EXPANDED_WIDTH = 264;
const SIDEBAR_COLLAPSED_WIDTH = 78;
const SIDEBAR_DRAG_TOGGLE_THRESHOLD = 64;

type NavItem = {
    key: string;
    label: string;
    icon: React.ReactNode;
    strong?: boolean;
};

type NavSection = {
    title: string;
    items: NavItem[];
};

const parseLatency = (healthData: any): number => {
    if (typeof healthData?.api_latency_ms === "number") return healthData.api_latency_ms;
    const raw = healthData?.api?.latency;
    if (typeof raw === "string") {
        const parsed = parseInt(raw.replace("ms", ""), 10);
        return Number.isFinite(parsed) ? parsed : 0;
    }
    return 0;
};

export default function Home() {
    const [activeTab, setActiveTab] = useState("ops");
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
    const [isSidebarDragging, setIsSidebarDragging] = useState(false);
    const [selectedSourceId, setSelectedSourceId] = useState<number | null>(null);
    const [selectedSourceInitial, setSelectedSourceInitial] = useState<{ name?: string; slug?: string; url?: string } | null>(null);
    const [catalogSearch, setCatalogSearch] = useState("");
    const [catalogPage, setCatalogPage] = useState(0);
    const [catalogPendingNewItems, setCatalogPendingNewItems] = useState(0);
    const dragStateRef = useRef({ startX: 0, startCollapsed: false });

    const tma = useTMA();
    const { t } = useLanguage();
    const opsRuntimeSettings = useOpsRuntimeSettings();
    const chatId = tma?.user?.id || tma?.authUser?.id;

    const {
        stats, health, scraping, sources, trends, workers, queue, subscriber,
        syncSpiders, isSyncing, isLoading,
        forceRun, isForceRunning,
        toggleSourceActive, updateSource, isUpdatingSource,
        connectWeeek, isConnectingWeeek,
        toggleSubscription, setLanguage: setBackendLanguage,
        sendTestNotification, isSendingTest,
        runAll, isRunningAll,
        runOne, isRunningOne,
        merchants, updateMerchant, isUpdatingMerchant
    } = useDashboardData(chatId);

    const catalogLimit = 20;
    const catalogOffset = catalogPage * catalogLimit;
    const catalogQuery = useCatalogProducts(catalogLimit, catalogOffset, catalogSearch);

    useEffect(() => {
        if (activeTab !== "catalog") return;
        let source: EventSource | null = null;

        try {
            source = new EventSource(getOpsStreamUrl());
        } catch {
            return;
        }

        const handleCatalogUpdated = (event: MessageEvent) => {
            try {
                const payload = event.data ? JSON.parse(event.data) : {};
                const incoming = Number(payload?.new_items || 0);
                if (!Number.isFinite(incoming) || incoming <= 0) return;
                setCatalogPendingNewItems((prev) => prev + incoming);
            } catch {
                // Ignore malformed SSE payloads.
            }
        };

        source.addEventListener("catalog.updated", handleCatalogUpdated);

        return () => {
            source?.removeEventListener("catalog.updated", handleCatalogUpdated);
            source?.close();
        };
    }, [activeTab]);

    const heroLatency = useMemo(() => parseLatency(health.data), [health.data]);
    const sidebarWidth = sidebarCollapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_EXPANDED_WIDTH;
    const openSourceDetail = (id: number, initial?: { name?: string; slug?: string; url?: string }) => {
        setSelectedSourceId(id);
        setSelectedSourceInitial(initial ?? null);
    };

    const handleSync = () => {
        syncSpiders(AVAILABLE_SPIDERS);
    };

    const navSections: NavSection[] = [
        {
            title: "Stats",
            items: [
                {
                    key: "dashboard",
                    label: "Main",
                    icon: <LayoutDashboard size={20} fill={activeTab === "dashboard" ? "currentColor" : "none"} />,
                    strong: true,
                },
                {
                    key: "catalog",
                    label: "Catalog",
                    icon: <Package size={20} fill={activeTab === "catalog" ? "currentColor" : "none"} />,
                },
            ],
        },
        {
            title: "Parsing",
            items: [
                {
                    key: "ops",
                    label: "Operations",
                    icon: <Workflow size={20} />,
                },
            ],
        },
        {
            title: "AI",
            items: [
                {
                    key: "intelligence",
                    label: "AI",
                    icon: <Brain size={20} fill={activeTab === "intelligence" ? "currentColor" : "none"} />,
                },
            ],
        },
        {
            title: "System",
            items: [
                {
                    key: "health",
                    label: "Health",
                    icon: <HeartPulse size={20} />,
                },
                {
                    key: "logs",
                    label: "Logs",
                    icon: <ScrollText size={20} />,
                },
                {
                    key: "frontend",
                    label: "Frontend",
                    icon: <Zap size={20} />,
                },
                {
                    key: "settings",
                    label: "Settings",
                    icon: <Settings size={20} fill={activeTab === "settings" ? "currentColor" : "none"} />,
                },
            ],
        },
    ];

    const stopDraggingSidebar = () => {
        setIsSidebarDragging(false);
        document.body.style.userSelect = "";
    };

    const startSidebarResize = (event: React.PointerEvent<HTMLDivElement>) => {
        if (event.pointerType === "mouse" && event.button !== 0) return;
        event.preventDefault();
        event.stopPropagation();

        dragStateRef.current = {
            startX: event.clientX,
            startCollapsed: sidebarCollapsed,
        };
        setIsSidebarDragging(true);
        document.body.style.userSelect = "none";

        const handlePointerMove = (moveEvent: PointerEvent) => {
            const deltaX = moveEvent.clientX - dragStateRef.current.startX;
            const startedCollapsed = dragStateRef.current.startCollapsed;
            const shouldCollapse = startedCollapsed
                ? deltaX < SIDEBAR_DRAG_TOGGLE_THRESHOLD
                : deltaX <= -SIDEBAR_DRAG_TOGGLE_THRESHOLD;
            if (shouldCollapse !== sidebarCollapsed) {
                setSidebarCollapsed(shouldCollapse);
            }
        };

        const handlePointerUp = () => {
            stopDraggingSidebar();
            window.removeEventListener("pointermove", handlePointerMove);
            window.removeEventListener("pointerup", handlePointerUp);
            window.removeEventListener("pointercancel", handlePointerUp);
        };

        window.addEventListener("pointermove", handlePointerMove);
        window.addEventListener("pointerup", handlePointerUp, { once: true });
        window.addEventListener("pointercancel", handlePointerUp, { once: true });
    };

    const renderContent = () => {
        if (isLoading && activeTab !== "settings" && activeTab !== "catalog" && activeTab !== "ops") {
            return (
                <div className="flex flex-col items-center justify-center py-24 gap-4">
                    <Loader2 className="animate-spin text-[var(--tg-theme-button-color)]" size={32} />
                    <p className="text-sm text-[var(--tg-theme-hint-color)]">{t("common.loading")}</p>
                </div>
            );
        }

        switch (activeTab) {
            case "dashboard":
                return (
                    <>
                        <div className="px-4 pt-4">
                            <ApiServerErrorBanner
                                errors={[
                                    stats.error,
                                    health.error,
                                    scraping.error,
                                    sources.error,
                                    trends.error,
                                    workers.error,
                                    queue.error,
                                ]}
                                onRetry={async () => {
                                    await Promise.allSettled([
                                        stats.refetch(),
                                        health.refetch(),
                                        scraping.refetch(),
                                        sources.refetch(),
                                        trends.refetch(),
                                        workers.refetch(),
                                        queue.refetch(),
                                    ]);
                                }}
                                title="Dashboard API временно недоступен"
                            />
                        </div>
                        <div className="px-4 pt-4">
                            <div className="rounded-3xl p-6 text-white shadow-xl relative overflow-hidden border border-white/20 bg-[linear-gradient(120deg,#1a8fe0_0%,#276db6_45%,#1a4e87_100%)]">
                                <div className="relative z-10">
                                    <div className="inline-flex items-center rounded-full border border-white/30 bg-white/15 px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-white/90 mb-3">
                                        Live System
                                    </div>
                                    <h2 className="text-[1.7rem] leading-tight font-bold flex items-center gap-2">
                                        <Zap size={22} fill="white" />
                                        {heroLatency < 500 ? t("common.system_optimal") : t("common.system_high_load")}
                                    </h2>
                                    <p className="text-white/80 text-sm mt-2 max-w-2xl">
                                        {t("common.ai_recommendation", { latency: heroLatency })}
                                    </p>
                                </div>
                                <div className="absolute top-0 right-0 w-40 h-40 bg-cyan-200/25 rounded-full -mr-20 -mt-16 blur-3xl"></div>
                                <div className="absolute bottom-0 left-0 w-28 h-28 bg-sky-100/20 rounded-full -ml-10 -mb-10 blur-2xl"></div>
                            </div>
                        </div>
                        <StatsGrid stats={stats.data} health={health.data} scraping={scraping.data} />
                        <UsageChart data={trends.data} />
                        <InfraPanel workers={workers.data} queue={queue.data} />
                        <SpiderList
                            sources={sources.data?.slice(0, 3)}
                            onSync={handleSync}
                            onOpenDetail={(id) => openSourceDetail(id)}
                            isSyncing={isSyncing}
                            onRunAll={runAll}
                            isRunningAll={isRunningAll}
                            onRunOne={runOne}
                            isRunningOne={isRunningOne}
                        />
                    </>
                );
            case "ops":
                return (
                    <OperationsView onOpenSourceDetails={(id, initial) => openSourceDetail(id, initial)} />
                );
            case "catalog":
                return (
                    <>
                        <div className="px-4 pt-4">
                            <ApiServerErrorBanner
                                errors={[catalogQuery.error]}
                                onRetry={async () => {
                                    await catalogQuery.refetch();
                                }}
                                title="Catalog API временно недоступен"
                            />
                        </div>
                        <CatalogView
                            data={catalogQuery.data}
                            isLoading={catalogQuery.isLoading || catalogQuery.isFetching}
                            pendingNewItems={catalogPendingNewItems}
                            search={catalogSearch}
                            page={catalogPage}
                            onSearchChange={(value) => {
                                setCatalogSearch(value);
                                setCatalogPage(0);
                            }}
                            onPageChange={setCatalogPage}
                            onRefresh={() => {
                                void catalogQuery.refetch().finally(() => {
                                    setCatalogPendingNewItems(0);
                                });
                            }}
                            onApplyNewItems={() => {
                                void catalogQuery.refetch().finally(() => {
                                    setCatalogPendingNewItems(0);
                                });
                            }}
                        />
                    </>
                );
            case "intelligence":
                return <Intelligence />;
            case "health":
                return (
                    <>
                        <div className="px-4 pt-4">
                            <ApiServerErrorBanner
                                errors={[health.error, workers.error, queue.error]}
                                onRetry={async () => {
                                    await Promise.allSettled([
                                        health.refetch(),
                                        workers.refetch(),
                                        queue.refetch(),
                                    ]);
                                }}
                                title="Health API временно недоступен"
                            />
                        </div>
                        <HealthView health={health.data} workers={workers.data} queue={queue.data} />
                    </>
                );
            case "settings":
                return (
                    <>
                        <div className="px-4 pt-4">
                            <ApiServerErrorBanner
                                errors={[subscriber.error]}
                                onRetry={async () => {
                                    await subscriber.refetch();
                                }}
                                title="Settings API временно недоступен"
                            />
                        </div>
                        <SettingsView
                            chatId={chatId}
                            subscriber={subscriber.data}
                            onConnectWeeek={(token) => connectWeeek({ token })}
                            isConnectingWeeek={isConnectingWeeek}
                            toggleSubscription={(topic, active) => toggleSubscription({ topic, active })}
                            setBackendLanguage={(lang) => setBackendLanguage(lang)}
                            onSendTestNotification={(topic) => sendTestNotification(topic)}
                            isSendingTest={isSendingTest}
                            runtimeSettings={opsRuntimeSettings.data}
                            runtimeSettingsLoading={opsRuntimeSettings.isLoading}
                            runtimeSettingsError={opsRuntimeSettings.error}
                            onUpdateRuntimeSettings={opsRuntimeSettings.updateSettings}
                            onRestoreRuntimeSettingsDefaults={opsRuntimeSettings.restoreDefaults}
                            isUpdatingRuntimeSettings={opsRuntimeSettings.isUpdating}
                            merchants={merchants.data}
                            merchantsLoading={merchants.isLoading}
                            merchantsError={merchants.error}
                            onUpdateMerchant={updateMerchant}
                            isUpdatingMerchant={isUpdatingMerchant}
                        />
                    </>
                );
            case "logs":
                return <LogsView />;
            case "frontend":
                return <FrontendRoutingView />;
            default:
                return null;
        }
    };

    return (
        <main
            className={`pb-24 min-h-screen animate-in fade-in duration-500 transition-all duration-300 ${
                sidebarCollapsed ? "md:pl-[6.2rem]" : "md:pl-[17.8rem]"
            }`}
        >
            <div className="max-w-[1280px] mx-auto px-2 md:px-4">
                <DashboardHeader />
                {renderContent()}
            </div>

            {selectedSourceId && (
                <SpiderDetail
                    sourceId={selectedSourceId}
                    initialSource={selectedSourceInitial || undefined}
                    onClose={() => {
                        setSelectedSourceId(null);
                        setSelectedSourceInitial(null);
                    }}
                    onForceRun={(id, strategy) => forceRun({ id, strategy })}
                    onToggleActive={(id, active) => toggleSourceActive({ id, active })}
                    onUpdateSource={(id, updates) => updateSource({ id, updates })}
                    onOpenSource={(id) => openSourceDetail(id)}
                    isForceRunning={isForceRunning}
                    isUpdatingSource={isUpdatingSource}
                />
            )}

            <nav
                className={`fixed floating-nav z-50 transition-all duration-300 ${isSidebarDragging ? "md:transition-none" : ""}
                    left-2 right-2 bottom-3 h-16 flex-row items-center justify-around
                    md:left-4 md:right-auto md:bottom-4 md:top-4 md:h-auto md:flex-col md:justify-start md:gap-1 md:overflow-y-auto
                    ${sidebarCollapsed
                        ? "md:items-center md:px-1.5 md:py-2.5"
                        : "md:items-stretch md:px-3 md:py-3"
                    }`}
                style={{ ["--sidebar-width" as string]: `${sidebarWidth}px` } as React.CSSProperties}
            >
                {!sidebarCollapsed && (
                    <div className="hidden md:flex items-center justify-between px-2 pb-2 mb-1 border-b border-white/10">
                        <div>
                            <p className="text-[10px] uppercase tracking-[0.16em] text-[var(--tg-theme-subtitle-text-color)]">Navigation</p>
                            <p className="text-sm font-semibold">Admin Console</p>
                        </div>
                    </div>
                )}

                <div className="md:hidden flex items-center gap-1 w-full overflow-x-auto no-scrollbar">
                    {navSections.flatMap((section) => section.items).map((item) => (
                        <button
                            key={`mobile-${item.key}`}
                            onClick={() => setActiveTab(item.key)}
                            className={`nav-item shrink-0 ${activeTab === item.key ? "active" : ""}`}
                        >
                            {item.icon}
                        </button>
                    ))}
                </div>

                {navSections.map((section) => (
                    <div
                        key={section.title}
                        className={`hidden md:block w-full ${sidebarCollapsed ? "mb-1.5" : "mb-2.5"}`}
                    >
                        {!sidebarCollapsed && (
                            <p className="px-2 pb-1.5 text-[10px] uppercase tracking-[0.14em] text-[var(--tg-theme-subtitle-text-color)]">
                                {section.title}
                            </p>
                        )}
                        <div className={`${sidebarCollapsed ? "space-y-1" : "space-y-1 p-1.5 rounded-xl border border-white/8 bg-white/3"}`}>
                            {section.items.map((item) => (
                                <button
                                    key={item.key}
                                    onClick={() => setActiveTab(item.key)}
                                    className={`nav-item ${activeTab === item.key ? "active" : ""} ${!sidebarCollapsed ? "md:w-full md:h-auto md:min-h-[2.7rem] md:flex-row md:justify-start md:px-3" : ""}`}
                                >
                                    {item.icon}
                                    {!sidebarCollapsed && (
                                        <span className={`hidden md:inline text-[13px] ${item.strong ? "font-semibold" : "font-medium"}`}>
                                            {item.label}
                                        </span>
                                    )}
                                </button>
                            ))}
                        </div>
                    </div>
                ))}

                <div
                    className={`hidden md:flex absolute top-1/2 -translate-y-1/2 -right-2 w-3 h-12 items-center justify-center cursor-ew-resize select-none touch-none group ${isSidebarDragging ? "opacity-100" : sidebarCollapsed ? "opacity-40 hover:opacity-80" : "opacity-65 hover:opacity-100"}`}
                    role="separator"
                    aria-label="Resize sidebar"
                    onPointerDown={startSidebarResize}
                >
                    <div className={`h-7 w-[2px] rounded-full transition-all ${isSidebarDragging ? "bg-sky-300 shadow-[0_0_14px_rgba(56,189,248,0.65)]" : "bg-white/32 group-hover:bg-sky-200/80"}`} />
                </div>
            </nav>
        </main>
    );
}
