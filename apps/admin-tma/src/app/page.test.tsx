import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/components/TMAProvider", () => ({
  useTMA: () => ({ authUser: { id: 1 } }),
}));

vi.mock("@/contexts/LanguageContext", () => ({
  useLanguage: () => ({
    language: "en",
    t: (key: string) => key,
  }),
}));

vi.mock("@/contexts/OpsRuntimeSettingsContext", () => ({
  useOpsRuntimeSettings: () => ({ getIntervalMs: () => 30000 }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    isSseDisabled: () => true,
    getOpsStreamUrl: () => "http://example/stream",
  };
});

vi.mock("@/hooks/useDashboard", () => ({
  useDashboardData: () => ({
    stats: { data: {}, error: null, refetch: vi.fn() },
    health: { data: {}, error: null, refetch: vi.fn() },
    scraping: { data: {}, error: null, refetch: vi.fn() },
    sources: { data: [], error: null, refetch: vi.fn() },
    trends: { data: {}, error: null, refetch: vi.fn() },
    workers: { data: {}, error: null, refetch: vi.fn() },
    queue: { data: {}, error: null, refetch: vi.fn() },
    subscriber: { data: null, error: null, refetch: vi.fn() },
    syncSpiders: vi.fn(),
    isSyncing: false,
    isLoading: false,
    forceRun: vi.fn(),
    isForceRunning: false,
    toggleSourceActive: vi.fn(),
    updateSource: vi.fn(),
    isUpdatingSource: false,
    connectWeeek: vi.fn(),
    isConnectingWeeek: false,
    toggleSubscription: vi.fn(),
    setLanguage: vi.fn(),
    sendTestNotification: vi.fn(),
    isSendingTest: false,
    runAll: vi.fn(),
    isRunningAll: false,
    runOne: vi.fn(),
    isRunningOne: false,
    merchants: { data: [], error: null, refetch: vi.fn() },
    updateMerchant: vi.fn(),
    isUpdatingMerchant: false,
  }),
  useCatalogProducts: () => ({
    data: { items: [], total: 0 },
    isLoading: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

vi.mock("@/components/DashboardHeader", () => ({
  DashboardHeader: () => <div data-testid="DashboardHeader" />,
}));
vi.mock("@/components/StatsGrid", () => ({
  StatsGrid: () => <div data-testid="StatsGrid" />,
}));
vi.mock("@/components/SpiderList", () => ({
  SpiderList: () => <div data-testid="SpiderList" />,
}));
vi.mock("@/components/SpiderDetail", () => ({
  SpiderDetail: () => <div data-testid="SpiderDetail" />,
}));
vi.mock("@/components/UsageChart", () => ({
  UsageChart: () => <div data-testid="UsageChart" />,
}));
vi.mock("@/components/SettingsView", () => ({
  SettingsView: () => <div data-testid="SettingsView" />,
}));
vi.mock("@/components/Intelligence", () => ({
  Intelligence: () => <div data-testid="Intelligence" />,
}));
vi.mock("@/components/InfraPanel", () => ({
  InfraPanel: () => <div data-testid="InfraPanel" />,
}));
vi.mock("@/components/HealthView", () => ({
  HealthView: () => <div data-testid="HealthView" />,
}));
vi.mock("@/components/CatalogView", () => ({
  CatalogView: () => <div data-testid="CatalogView" />,
}));
vi.mock("@/components/LogsView", () => ({
  LogsView: () => <div data-testid="LogsView" />,
}));
vi.mock("@/components/frontend/FrontendRoutingView", () => ({
  FrontendRoutingView: () => <div data-testid="FrontendRoutingView" />,
}));
vi.mock("@/components/operations/OperationsView", () => ({
  OperationsView: () => <div data-testid="OperationsView" />,
}));

import Home from "./page";

describe("Home page (tabs)", () => {
  it("renders and navigates across tabs", async () => {
    const user = userEvent.setup();
    render(<Home />);

    // Default tab is ops.
    expect(screen.getByTestId("OperationsView")).toBeInTheDocument();

    await user.click(screen.getByTestId("nav-dashboard"));
    expect(screen.getByTestId("StatsGrid")).toBeInTheDocument();

    await user.click(screen.getByTestId("nav-catalog"));
    expect(screen.getByTestId("CatalogView")).toBeInTheDocument();

    await user.click(screen.getByTestId("nav-health"));
    expect(screen.getByTestId("HealthView")).toBeInTheDocument();

    await user.click(screen.getByTestId("nav-logs"));
    expect(screen.getByTestId("LogsView")).toBeInTheDocument();

    await user.click(screen.getByTestId("nav-frontend"));
    expect(screen.getByTestId("FrontendRoutingView")).toBeInTheDocument();

    await user.click(screen.getByTestId("nav-settings"));
    expect(screen.getByTestId("SettingsView")).toBeInTheDocument();
  });
});
