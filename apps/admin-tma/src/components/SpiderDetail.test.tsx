import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: any) => <div data-testid="chart">{children}</div>,
  LineChart: ({ children }: any) => <div>{children}</div>,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  CartesianGrid: () => null,
}));

vi.mock("@tanstack/react-query", () => ({
  useQuery: (options: any) => {
    const key = Array.isArray(options?.queryKey) ? options.queryKey[0] : options?.queryKey;
    if (key === "ops-discovery-category") {
      return {
        data: { item: { id: 123, status: "new", url: "https://example.com/cat" } },
        isLoading: false,
        error: null,
      };
    }
    if (key === "ops-source-items-trend") {
      return {
        data: { items: [{ ts: "2026-03-04T00:00:00Z", items_new: 3, items_total: 10 }] },
        isLoading: false,
        error: null,
      };
    }
    return { data: null, isLoading: false, error: null };
  },
}));

vi.mock("@/hooks/useDashboard", () => ({
  useSourceDetails: () => ({
    data: {
      id: 1,
      site_key: "site-1",
      name: "Test Source",
      status: "completed",
      is_active: true,
      url: "https://example.com",
      config: { site_name: "Test Source" },
      history: [
        { id: 1, status: "completed", started_at: "2026-03-04T00:00:00Z", finished_at: "2026-03-04T00:01:00Z", items_new: 2 },
      ],
      aggregate_history: [],
      related_sources: [
        { id: 101, site_key: "cat-1", url: "https://example.com/cat-1", config: { discovery_name: "Category 1" } },
        { id: 102, site_key: "cat-2", url: "https://example.com/cat-2", config: { discovery_name: "Category 2" } },
      ],
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
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

import { SpiderDetail } from "./SpiderDetail";

describe("SpiderDetail (smoke)", () => {
  it("renders overview and categories tabs", async () => {
    const user = userEvent.setup();

    render(
      <SpiderDetail
        sourceId={1}
        onClose={() => undefined}
        onForceRun={() => undefined}
        isForceRunning={false}
      />,
    );

    expect(screen.getByText("Test Source")).toBeInTheDocument();

    // Switch to categories tab.
    await user.click(screen.getByRole("button", { name: "Категории" }));

    expect(screen.getByText(/Category 1/i)).toBeInTheDocument();
  });
});
