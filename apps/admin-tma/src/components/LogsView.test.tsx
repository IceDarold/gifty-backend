import React from "react";
import { describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";

vi.mock("@/hooks/useAdminStreamQuery", () => ({
  useAdminChannelQuery: vi.fn((channel: string) => {
    if (channel === "logs.snapshot") {
      return {
        data: { items: [{ ts: "2026-03-04T00:00:00Z", ts_ns: 1, service: "api", line: "hello world" }] },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      };
    }
    if (channel === "logs.tail") {
      return {
        data: { items: [{ ts: "2026-03-04T00:00:01Z", ts_ns: 2, service: "api", line: "tail line" }] },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      };
    }
    if (channel === "logs.services") {
      return { data: { items: ["api"] }, isLoading: false, error: null, refetch: vi.fn() };
    }
    return { data: null, isLoading: false, error: null, refetch: vi.fn() };
  }),
}));

import { LogsView } from "@/components/LogsView";
import { renderWithProviders } from "@/test/renderWithProviders";
describe("LogsView", () => {
  it("loads history and renders log lines (SSE disabled)", async () => {
    process.env.NEXT_PUBLIC_DISABLE_SSE = "1";
    renderWithProviders(<LogsView />);
    await waitFor(() => {
      expect(screen.getByText(/hello world/i)).toBeInTheDocument();
    });
  });
});
