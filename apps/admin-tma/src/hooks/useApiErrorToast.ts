"use client";

import { useEffect, useMemo, useRef } from "react";
import { getApiErrorMessage, getApiErrorStatus, isServerApiError } from "@/lib/api";
import { useNotificationCenter } from "@/contexts/NotificationCenterContext";

type UseApiErrorToastArgs = {
  id: string;
  title: string;
  errors: unknown[];
  enabled?: boolean;
  ttlMs?: number;
};

export function useApiErrorToast({ id, title, errors, enabled = true, ttlMs = 10000 }: UseApiErrorToastArgs) {
  const { toast: showToast } = useNotificationCenter();
  const lastSignatureRef = useRef<string | null>(null);

  const snapshot = useMemo(() => {
    if (!enabled) return null;
    const apiErrors = errors.filter((e) => isServerApiError(e));
    if (!apiErrors.length) return null;

    const signature = apiErrors
      .map((e, idx) => {
        const status = getApiErrorStatus(e);
        const msg = getApiErrorMessage(e);
        return `${idx}:${status ?? "x"}:${msg}`;
      })
      .join("|");

    const first = apiErrors[0]!;
    const status = getApiErrorStatus(first);
    const msg = getApiErrorMessage(first);
    const extra = apiErrors.length > 1 ? ` (+${apiErrors.length - 1})` : "";
    const messageRaw = `${msg}${status ? ` (HTTP ${status})` : ""}${extra}`;
    const message = messageRaw.length > 220 ? `${messageRaw.slice(0, 217)}...` : messageRaw;

    return { signature, message };
  }, [enabled, errors]);

  useEffect(() => {
    if (!enabled) {
      lastSignatureRef.current = null;
      return;
    }
    if (!snapshot) {
      lastSignatureRef.current = null;
      return;
    }
    if (lastSignatureRef.current === snapshot.signature) return;
    lastSignatureRef.current = snapshot.signature;

    showToast(
      {
        id,
        level: "error",
        title,
        message: snapshot.message,
        dedupeKey: `${id}:${snapshot.signature}`,
      },
      { ttlMs },
    );
  }, [enabled, snapshot, showToast, id, title, ttlMs]);
}

