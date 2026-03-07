import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

describe("TMAProvider", () => {
  it("in test mode provides authUser immediately", async () => {
    process.env.NEXT_PUBLIC_TEST_MODE = "1";
    process.env.NEXT_PUBLIC_TEST_USER_JSON = JSON.stringify({ id: 123, role: "superadmin", permissions: ["*"] });
    vi.resetModules();

    const { TMAProvider, useTMA } = await import("@/components/TMAProvider");

    function Child() {
      const ctx = useTMA();
      return <div>user:{ctx?.authUser?.id}</div>;
    }

    render(
      <TMAProvider>
        <Child />
      </TMAProvider>,
    );

    expect(await screen.findByText("user:123")).toBeInTheDocument();
  });

  it("in non-test mode shows unauthorized UI when auth fails", async () => {
    process.env.NEXT_PUBLIC_TEST_MODE = "0";
    vi.resetModules();

    vi.doMock("@telegram-apps/sdk", () => ({
      initData: { user: () => null, startParam: () => null },
      miniApp: { mount: { isAvailable: () => false }, ready: { isAvailable: () => false } },
      viewport: { mount: { isAvailable: () => false }, expand: { isAvailable: () => false } },
      themeParams: { mount: { isAvailable: () => false } },
    }));

    vi.doMock("@/lib/api", async (importOriginal) => {
      const actual = await importOriginal<typeof import("@/lib/api")>();
      return {
        ...actual,
        authWithTelegram: vi.fn(async () => Promise.reject(new Error("fail"))),
        // Avoid long polling loop in provider.
        getInitDataRaw: () => "dev_user_1821014162",
      };
    });

    const { TMAProvider } = await import("@/components/TMAProvider");

    render(
      <TMAProvider>
        <div>child</div>
      </TMAProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText(/Доступ запрещен/i)).toBeInTheDocument();
    }, { timeout: 5000 });
  });
});
