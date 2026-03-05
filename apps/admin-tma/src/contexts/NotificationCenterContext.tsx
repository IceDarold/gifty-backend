"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useReducer } from "react";

export type NotificationLevel = "running" | "success" | "info" | "warn" | "error";

export type NotificationEvent = {
  id: string;
  level: NotificationLevel;
  title: string;
  message: string;
  ts: number; // first seen
  lastTs: number; // last update
  count: number; // number of updates / repeats
  readAt: number | null;
  source?: string;
  meta?: Record<string, unknown>;
  dedupeKey?: string;
};

type NotificationCenterState = {
  events: NotificationEvent[];
  toasts: {
    id: string;
    expiresAt: number | null;
  }[];
};

type UpsertInput = Omit<NotificationEvent, "ts" | "lastTs" | "count" | "readAt"> & {
  dedupeKey?: string;
};

type NotificationCenterAction =
  | { type: "load"; events: NotificationEvent[] }
  | { type: "upsert"; now: number; event: UpsertInput }
  | { type: "toast"; now: number; event: UpsertInput; ttlMs?: number }
  | { type: "dismissToast"; id: string }
  | { type: "pruneToasts"; now: number }
  | { type: "markRead"; id: string; now: number }
  | { type: "markAllRead"; now: number }
  | { type: "clear" }
  | { type: "prune"; now: number };

const STORAGE_KEY = "admin_tma_notifications_v1";
const MAX_ITEMS = 500;
const TTL_MS = 1000 * 60 * 60 * 48; // 48h
const DEDUPE_WINDOW_MS = 10_000;

const isPlainObject = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);

const normalizeLoadedEvents = (raw: unknown, now: number): NotificationEvent[] => {
  if (!Array.isArray(raw)) return [];
  const out: NotificationEvent[] = [];
  for (const item of raw) {
    if (!isPlainObject(item)) continue;
    const id = typeof item.id === "string" ? item.id : "";
    const level = typeof item.level === "string" ? (item.level as NotificationLevel) : "info";
    const title = typeof item.title === "string" ? item.title : "";
    const message = typeof item.message === "string" ? item.message : "";
    const ts = typeof item.ts === "number" ? item.ts : now;
    const lastTs = typeof item.lastTs === "number" ? item.lastTs : ts;
    const count = typeof item.count === "number" ? item.count : 1;
    const readAt = typeof item.readAt === "number" ? item.readAt : null;
    const source = typeof item.source === "string" ? item.source : undefined;
    const meta = isPlainObject(item.meta) ? (item.meta as Record<string, unknown>) : undefined;
    const dedupeKey = typeof item.dedupeKey === "string" ? item.dedupeKey : undefined;
    if (!id || !title) continue;
    out.push({ id, level, title, message, ts, lastTs, count, readAt, source, meta, dedupeKey });
  }
  return out;
};

const pruneEvents = (events: NotificationEvent[], now: number) => {
  const keep = events.filter((e) => now - e.lastTs <= TTL_MS);
  keep.sort((a, b) => b.lastTs - a.lastTs);
  return keep.slice(0, MAX_ITEMS);
};

const upsertEvent = (events: NotificationEvent[], now: number, next: UpsertInput): NotificationEvent[] => {
  const signatureKey = next.dedupeKey || `${next.level}:${next.title}:${next.message}`;
  const idxById = events.findIndex((e) => e.id === next.id);

  // Prefer stable id-based updates (matches existing toast behavior).
  if (idxById >= 0) {
    const prev = events[idxById]!;
    const updated: NotificationEvent = {
      ...prev,
      level: next.level,
      title: next.title,
      message: next.message,
      source: next.source,
      meta: next.meta,
      dedupeKey: next.dedupeKey,
      lastTs: now,
      count: prev.count + 1,
      readAt: null,
    };
    const copy = [...events];
    copy[idxById] = updated;
    return copy;
  }

  // Otherwise, dedupe within window by dedupeKey/signature to avoid spam.
  const idxBySignature = events.findIndex(
    (e) => (e.dedupeKey || `${e.level}:${e.title}:${e.message}`) === signatureKey && now - e.lastTs <= DEDUPE_WINDOW_MS,
  );
  if (idxBySignature >= 0) {
    const prev = events[idxBySignature]!;
    const updated: NotificationEvent = {
      ...prev,
      level: next.level,
      title: next.title,
      message: next.message,
      source: next.source,
      meta: next.meta,
      dedupeKey: next.dedupeKey,
      lastTs: now,
      count: prev.count + 1,
      readAt: null,
    };
    const copy = [...events];
    copy[idxBySignature] = updated;
    return copy;
  }

  return [
    ...events,
    {
      id: next.id,
      level: next.level,
      title: next.title,
      message: next.message,
      ts: now,
      lastTs: now,
      count: 1,
      readAt: null,
      source: next.source,
      meta: next.meta,
      dedupeKey: next.dedupeKey,
    },
  ];
};

const reducer = (state: NotificationCenterState, action: NotificationCenterAction): NotificationCenterState => {
  switch (action.type) {
    case "load":
      return { ...state, events: action.events };
    case "upsert": {
      const events = pruneEvents(upsertEvent(state.events, action.now, action.event), action.now);
      return { ...state, events };
    }
    case "toast": {
      const events = pruneEvents(upsertEvent(state.events, action.now, action.event), action.now);
      const toastTtlMs = typeof action.ttlMs === "number" ? action.ttlMs : action.event.level === "running" ? 0 : 6000;
      const expiresAt = action.event.level === "running" ? null : action.now + Math.max(500, toastTtlMs || 6000);
      const existingIdx = state.toasts.findIndex((t) => t.id === action.event.id);
      const nextToasts = [...state.toasts];
      if (existingIdx >= 0) {
        nextToasts[existingIdx] = { id: action.event.id, expiresAt };
      } else {
        nextToasts.push({ id: action.event.id, expiresAt });
      }
      return { events, toasts: nextToasts };
    }
    case "dismissToast":
      return { ...state, toasts: state.toasts.filter((t) => t.id !== action.id) };
    case "pruneToasts": {
      const toasts = state.toasts.filter((t) => t.expiresAt === null || t.expiresAt > action.now);
      return toasts.length === state.toasts.length ? state : { ...state, toasts };
    }
    case "markRead": {
      const events = state.events.map((e) => (e.id === action.id ? { ...e, readAt: e.readAt ?? action.now } : e));
      return { ...state, events };
    }
    case "markAllRead": {
      const events = state.events.map((e) => ({ ...e, readAt: e.readAt ?? action.now }));
      return { ...state, events };
    }
    case "clear":
      return { events: [], toasts: [] };
    case "prune":
      return { ...state, events: pruneEvents(state.events, action.now) };
    default:
      return state;
  }
};

type NotificationCenterApi = {
  events: NotificationEvent[];
  toasts: NotificationEvent[];
  unreadCount: number;
  upsert: (event: UpsertInput) => void;
  toast: (event: UpsertInput, opts?: { ttlMs?: number }) => void;
  dismissToast: (id: string) => void;
  markRead: (id: string) => void;
  markAllRead: () => void;
  clear: () => void;
};

const NotificationCenterContext = createContext<NotificationCenterApi | null>(null);

export function NotificationCenterProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, { events: [], toasts: [] });

  useEffect(() => {
    const now = Date.now();
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      const parsed = raw ? JSON.parse(raw) : null;
      const events = pruneEvents(normalizeLoadedEvents(parsed, now), now);
      dispatch({ type: "load", events });
    } catch {
      dispatch({ type: "load", events: [] });
    }
    dispatch({ type: "prune", now });
  }, []);

  useEffect(() => {
    const t = window.setInterval(() => dispatch({ type: "pruneToasts", now: Date.now() }), 500);
    return () => window.clearInterval(t);
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state.events));
    } catch {
      // ignore storage quota / privacy modes
    }
  }, [state.events]);

  const upsert = useCallback((event: UpsertInput) => dispatch({ type: "upsert", now: Date.now(), event }), []);
  const toast = useCallback((event: UpsertInput, opts?: { ttlMs?: number }) => dispatch({ type: "toast", now: Date.now(), event, ttlMs: opts?.ttlMs }), []);
  const dismissToast = useCallback((id: string) => dispatch({ type: "dismissToast", id }), []);
  const markRead = useCallback((id: string) => dispatch({ type: "markRead", id, now: Date.now() }), []);
  const markAllRead = useCallback(() => dispatch({ type: "markAllRead", now: Date.now() }), []);
  const clear = useCallback(() => dispatch({ type: "clear" }), []);

  const unreadCount = useMemo(() => state.events.reduce((acc, e) => acc + (e.readAt ? 0 : 1), 0), [state.events]);
  const toastEvents = useMemo(() => {
    const byId = new Map(state.events.map((e) => [e.id, e] as const));
    return state.toasts
      .map((t) => byId.get(t.id))
      .filter(Boolean)
      .sort((a, b) => (b!.lastTs ?? 0) - (a!.lastTs ?? 0)) as NotificationEvent[];
  }, [state.events, state.toasts]);

  const api = useMemo<NotificationCenterApi>(
    () => ({ events: state.events, toasts: toastEvents, unreadCount, upsert, toast, dismissToast, markRead, markAllRead, clear }),
    [state.events, toastEvents, unreadCount, upsert, toast, dismissToast, markRead, markAllRead, clear],
  );

  return <NotificationCenterContext.Provider value={api}>{children}</NotificationCenterContext.Provider>;
}

export function useNotificationCenter() {
  const ctx = useContext(NotificationCenterContext);
  if (!ctx) throw new Error("useNotificationCenter must be used within NotificationCenterProvider");
  return ctx;
}
