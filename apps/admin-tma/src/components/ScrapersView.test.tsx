import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/contexts/LanguageContext", () => ({
  useLanguage: () => ({
    language: "en",
    t: (key: string) => key,
  }),
}));

import { ScrapersView } from "./ScrapersView";

describe("ScrapersView", () => {
  it("renders empty state and calls sync", async () => {
    const user = userEvent.setup();
    const onSync = vi.fn();

    render(
      <ScrapersView
        sources={[]}
        discoveredCategories={[]}
        onOpenDetail={() => undefined}
        onRunOne={() => undefined}
        onDeleteData={() => undefined}
        onRunAll={() => undefined}
        onActivateDiscoveredCategories={async () => undefined}
        onSync={onSync}
        isSyncing={false}
        isRunningAll={false}
        isRunningOne={false}
        isActivatingDiscoveredCategories={false}
        isDeleting={false}
      />,
    );

    expect(screen.getByText("spiders.no_spiders")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "spiders.sync_now" }));
    expect(onSync).toHaveBeenCalledTimes(1);
  });
});

