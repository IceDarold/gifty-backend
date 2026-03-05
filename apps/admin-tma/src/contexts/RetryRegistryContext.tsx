"use client";

import React, { createContext, useCallback, useContext, useMemo, useRef } from "react";

type RetryFn = () => void | Promise<void>;

type RetryRegistryApi = {
  register: (key: string, fn: RetryFn) => () => void;
  run: (key: string) => Promise<boolean>;
  has: (key: string) => boolean;
};

const RetryRegistryContext = createContext<RetryRegistryApi | null>(null);

export function RetryRegistryProvider({ children }: { children: React.ReactNode }) {
  const fnsRef = useRef(new Map<string, RetryFn>());

  const register = useCallback((key: string, fn: RetryFn) => {
    fnsRef.current.set(key, fn);
    return () => {
      // Only delete if the same fn is still registered (avoid removing newer replacement).
      if (fnsRef.current.get(key) === fn) fnsRef.current.delete(key);
    };
  }, []);

  const has = useCallback((key: string) => fnsRef.current.has(key), []);

  const run = useCallback(async (key: string) => {
    const fn = fnsRef.current.get(key);
    if (!fn) return false;
    try {
      await fn();
    } catch {
      // Errors are surfaced via API error toasts; ignore here.
    }
    return true;
  }, []);

  const api = useMemo<RetryRegistryApi>(() => ({ register, run, has }), [register, run, has]);
  return <RetryRegistryContext.Provider value={api}>{children}</RetryRegistryContext.Provider>;
}

export function useRetryRegistry() {
  const ctx = useContext(RetryRegistryContext);
  if (!ctx) throw new Error("useRetryRegistry must be used within RetryRegistryProvider");
  return ctx;
}

