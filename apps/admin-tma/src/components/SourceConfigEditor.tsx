"use client";

import React, { useMemo, useState } from "react";
import { X, Save, Loader2 } from "lucide-react";

type SourceConfigEditorProps = {
  source: any;
  onClose: () => void;
  onSave?: (id: number, payload: Record<string, any>) => Promise<any> | void;
  isSaving?: boolean;
};

export function SourceConfigEditor({ source, onClose, onSave, isSaving }: SourceConfigEditorProps) {
  const initial = useMemo(() => {
    const cfg = source?.config ?? {};
    try {
      return JSON.stringify(cfg, null, 2);
    } catch {
      return "{}";
    }
  }, [source]);

  const [text, setText] = useState(initial);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    setError(null);
    let parsed: any;
    try {
      parsed = text.trim() ? JSON.parse(text) : {};
    } catch (e: any) {
      setError(String(e?.message || "Invalid JSON"));
      return;
    }

    if (!onSave) {
      onClose();
      return;
    }

    await Promise.resolve(onSave(Number(source?.id), { config: parsed }));
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[80] flex items-end sm:items-center justify-center bg-black/65 p-2 sm:p-4">
      <div className="w-full max-w-2xl rounded-2xl border border-white/20 bg-[#0a1322] shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between border-b border-white/12 px-4 py-3">
          <div>
            <h3 className="text-lg font-semibold text-white">Edit Source Config</h3>
            <p className="text-xs text-white/70">{String(source?.site_key || source?.id || "")}</p>
          </div>
          <button
            className="rounded-lg border border-white/25 px-2 py-1 text-xs text-white/85 hover:bg-white/10"
            onClick={onClose}
          >
            <X size={14} />
          </button>
        </div>

        <div className="p-4 space-y-3">
          <div className="rounded-xl border border-white/12 bg-black/20 p-3">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="w-full min-h-[320px] font-mono text-[12px] leading-relaxed bg-transparent outline-none text-white/90"
              spellCheck={false}
            />
          </div>
          {error ? (
            <div className="rounded-xl border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-100">
              {error}
            </div>
          ) : null}
          <div className="flex items-center justify-end gap-2">
            <button
              className="rounded-xl border border-white/15 bg-white/[0.03] px-3 py-2 text-xs font-bold text-white/80 hover:bg-white/10"
              onClick={onClose}
              disabled={!!isSaving}
            >
              Cancel
            </button>
            <button
              className="rounded-xl bg-[var(--tg-theme-button-color)] px-3 py-2 text-xs font-black text-[#042138] hover:brightness-110 active:scale-[0.99] disabled:opacity-60 inline-flex items-center gap-2"
              onClick={() => void handleSave()}
              disabled={!!isSaving}
            >
              {isSaving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
              Save
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

