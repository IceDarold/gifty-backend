import React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/hooks/useAdminStreamQuery", () => ({
  useAdminChannelQuery: vi.fn(() => ({ data: { items: [] }, isLoading: false, error: null, refetch: vi.fn() })),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    publishFrontendConfig: vi.fn(async () => ({ status: "ok" })),
    rollbackFrontendConfig: vi.fn(async () => ({ status: "ok" })),
  };
});

import { useFrontendRoutingData } from "@/hooks/useFrontendRouting";
import { publishFrontendConfig } from "@/lib/api";

function Probe() {
  const data = useFrontendRoutingData();
  return (
    <button onClick={() => data.publish.mutateAsync({ active_profile_id: 1, fallback_release_id: 2 })}>
      Publish
    </button>
  );
}

describe("useFrontendRoutingData", () => {
  it("invalidates frontend queries after publish", async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    const spy = vi.spyOn(qc, "invalidateQueries");

    render(
      <QueryClientProvider client={qc}>
        <Probe />
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Publish" }));

    await waitFor(() => {
      expect(publishFrontendConfig).toHaveBeenCalledTimes(1);
    });

    await waitFor(() => {
      expect(spy).toHaveBeenCalled();
    });

    const keys = spy.mock.calls.map((c) => JSON.stringify((c[0] as any)?.queryKey || null));
    expect(keys.some((k) => k.includes("frontend-apps"))).toBe(true);
    expect(keys.some((k) => k.includes("frontend-runtime-state"))).toBe(true);
  });
});
