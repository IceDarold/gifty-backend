"use client";

import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";
import { useNotificationCenter } from "@/contexts/NotificationCenterContext";

const toastClassByLevel = (level: string) => {
  if (level === "running") return "border-sky-300/45 bg-sky-500/15 text-sky-100";
  if (level === "success") return "border-emerald-300/45 bg-emerald-500/15 text-emerald-100";
  if (level === "warn") return "border-amber-300/45 bg-amber-500/15 text-amber-100";
  if (level === "error") return "border-rose-300/45 bg-rose-500/15 text-rose-100";
  return "border-white/15 bg-white/[0.04] text-white/90";
};

export function ToastHost() {
  const { toasts, dismissToast } = useNotificationCenter();
  if (!toasts.length) return null;

  return (
    <div className="fixed bottom-4 right-4 z-[80] flex w-[320px] max-w-[calc(100vw-2rem)] flex-col gap-2">
      {toasts.map((t) => (
        <div key={t.id} className={`rounded-xl border p-3 shadow-xl ${toastClassByLevel(t.level)}`}>
          <div className="flex items-start gap-2">
            {t.level === "running" ? (
              <Loader2 size={14} className="mt-0.5 animate-spin" />
            ) : t.level === "success" ? (
              <CheckCircle2 size={14} className="mt-0.5" />
            ) : (
              <AlertCircle size={14} className="mt-0.5" />
            )}
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold leading-tight">
                {t.title}
                {t.count > 1 ? <span className="ml-2 text-xs opacity-80">×{t.count}</span> : null}
              </p>
              <p className="mt-0.5 text-xs opacity-90 break-words">{t.message}</p>
            </div>
            <button className="text-xs opacity-80 hover:opacity-100" onClick={() => dismissToast(t.id)} aria-label="Dismiss">
              x
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

