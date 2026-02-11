"use client";

import { useState } from "react";
import { DashboardHeader } from "@/components/DashboardHeader";
import { StatsGrid } from "@/components/StatsGrid";
import { SpiderList } from "@/components/SpiderList";
import { UsageChart } from "@/components/UsageChart";
import { SettingsView } from "@/components/SettingsView";
import { useDashboardData } from "@/hooks/useDashboard";
import { useTMA } from "@/components/TMAProvider";
import { Zap, Bell, RefreshCcw, LayoutDashboard, Loader2, Settings } from "lucide-react";

const AVAILABLE_SPIDERS = [
  "detmir", "group_price", "inteltoys", "kassir",
  "letu", "mrgeek", "mvideo", "nashi_podarki", "vseigrushki"
];

export default function Home() {
  const [activeTab, setActiveTab] = useState("dashboard");
  const tma = useTMA();
  const chatId = tma?.user?.id;

  const {
    stats, health, scraping, sources, trends, subscriber,
    syncSpiders, isSyncing, isLoading,
    connectWeeek, isConnectingWeeek,
    toggleSubscription, setLanguage
  } = useDashboardData(chatId);

  const handleSync = () => {
    syncSpiders(AVAILABLE_SPIDERS);
  };

  const renderContent = () => {
    if (isLoading && activeTab !== 'settings') {
      return (
        <div className="flex flex-col items-center justify-center py-24 gap-4">
          <Loader2 className="animate-spin text-[var(--tg-theme-button-color)]" size={32} />
          <p className="text-sm text-[var(--tg-theme-hint-color)]">Loading system data...</p>
        </div>
      );
    }

    switch (activeTab) {
      case "dashboard":
        return (
          <>
            <div className="px-4 pt-4">
              <div className="bg-gradient-to-r from-[#2481cc] to-[#5288c1] rounded-2xl p-5 text-white shadow-xl relative overflow-hidden">
                <div className="relative z-10">
                  <h2 className="text-xl font-bold flex items-center gap-2">
                    <Zap size={20} fill="white" />
                    {health.data?.api_latency_ms < 500 ? "System: Optimal" : "System: High Load"}
                  </h2>
                  <p className="text-white/80 text-xs mt-1">
                    AI recommendation engine v1.2-qwen is active with {health.data?.api_latency_ms || 0}ms latency.
                  </p>
                </div>
                <div className="absolute top-0 right-0 w-32 h-32 bg-white/10 rounded-full -mr-16 -mt-16 blur-2xl"></div>
                <div className="absolute bottom-0 left-0 w-24 h-24 bg-white/10 rounded-full -ml-12 -mb-12 blur-xl"></div>
              </div>
            </div>
            <StatsGrid stats={stats.data} health={health.data} scraping={scraping.data} />
            <UsageChart data={trends.data} />
            <SpiderList
              sources={sources.data?.slice(0, 3)}
              onSync={handleSync}
              isSyncing={isSyncing}
            />
          </>
        );
      case "scrapers":
        return (
          <SpiderList
            sources={sources.data}
            onSync={handleSync}
            isSyncing={isSyncing}
          />
        );
      case "alerts":
        return (
          <div className="p-10 text-center space-y-4">
            <Bell size={48} className="mx-auto text-[var(--tg-theme-hint-color)] opacity-20" />
            <h3 className="font-bold">No active alerts</h3>
            <p className="text-sm text-[var(--tg-theme-hint-color)]">System is running within normal parameters.</p>
          </div>
        );
      case "settings":
        return (
          <SettingsView
            chatId={chatId}
            subscriber={subscriber.data}
            onConnectWeeek={(token) => connectWeeek({ token })}
            isConnectingWeeek={isConnectingWeeek}
            toggleSubscription={(topic, active) => toggleSubscription({ topic, active })}
            setLanguage={(lang) => setLanguage(lang)}
          />
        );
      default:
        return null;
    }
  };

  return (
    <main className="pb-24 min-h-screen animate-in fade-in duration-500">
      <DashboardHeader />

      {renderContent()}

      <nav className="fixed bottom-4 left-4 right-4 h-16 glass card flex items-center justify-around z-50">
        <button
          onClick={() => setActiveTab("dashboard")}
          className={`flex flex-col items-center gap-1 transition-colors ${activeTab === 'dashboard' ? 'text-[var(--tg-theme-button-color)]' : 'text-[var(--tg-theme-hint-color)]'}`}
        >
          <LayoutDashboard size={22} fill={activeTab === 'dashboard' ? 'currentColor' : 'none'} />
          <span className="text-[10px] font-bold">Main</span>
        </button>

        <button
          onClick={() => setActiveTab("scrapers")}
          className={`flex flex-col items-center gap-1 transition-colors ${activeTab === 'scrapers' ? 'text-[var(--tg-theme-button-color)]' : 'text-[var(--tg-theme-hint-color)]'}`}
        >
          <RefreshCcw size={22} className={activeTab === 'scrapers' ? 'animate-pulse' : ''} />
          <span className="text-[10px] font-medium">Scrapers</span>
        </button>

        <button
          onClick={() => setActiveTab("alerts")}
          className={`flex flex-col items-center gap-1 transition-colors ${activeTab === 'alerts' ? 'text-[var(--tg-theme-button-color)]' : 'text-[var(--tg-theme-hint-color)]'}`}
        >
          <Bell size={22} fill={activeTab === 'alerts' ? 'currentColor' : 'none'} />
          <span className="text-[10px] font-medium">Alerts</span>
        </button>

        <button
          onClick={() => setActiveTab("settings")}
          className={`flex flex-col items-center gap-1 transition-colors ${activeTab === 'settings' ? 'text-[var(--tg-theme-button-color)]' : 'text-[var(--tg-theme-hint-color)]'}`}
        >
          <Settings size={22} fill={activeTab === 'settings' ? 'currentColor' : 'none'} />
          <span className="text-[10px] font-medium">Settings</span>
        </button>
      </nav>
    </main>
  );
}
