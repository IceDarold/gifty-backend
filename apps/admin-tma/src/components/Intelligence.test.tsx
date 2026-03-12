import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";

vi.mock("@/hooks/useAdminStreamQuery", () => ({
  useAdminChannelQuery: vi.fn(() => ({ data: null, isLoading: false, error: null, refetch: vi.fn() })),
}));

import { Intelligence } from "@/components/Intelligence";
import { renderWithProviders } from "@/test/renderWithProviders";
describe("Intelligence", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows error banner when API fails", async () => {
    const { useAdminChannelQuery } = await import("@/hooks/useAdminStreamQuery");
    (useAdminChannelQuery as any).mockImplementation(() => ({
      data: null,
      isLoading: false,
      error: new Error("Bad gateway"),
      refetch: vi.fn(),
    }));

    renderWithProviders(<Intelligence />);

    await waitFor(() => {
      expect(screen.getByText(/AI Intelligence( API)? временно недоступен/i)).toBeInTheDocument();
    });
  });

  it("renders metrics when API succeeds", async () => {
    const { useAdminChannelQuery } = await import("@/hooks/useAdminStreamQuery");
    (useAdminChannelQuery as any).mockImplementation(() => ({
      data: {
        metrics: { total_requests: 10, total_cost: 1.23, total_tokens: 1000, avg_latency: 500 },
        providers: [{ provider: "claude", count: 10 }],
        latency_heatmap: [{ hour: 1, avg_latency: 900 }],
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    }));

    renderWithProviders(<Intelligence />);

    expect(await screen.findByText(/\$1\.23/)).toBeInTheDocument();
    expect(screen.getByText(/Provider Distribution/i)).toBeInTheDocument();
  });
});
