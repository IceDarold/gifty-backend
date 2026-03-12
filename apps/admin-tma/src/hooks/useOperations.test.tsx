import React from "react";
import { describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";

vi.mock("@/hooks/useAdminStreamQuery", () => ({
  useAdminChannelQuery: vi.fn((channel: string) => {
    if (channel === "ops.overview") {
      return { data: { status: "ok", queue: { messages_total: 1 } }, isLoading: false, error: null, refetch: vi.fn() };
    }
    if (channel === "ops.sites") {
      return { data: { items: [{ site_key: "detmir" }] }, isLoading: false, error: null, refetch: vi.fn() };
    }
    return { data: null, isLoading: false, error: null, refetch: vi.fn() };
  }),
}));

import { useOperationsData } from "@/hooks/useOperations";
import { renderWithProviders } from "@/test/renderWithProviders";

function Probe() {
  const { overview, sites } = useOperationsData();
  return (
    <div>
      <div>overview:{overview.data?.queue?.messages_total ?? "-"}</div>
      <div>sites:{sites.data?.items?.length ?? 0}</div>
    </div>
  );
}

describe("useOperationsData", () => {
  it("fetches data with polling but does not require SSE", async () => {
    renderWithProviders(<Probe />);
    expect(await screen.findByText(/overview:1/)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/sites:1/)).toBeInTheDocument();
    });
  });
});
