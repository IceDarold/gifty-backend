import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

process.env.NEXT_PUBLIC_TEST_MODE = process.env.NEXT_PUBLIC_TEST_MODE || "1";
process.env.NEXT_PUBLIC_DISABLE_SSE = process.env.NEXT_PUBLIC_DISABLE_SSE || "1";
process.env.NEXT_PUBLIC_TEST_USER_JSON =
  process.env.NEXT_PUBLIC_TEST_USER_JSON || JSON.stringify({ id: 1, role: "superadmin", permissions: ["*"] });

if (!("matchMedia" in window)) {
  (window as any).matchMedia = () => ({
    matches: false,
    media: "",
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  });
}

class NoopResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (!("ResizeObserver" in window)) {
  (window as any).ResizeObserver = NoopResizeObserver;
}

if (!("scrollTo" in window)) {
  (window as any).scrollTo = () => {};
}

if (!("EventSource" in window)) {
  class DummyEventSource {
    onopen: ((this: EventSource, ev: Event) => any) | null = null;
    onerror: ((this: EventSource, ev: Event) => any) | null = null;
    url: string;
    withCredentials: boolean = false;
    readyState: number = 0;
    constructor(url: string) {
      this.url = url;
    }
    close() {}
    addEventListener() {}
    removeEventListener() {}
    dispatchEvent() {
      return false;
    }
  }
  (window as any).EventSource = DummyEventSource;
}

Object.defineProperty(globalThis.navigator, "clipboard", {
  value: {
    writeText: async () => {},
  },
  configurable: true,
});

afterEach(() => {
  cleanup();
});
