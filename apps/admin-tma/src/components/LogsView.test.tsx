import React from "react";
import { describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    fetchLogServices: vi.fn(async () => ({ items: ["api"] })),
    fetchLogsQuery: vi.fn(async () => ({
      items: [{ ts: "2026-03-04T00:00:00Z", ts_ns: 1, service: "api", line: "hello world" }],
    })),
  };
});

import { LogsView } from "@/components/LogsView";
import { renderWithProviders } from "@/test/renderWithProviders";
import { fetchLogsQuery } from "@/lib/api";

describe("LogsView", () => {
  it("loads history and renders log lines (SSE disabled)", async () => {
    process.env.NEXT_PUBLIC_DISABLE_SSE = "1";
    renderWithProviders(<LogsView />);

    await waitFor(() => {
      expect(fetchLogsQuery).toHaveBeenCalled();
    });

    expect(await screen.findByText(/hello world/i)).toBeInTheDocument();
  });
});

