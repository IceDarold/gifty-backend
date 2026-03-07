import { describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { CatalogView } from "@/components/CatalogView";
import { renderWithProviders } from "@/test/renderWithProviders";

describe("CatalogView", () => {
  it("renders items and triggers pagination + apply new items", () => {
    const onSearchChange = vi.fn();
    const onPageChange = vi.fn();
    const onRefresh = vi.fn();
    const onApplyNewItems = vi.fn();

    renderWithProviders(
      <CatalogView
        data={{
          total: 45,
          items: [{ product_id: 1, title: "Item 1", price: 100, currency: "RUB", merchant: "m" }],
        }}
        isLoading={false}
        pendingNewItems={3}
        search=""
        page={0}
        onSearchChange={onSearchChange}
        onPageChange={onPageChange}
        onRefresh={onRefresh}
        onApplyNewItems={onApplyNewItems}
      />,
    );

    expect(screen.getByText(/Global Catalog/i)).toBeInTheDocument();
    expect(screen.getByText("Item 1")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /3 new items/i }));
    expect(onApplyNewItems).toHaveBeenCalledTimes(1);

    fireEvent.change(screen.getByPlaceholderText(/Search by title/i), { target: { value: "lego" } });
    expect(onSearchChange).toHaveBeenCalledWith("lego");

    fireEvent.click(screen.getByRole("button", { name: /Next/i }));
    expect(onPageChange).toHaveBeenCalledWith(1);
  });
});

