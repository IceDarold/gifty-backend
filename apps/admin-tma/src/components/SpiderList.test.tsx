import { describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { SpiderList } from "@/components/SpiderList";
import { renderWithProviders } from "@/test/renderWithProviders";

describe("SpiderList", () => {
  it("calls onRunOne when run button clicked", () => {
    const onRunOne = vi.fn();
    const onOpenDetail = vi.fn();

    renderWithProviders(
      <SpiderList
        sources={[{ id: 10, site_key: "detmir", status: "idle", total_items: 12 }]}
        onRunOne={onRunOne}
        onOpenDetail={onOpenDetail}
      />,
    );

    fireEvent.click(screen.getByTitle("Run detmir"));
    expect(onRunOne).toHaveBeenCalledWith(10);
  });
});

