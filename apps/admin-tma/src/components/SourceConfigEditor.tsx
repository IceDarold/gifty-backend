"use client";

import { useState } from "react";
import { Loader2, Save, X } from "lucide-react";

interface SourceConfigEditorProps {
    source: any;
    onClose: () => void;
    onSave: (id: number, payload: Record<string, any>) => Promise<any> | void;
    isSaving?: boolean;
}

export function SourceConfigEditor({ source, onClose, onSave, isSaving }: SourceConfigEditorProps) {
    const [url, setUrl] = useState(source?.url || "");
    const [priority, setPriority] = useState(String(source?.priority ?? 50));
    const [refreshInterval, setRefreshInterval] = useState(String(source?.refresh_interval_hours ?? 24));
    const [configText, setConfigText] = useState(JSON.stringify(source?.config || {}, null, 2));
    const [error, setError] = useState<string | null>(null);

    const handleSave = async () => {
        try {
            const parsedConfig = JSON.parse(configText || "{}");
            await onSave(source.id, {
                url,
                priority: Number(priority),
                refresh_interval_hours: Number(refreshInterval),
                config: parsedConfig,
            });
            onClose();
        } catch (e: any) {
            setError(e?.message || "Invalid JSON config");
        }
    };

    return (
        <div className="fixed inset-0 z-[80] bg-black/70 backdrop-blur-sm flex items-end sm:items-center justify-center">
            <div className="w-full max-w-xl bg-[var(--tg-theme-bg-color)] rounded-t-3xl sm:rounded-3xl overflow-hidden shadow-2xl">
                <div className="flex items-center justify-between p-4 border-b border-[var(--tg-theme-secondary-bg-color)]">
                    <h3 className="font-bold">Edit Source Config</h3>
                    <button onClick={onClose} className="p-2 rounded-lg hover:bg-[var(--tg-theme-secondary-bg-color)]">
                        <X size={18} />
                    </button>
                </div>

                <div className="p-4 space-y-3 max-h-[80vh] overflow-auto">
                    {error && <div className="text-xs text-red-500 bg-red-500/10 p-2 rounded-lg">{error}</div>}
                    <div>
                        <label className="text-[10px] uppercase font-bold text-[var(--tg-theme-hint-color)]">URL</label>
                        <input
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                            className="mt-1 w-full rounded-xl border border-[var(--tg-theme-secondary-bg-color)] bg-[var(--tg-theme-section-bg-color)] p-2.5 text-sm"
                        />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                        <div>
                            <label className="text-[10px] uppercase font-bold text-[var(--tg-theme-hint-color)]">Priority</label>
                            <input
                                type="number"
                                value={priority}
                                onChange={(e) => setPriority(e.target.value)}
                                className="mt-1 w-full rounded-xl border border-[var(--tg-theme-secondary-bg-color)] bg-[var(--tg-theme-section-bg-color)] p-2.5 text-sm"
                            />
                        </div>
                        <div>
                            <label className="text-[10px] uppercase font-bold text-[var(--tg-theme-hint-color)]">Interval (hours)</label>
                            <input
                                type="number"
                                value={refreshInterval}
                                onChange={(e) => setRefreshInterval(e.target.value)}
                                className="mt-1 w-full rounded-xl border border-[var(--tg-theme-secondary-bg-color)] bg-[var(--tg-theme-section-bg-color)] p-2.5 text-sm"
                            />
                        </div>
                    </div>
                    <div>
                        <label className="text-[10px] uppercase font-bold text-[var(--tg-theme-hint-color)]">Config JSON</label>
                        <textarea
                            rows={10}
                            value={configText}
                            onChange={(e) => setConfigText(e.target.value)}
                            className="mt-1 w-full rounded-xl border border-[var(--tg-theme-secondary-bg-color)] bg-[var(--tg-theme-section-bg-color)] p-3 text-xs font-mono"
                        />
                    </div>
                </div>

                <div className="p-4 border-t border-[var(--tg-theme-secondary-bg-color)]">
                    <button
                        onClick={handleSave}
                        disabled={isSaving}
                        className="w-full py-3 rounded-xl bg-[var(--tg-theme-button-color)] text-white font-bold flex items-center justify-center gap-2 disabled:opacity-50"
                    >
                        {isSaving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                        Save
                    </button>
                </div>
            </div>
        </div>
    );
}
