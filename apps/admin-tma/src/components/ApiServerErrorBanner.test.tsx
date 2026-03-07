import { describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { ApiServerErrorBanner } from "@/components/ApiServerErrorBanner";
import { renderWithProviders } from "@/test/renderWithProviders";

describe("ApiServerErrorBanner", () => {
  it("renders only for server api errors and calls retry", async () => {
    const onRetry = vi.fn();
    const axiosLikeError = {
      isAxiosError: true,
      message: "Request failed",
      response: { status: 502, data: { detail: "Bad gateway" } },
    } as any;

    renderWithProviders(<ApiServerErrorBanner errors={[null, axiosLikeError]} onRetry={onRetry} />);

    expect(screen.getByText(/Ошибка сервера/i)).toBeInTheDocument();
    expect(screen.getByText(/502/)).toBeInTheDocument();
    expect(screen.getByText(/Bad gateway/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Попробовать снова/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("does not render for non-server errors", () => {
    renderWithProviders(<ApiServerErrorBanner errors={[new Error("x")]} onRetry={() => {}} />);
    expect(screen.queryByText(/Ошибка сервера/i)).not.toBeInTheDocument();
  });
});

