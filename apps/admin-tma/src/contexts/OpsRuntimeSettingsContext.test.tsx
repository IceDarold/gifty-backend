import React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";

vi.mock("@/hooks/useAdminStreamQuery", () => ({
  useAdminChannelQuery: vi.fn(() => ({ data: null, isLoading: false, error: null, refetch: vi.fn() })),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    updateOpsRuntimeSettings: vi.fn(),
  };
});

import { useOpsRuntimeSettings } from "@/contexts/OpsRuntimeSettingsContext";
import { renderWithProviders } from "@/test/renderWithProviders";
import { updateOpsRuntimeSettings } from "@/lib/api";

function Probe() {
  const { getIntervalMs, restoreDefaults, isUpdating } = useOpsRuntimeSettings();
  return (
    <div>
      <div data-testid="interval">{getIntervalMs("dashboard.stats_ms", 60000)}</div>
      <button onClick={() => void restoreDefaults()} disabled={isUpdating}>
        Restore
      </button>
    </div>
  );
}

describe("OpsRuntimeSettingsProvider", () => {
  it("uses server interval when provided and clamps values", async () => {
    const { useAdminChannelQuery } = await import("@/hooks/useAdminStreamQuery");
    (useAdminChannelQuery as any).mockReturnValueOnce({
      data: { item: { ops_client_intervals: { "dashboard.stats_ms": 500 } } },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    renderWithProviders(<Probe />);

    await waitFor(() => {
      expect(screen.getByTestId("interval")).toHaveTextContent("1000");
    });
  });

  it("restoreDefaults calls updateOpsRuntimeSettings with defaults", async () => {
    const { useAdminChannelQuery } = await import("@/hooks/useAdminStreamQuery");
    (useAdminChannelQuery as any).mockReturnValueOnce({
      data: { item: { ops_client_intervals: {} } },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    (updateOpsRuntimeSettings as any).mockResolvedValueOnce({ status: "ok" });

    renderWithProviders(<Probe />);

    fireEvent.click(await screen.findByRole("button", { name: "Restore" }));

    await waitFor(() => {
      expect(updateOpsRuntimeSettings).toHaveBeenCalledTimes(1);
    });

    const payload = (updateOpsRuntimeSettings as any).mock.calls[0][0];
    expect(payload).toMatchObject({
      ops_aggregator_enabled: true,
      ops_aggregator_interval_ms: 2000,
      ops_snapshot_ttl_ms: 10000,
      ops_stale_max_age_ms: 60000,
    });
    expect(payload.ops_client_intervals).toBeTruthy();
  });
});
