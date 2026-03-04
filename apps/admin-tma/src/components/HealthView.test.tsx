import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { HealthView } from "@/components/HealthView";
import { renderWithProviders } from "@/test/renderWithProviders";

describe("HealthView", () => {
  it("renders status chips from provided props", () => {
    renderWithProviders(
      <HealthView
        health={{
          api: { status: "Healthy", latency: "12ms" },
          database: { status: "Connected", engine: "PostgreSQL" },
          redis: { status: "Healthy", memory_usage: "10MB" },
        }}
        workers={[{ hostname: "w1" }]}
        queue={{ messages_total: 42 }}
      />,
    );

    expect(screen.getByText(/System Health/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Healthy/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Connected/i)).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });
});
