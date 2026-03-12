import type { LiveSnapshotResponse } from "@/types/liveAnalytics";

const base = process.env.NEXT_PUBLIC_LIVE_ANALYTICS_BASE_URL || "";

const wsBase = (() => {
  if (base.startsWith("https://")) return base.replace("https://", "wss://");
  if (base.startsWith("http://")) return base.replace("http://", "ws://");
  if (typeof window !== "undefined") {
    const proto = window.location.protocol === "https:" ? "wss://" : "ws://";
    return `${proto}${window.location.host}`;
  }
  return "ws://localhost:8095";
})();

export async function fetchLiveSnapshot(channels: string[]): Promise<LiveSnapshotResponse> {
  const query = channels.length > 0 ? `?channels=${encodeURIComponent(channels.join(","))}` : "";
  const url = `${base}/api/v1/live-analytics/snapshot${query}`;
  const res = await fetch(url, { method: "GET" });
  if (!res.ok) {
    throw new Error(`live snapshot failed: ${res.status}`);
  }
  return (await res.json()) as LiveSnapshotResponse;
}

export function openLiveWebSocket(token?: string): WebSocket {
  const query = token ? `?access_token=${encodeURIComponent(token)}` : "";
  const url = `${wsBase}/api/v1/live-analytics/ws${query}`;
  const ws = new WebSocket(url);
  return ws;
}
