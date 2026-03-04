import React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { SettingsView } from "@/components/SettingsView";
import { renderWithProviders } from "@/test/renderWithProviders";

describe("SettingsView", () => {
  it("calls restore defaults when button clicked", () => {
    const restore = vi.fn(async () => ({}));

    renderWithProviders(
      <SettingsView
        chatId={1}
        subscriber={{ subscriptions: [] }}
        onConnectWeeek={async () => ({})}
        isConnectingWeeek={false}
        toggleSubscription={() => {}}
        setBackendLanguage={() => {}}
        onSendTestNotification={() => {}}
        isSendingTest={false}
        runtimeSettings={{
          item: {
            settings_version: 1,
            ops_client_intervals: { "dashboard.stats_ms": 60000 },
            bounds: { ops_client_intervals: { min: 1000, max: 600000 } },
          },
        }}
        runtimeSettingsLoading={false}
        runtimeSettingsError={null}
        onUpdateRuntimeSettings={async () => ({})}
        onRestoreRuntimeSettingsDefaults={restore}
        isUpdatingRuntimeSettings={false}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Restore defaults/i }));
    expect(restore).toHaveBeenCalledTimes(1);
  });
});

