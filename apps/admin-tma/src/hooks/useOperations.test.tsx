import React from "react";
import { describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    fetchOpsOverview: vi.fn(async () => ({ status: "ok", queue: { messages_total: 1 } })),
    fetchOpsSites: vi.fn(async () => ({ items: [{ site_key: "detmir" }] })),
    fetchOpsPipeline: vi.fn(async () => ({ status: "ok", items: [] })),
    fetchOpsActiveRuns: vi.fn(async () => ({ items: [] })),
    fetchOpsRunDetails: vi.fn(async () => ({ item: {} })),
    fetchOpsDiscoveryCategories: vi.fn(async () => ({ items: [] })),
    getOpsStreamUrl: vi.fn(() => "http://test/ops/stream"),
    isSseDisabled: () => true,
  };
});

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

