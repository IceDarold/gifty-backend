import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/hooks/useDashboard", () => ({
  useQueueRunDetails: () => ({
    data: {
      item: {
        id: 123,
        site_key: "site-1",
        status: "error",
        duration_seconds: 1.2,
        logs: "2026-03-04T00:00:00Z ERROR something failed\n2026-03-04T00:00:01Z info queued task",
      },
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

import { QueueView } from "./QueueView";

describe("QueueView (smoke)", () => {
  it("renders history and opens run details modal", async () => {
    const user = userEvent.setup();

    render(
      <QueueView
        queue={{ rate_publish: 0.5, messages_unacknowledged: 1, messages_total: 2, consumers: 1 }}
        tasksData={{ status: "ok", items: [{ id: "m1" }] }}
        historyData={{
          items: [
            {
              id: 123,
              site_key: "site-1",
              status: "error",
              created_at: "2026-03-04T00:00:00Z",
              items_scraped: 1,
              items_new: 1,
              duration_seconds: 1.2,
              error_message: "boom",
            },
          ],
        }}
      />,
    );

    expect(screen.getByText("Recent History")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /site-1/i }));

    expect(await screen.findByText("Run Details")).toBeInTheDocument();
    expect(screen.getByText(/run #123/i)).toBeInTheDocument();
  });
});

