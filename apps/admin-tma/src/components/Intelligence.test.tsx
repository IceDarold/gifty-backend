import React from "react";
import { describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, fetchIntelligence: vi.fn() };
});

import { Intelligence } from "@/components/Intelligence";
import { renderWithProviders } from "@/test/renderWithProviders";
import { fetchIntelligence } from "@/lib/api";

describe("Intelligence", () => {
  it("shows error banner when API fails", async () => {
    (fetchIntelligence as any).mockRejectedValueOnce({
      isAxiosError: true,
      message: "Request failed",
      response: { status: 502, data: { detail: "Bad gateway" } },
    });

    renderWithProviders(<Intelligence />);

    await waitFor(() => {
      expect(screen.getByText(/AI Intelligence API временно недоступен/i)).toBeInTheDocument();
    });
  });

  it("renders metrics when API succeeds", async () => {
    (fetchIntelligence as any).mockResolvedValueOnce({
      metrics: { total_requests: 10, total_cost: 1.23, total_tokens: 1000, avg_latency: 500 },
      providers: [{ provider: "claude", count: 10 }],
      latency_heatmap: [{ hour: 1, avg_latency: 900 }],
    });

    renderWithProviders(<Intelligence />);

    expect(await screen.findByText(/\$1\.23/)).toBeInTheDocument();
    expect(screen.getByText(/Provider Distribution/i)).toBeInTheDocument();
  });
});
