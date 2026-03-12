import React from "react";
import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/renderWithProviders";

const mockUseQuery = vi.fn((options: any) => {
  const key = Array.isArray(options?.queryKey) ? options.queryKey[0] : options?.queryKey;
  if (key === "ops-scheduler-stats") {
    return {
      data: {
        summary: {
          scheduler_paused: false,
          active_sources: 3,
          due_now: 1,
          overdue_15m: 0,
          scheduled_next_hour: 2,
          paused_sources: 0,
        },
        intervals: [],
        runs_24h: { completed: { count: 5, items_new: 12 }, error: { count: 1, items_new: 0 } },
        queue_plan_trend: [],
        upcoming: [],
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    };
  }
  if (key === "queue-history-for-ops-error") {
    return { data: { items: [], total: 0 }, isLoading: false, isFetching: false, error: null, refetch: vi.fn() };
  }
  if (key === "ops-items-trend") {
    return {
      data: { points: [{ ts: "2026-03-04T00:00:00Z", items_new: 3 }], totals: { items_new: 3 } },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    };
  }
  if (key === "ops-tasks-trend") {
    return {
      data: { points: [{ ts: "2026-03-04T00:00:00Z", tasks: 2 }], totals: { tasks: 2 } },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    };
  }
  return { data: null, isLoading: false, isFetching: false, error: null, refetch: vi.fn() };
});

const mockUseInfiniteQuery = vi.fn(() => ({
  data: { pages: [{ items: [], total: 0 }] },
  isLoading: false,
  isFetching: false,
  isFetchingNextPage: false,
  hasNextPage: false,
  fetchNextPage: vi.fn(),
  refetch: vi.fn(),
  error: null,
}));

vi.mock("@tanstack/react-query", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-query")>();
  return {
    ...actual,
    useQuery: (opts: any) => mockUseQuery(opts),
    useInfiniteQuery: (opts: any) => mockUseInfiniteQuery(opts),
  };
});

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: any) => <div data-testid="chart">{children}</div>,
  LineChart: ({ children }: any) => <div>{children}</div>,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  CartesianGrid: () => null,
}));

vi.mock("@/contexts/OpsRuntimeSettingsContext", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/contexts/OpsRuntimeSettingsContext")>();
  return {
    ...actual,
    useOpsRuntimeSettings: () => ({ getIntervalMs: () => 30000 }),
  };
});

vi.mock("@/lib/grafana", () => ({
  openGrafanaExploreLoki: vi.fn(),
  openGrafanaExplorePrometheus: vi.fn(),
}));

vi.mock("@/hooks/useOperations", () => ({
  useOperationsData: () => ({
    selectedSiteKey: "site-1",
    setSelectedSiteKey: vi.fn(),
    selectedRunId: null,
    setSelectedRunId: vi.fn(),
    streamState: "connected",
    streamError: null,
    discoveryStateFilter: "new",
    setDiscoveryStateFilter: vi.fn(),
    discoverySearch: "",
    setDiscoverySearch: vi.fn(),
    overview: {
      data: {
        runs: { running: 1, completed: 2, error: 0 },
        queue: { messages_total: 3, messages_ready: 1, messages_unacknowledged: 0 },
        workers: { online: 1, items: [] },
        discovery_categories: { new: 1, promoted: 0 },
        discovery_products: { total: 100 },
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    },
    sites: {
      data: { items: [{ site_key: "site-1", name: "Site 1" }] },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    },
    pipeline: { data: null, isLoading: false, error: null, refetch: vi.fn() },
    activeRuns: {
      data: { items: [] },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    },
    discovery: { data: { items: [] }, isLoading: false, error: null, refetch: vi.fn() },
    queuedRuns: { data: { items: [] }, isLoading: false, error: null, refetch: vi.fn() },
    completedRuns: { data: { items: [] }, isLoading: false, error: null, refetch: vi.fn() },
    errorRuns: { data: { items: [] }, isLoading: false, error: null, refetch: vi.fn() },
    schedulerStats: { data: {}, isLoading: false, error: null, refetch: vi.fn() },
    itemsTrendMap: { data: {}, isLoading: false, error: null, refetch: vi.fn() },
    tasksTrendMap: { data: {}, isLoading: false, error: null, refetch: vi.fn() },
    sources: { data: { items: [] }, isLoading: false, error: null, refetch: vi.fn() },
    runDetails: {
      data: null,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    },
    promoteCategories: vi.fn(async () => undefined),
    rejectCategories: vi.fn(async () => undefined),
    reactivateCategories: vi.fn(async () => undefined),
    bulkUpdateSources: vi.fn(async () => undefined),
    retryRun: vi.fn(async () => undefined),
    runSourceNow: vi.fn(async () => undefined),
    runSiteDiscovery: vi.fn(async () => undefined),
    anyPendingAction: false,
  }),
}));

vi.mock("@/hooks/useAdminStreamQuery", () => ({
  useAdminChannelQuery: vi.fn(() => ({ data: null, isLoading: false, error: null, refetch: vi.fn() })),
  useAdminRequestQuery: vi.fn(() => ({ data: { items: [], total: 0 }, isLoading: false, error: null, refetch: vi.fn() })),
}));

import { OperationsView } from "./OperationsView";

describe("OperationsView (smoke)", () => {
  it("renders and switches tabs without real react-query/recharts", async () => {
    const user = userEvent.setup();
    renderWithProviders(<OperationsView onOpenSourceDetails={() => undefined} />);

    expect(screen.getByText("Operations Center")).toBeInTheDocument();
    expect(screen.getByText("Live connected")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Workers" }));
    await user.click(screen.getByRole("button", { name: "Scheduler" }));

    expect(screen.getByText("Operations Center")).toBeInTheDocument();
  });
});
