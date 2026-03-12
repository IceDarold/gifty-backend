"use client";

import React, { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import { openLiveWebSocket } from "@/lib/liveAnalytics";
import type { LiveUpdateMessage } from "@/types/liveAnalytics";

const ALL_CHANNELS = [
  "dashboard.stats",
  "dashboard.health",
  "dashboard.scraping",
  "dashboard.sources",
  "dashboard.trends",
  "dashboard.workers",
  "dashboard.queue",
  "dashboard.discovered_categories",
  "ops.overview",
  "ops.sites",
  "ops.pipeline",
  "ops.scheduler_stats",
  "ops.items_trend",
  "ops.tasks_trend",
  "ops.discovery",
  "ops.runs.active",
  "ops.runs.queued",
  "ops.runs.completed",
  "ops.runs.error",
  "ops.run_details",
  "intelligence.summary",
  "llm.logs",
  "llm.stats",
  "llm.outliers",
  "llm.throughput",
  "llm.breakdown.status",
  "llm.breakdown.provider",
  "llm.breakdown.model",
  "llm.breakdown.call_type",
  "logs.snapshot",
  "logs.tail",
  "logs.services",
  "catalog.products",
  "settings.runtime",
  "settings.subscriber",
  "settings.merchants",
  "frontend.apps",
  "frontend.releases",
  "frontend.profiles",
  "frontend.rules",
  "frontend.runtime_state",
  "frontend.allowed_hosts",
  "frontend.audit_log",
];

type AdminStreamState = {
  connected: boolean;
  items: Record<string, any>;
};

type AdminStreamContextValue = AdminStreamState & {
  addChannel: (channel: string) => void;
  request: (channel: string, params?: Record<string, any>) => Promise<any>;
};

const AdminStreamContext = createContext<AdminStreamContextValue>({
  connected: false,
  items: {},
  addChannel: () => {},
  request: async () => null,
});

export function AdminStreamProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AdminStreamState>({ connected: false, items: {} });
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<number>(0);
  const channelsRef = useRef<Set<string>>(new Set(ALL_CHANNELS));
  const pendingRef = useRef<Map<string, (data: any) => void>>(new Map());
  const pendingErrRef = useRef<Map<string, (err: any) => void>>(new Map());

  useEffect(() => {
    let active = true;

    const connect = async () => {
      const token =
        process.env.NEXT_PUBLIC_LIVE_ANALYTICS_WS_TOKEN ||
        process.env.NEXT_PUBLIC_API_INTERNAL_TOKEN ||
        "";
      const ws = openLiveWebSocket(token);
      wsRef.current = ws;

      ws.onopen = () => {
        retryRef.current = 0;
        setState((prev) => ({ ...prev, connected: true }));
        ws.send(JSON.stringify({ type: "subscribe", channels: Array.from(channelsRef.current) }));
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data) as LiveUpdateMessage;
          if (msg.type === "error" && msg.req_id) {
            const rej = pendingErrRef.current.get(msg.req_id);
            if (rej) {
              pendingErrRef.current.delete(msg.req_id);
              pendingRef.current.delete(msg.req_id);
              rej(msg);
              return;
            }
          }
          if (msg.type === "snapshot" && msg.req_id) {
            const resolve = pendingRef.current.get(msg.req_id);
            if (resolve) {
              pendingRef.current.delete(msg.req_id);
              pendingErrRef.current.delete(msg.req_id);
              resolve(msg.data ?? null);
              return;
            }
          }
          if ((msg.type === "update" || msg.type === "snapshot") && msg.channel) {
            setState((prev) => ({
              ...prev,
              items: {
                ...prev.items,
                [msg.channel!]: msg.data ?? null,
              },
            }));
          }
        } catch {
          // ignore
        }
      };

      ws.onclose = () => {
        setState((prev) => ({ ...prev, connected: false }));
        if (!active) return;
        retryRef.current += 1;
        const delay = Math.min(5000, 250 * retryRef.current);
        window.setTimeout(connect, delay);
      };
    };

    connect();
    return () => {
      active = false;
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, []);

  const addChannel = (channel: string) => {
    if (!channel || channelsRef.current.has(channel)) return;
    channelsRef.current.add(channel);
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "subscribe", channels: [channel] }));
    }
  };

  const request = (channel: string, params?: Record<string, any>) => {
    const reqId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    return new Promise((resolve, reject) => {
      pendingRef.current.set(reqId, resolve);
      pendingErrRef.current.set(reqId, reject);
      const sendReq = () => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
          return false;
        }
        wsRef.current.send(
          JSON.stringify({
            type: "request",
            req_id: reqId,
            channel,
            params: params || {},
          }),
        );
        return true;
      };
      if (sendReq()) {
        return;
      }
      let attempts = 0;
      const timer = window.setInterval(() => {
        attempts += 1;
        if (sendReq()) {
          window.clearInterval(timer);
          return;
        }
        if (attempts >= 10) {
          window.clearInterval(timer);
          pendingRef.current.delete(reqId);
          pendingErrRef.current.delete(reqId);
          reject(new Error("ws_not_connected"));
        }
      }, 200);
    });
  };

  const value = useMemo(() => ({ ...state, addChannel, request }), [state]);
  return <AdminStreamContext.Provider value={value}>{children}</AdminStreamContext.Provider>;
}

export function useAdminChannel<T = any>(channel: string): { data: T | undefined; connected: boolean } {
  const ctx = useContext(AdminStreamContext);
  useEffect(() => {
    if (channel) {
      ctx.addChannel(channel);
    }
  }, [channel, ctx]);
  return { data: ctx.items[channel] as T | undefined, connected: ctx.connected };
}

export function useAdminRequest() {
  return useContext(AdminStreamContext).request;
}
