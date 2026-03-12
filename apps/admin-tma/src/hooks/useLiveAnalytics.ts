import { useEffect, useMemo, useRef, useState } from "react";
import { openLiveWebSocket } from "@/lib/liveAnalytics";
import type { LiveSnapshotItem, LiveUpdateMessage } from "@/types/liveAnalytics";

type State = {
  connected: boolean;
  items: Record<string, LiveSnapshotItem>;
};

export function useLiveAnalytics(channels: string[]) {
  const [state, setState] = useState<State>({ connected: false, items: {} });
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<number>(0);

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
        ws.send(JSON.stringify({ type: "subscribe", channels }));
      };

      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data) as LiveUpdateMessage;
          if ((msg.type === "update" || msg.type === "snapshot") && msg.channel && msg.seq && msg.data) {
            setState((prev) => {
              const current = prev.items[msg.channel!];
              if (current && current.seq >= msg.seq!) return prev;
              return {
                ...prev,
                items: {
                  ...prev.items,
                  [msg.channel!]: { channel: msg.channel!, seq: msg.seq!, data: msg.data! },
                },
              };
            });
          }
        } catch {
          // ignore malformed
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
  }, [channels.join(",")]);

  return useMemo(() => state, [state]);
}
