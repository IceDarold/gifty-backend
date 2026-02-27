"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Check, Copy, Pause, Play, RefreshCcw, Search, Trash2 } from "lucide-react";
import { fetchLogServices, fetchLogsQuery, getLogsStreamUrl } from "@/lib/api";

type LogItem = {
    ts: string;
    ts_ns?: number;
    service?: string | null;
    container?: string | null;
    labels?: Record<string, string>;
    line: string;
};

const MAX_BUFFER = 2500;

const classifyLevel = (line: string): "error" | "warn" | "info" | "debug" | "other" => {
    const s = line.toLowerCase();
    if (s.includes(" error") || s.includes("error:") || s.includes("exception") || s.includes("traceback")) return "error";
    if (s.includes(" warn") || s.includes("warning") || s.includes("warn:")) return "warn";
    if (s.includes(" info") || s.includes("info:")) return "info";
    if (s.includes(" debug") || s.includes("debug:")) return "debug";
    return "other";
};

const levelClass = (lvl: string) => {
    if (lvl === "error") return "text-rose-200";
    if (lvl === "warn") return "text-amber-200";
    if (lvl === "info") return "text-sky-200";
    if (lvl === "debug") return "text-slate-300";
    return "text-slate-200";
};

export function LogsView() {
    const [services, setServices] = useState<string[]>([]);
    const [selectedService, setSelectedService] = useState<string>("api");
    const [serverFilter, setServerFilter] = useState<string>("");
    const [draftFilter, setDraftFilter] = useState<string>("");
    const [paused, setPaused] = useState(false);
    const [items, setItems] = useState<LogItem[]>([]);
    const [isConnecting, setIsConnecting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [copied, setCopied] = useState(false);
    const [unseen, setUnseen] = useState(0);
    const listRef = useRef<HTMLDivElement | null>(null);
    const esRef = useRef<EventSource | null>(null);
    const shouldFollowRef = useRef(true);

    const applyFilter = () => {
        setServerFilter(draftFilter.trim());
        setItems([]);
        setUnseen(0);
        shouldFollowRef.current = true;
    };

    const copyVisible = async () => {
        const text = items.map((l) => `${l.ts} ${l.service || ""} ${l.line}`.trim()).join("\n");
        try {
            await navigator.clipboard.writeText(text);
            setCopied(true);
            setTimeout(() => setCopied(false), 900);
        } catch {
            // ignore
        }
    };

    const sortLogsAsc = (arr: LogItem[]) => {
        // Loki returns ns timestamp; if missing, fall back to string compare.
        return [...arr].sort((a, b) => {
            const an = a.ts_ns ?? 0;
            const bn = b.ts_ns ?? 0;
            if (an !== bn) return an - bn;
            return String(a.ts).localeCompare(String(b.ts));
        });
    };

    const scrollToBottom = () => {
        const el = listRef.current;
        if (!el) return;
        el.scrollTop = el.scrollHeight;
    };

    const isNearBottom = () => {
        const el = listRef.current;
        if (!el) return true;
        const threshold = 28; // px
        return el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
    };

    const connectStream = () => {
        esRef.current?.close();
        esRef.current = null;

        setIsConnecting(true);
        setError(null);
        const url = getLogsStreamUrl({ service: selectedService, q: serverFilter, limit: 200 });
        const source = new EventSource(url);
        esRef.current = source;

        const onLine = (event: MessageEvent) => {
            if (paused) return;
            try {
                const payload = event.data ? JSON.parse(event.data) : {};
                const next: LogItem = {
                    ts: String(payload.ts || ""),
                    ts_ns: payload.ts_ns,
                    service: payload.service,
                    container: payload.container,
                    labels: payload.labels,
                    line: String(payload.line || ""),
                };
                setItems((prev) => {
                    const merged = [...prev, next];
                    return merged.length > MAX_BUFFER ? merged.slice(merged.length - MAX_BUFFER) : merged;
                });

                // Autoscroll: follow only if user is at bottom.
                if (shouldFollowRef.current && isNearBottom()) {
                    queueMicrotask(() => scrollToBottom());
                } else {
                    setUnseen((n) => n + 1);
                }
            } catch {
                // ignore malformed
            }
        };

        const onErrorEvt = (event: MessageEvent) => {
            try {
                const payload = event.data ? JSON.parse(event.data) : {};
                setError(String(payload.message || "Stream error"));
            } catch {
                setError("Stream error");
            }
        };

        const onOpen = () => {
            setIsConnecting(false);
        };

        source.addEventListener("log.line", onLine);
        source.addEventListener("logs.error", onErrorEvt);
        source.onopen = onOpen;
        source.onerror = () => {
            setIsConnecting(false);
        };
    };

    const loadHistory = async () => {
        setError(null);
        try {
            const data = await fetchLogsQuery({ service: selectedService, q: serverFilter || undefined, limit: 200, since_seconds: 600 });
            const history = (data?.items || []) as LogItem[];
            setItems(sortLogsAsc(history));
            setUnseen(0);
            shouldFollowRef.current = true;
            queueMicrotask(() => scrollToBottom());
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : "Failed to load history");
        }
    };

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const data = await fetchLogServices();
                const list = (data?.items || []) as string[];
                if (cancelled) return;
                setServices(list);
                if (list.length && !list.includes(selectedService)) {
                    setSelectedService(list[0]);
                }
            } catch {
                // ignore; UI still works with default
            }
        })();
        return () => {
            cancelled = true;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        // (re)connect on service/filter change
        connectStream();
        void loadHistory();
        return () => {
            esRef.current?.close();
            esRef.current = null;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedService, serverFilter]);

    useEffect(() => {
        // Follow tail after initial load / when user is already at bottom.
        if (!shouldFollowRef.current) return;
        if (!isNearBottom()) return;
        queueMicrotask(() => scrollToBottom());
    }, [items.length]);

    const header = useMemo(() => {
        const label = selectedService || "all";
        return `${label}${serverFilter ? ` · ${serverFilter}` : ""}`;
    }, [selectedService, serverFilter]);

    return (
        <div className="px-4 pt-4 pb-24 space-y-4">
            <div className="flex items-center justify-between gap-3">
                <div>
                    <h2 className="text-lg font-bold">Logs</h2>
                    <p className="text-xs text-[var(--tg-theme-hint-color)]">Loki tail · realtime</p>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setPaused((p) => !p)}
                        className="inline-flex items-center gap-1.5 rounded-xl border border-white/12 bg-black/20 px-3 py-2 text-xs font-semibold text-white/85 active:scale-95 transition-all"
                        title={paused ? "Resume" : "Pause"}
                    >
                        {paused ? <Play size={14} /> : <Pause size={14} />}
                        {paused ? "Resume" : "Pause"}
                    </button>
                    <button
                        onClick={() => {
                            setItems([]);
                            setUnseen(0);
                            shouldFollowRef.current = true;
                        }}
                        className="p-2 rounded-xl border border-white/12 bg-black/20 text-white/80 active:scale-95 transition-all"
                        title="Clear"
                    >
                        <Trash2 size={16} />
                    </button>
                    <button
                        onClick={copyVisible}
                        className="inline-flex items-center gap-1.5 rounded-xl border border-white/12 bg-black/20 px-3 py-2 text-xs font-semibold text-white/85 active:scale-95 transition-all"
                        title="Copy visible logs"
                        disabled={items.length === 0}
                    >
                        {copied ? <Check size={14} /> : <Copy size={14} />}
                        Copy
                    </button>
                    <button
                        onClick={() => {
                            void loadHistory();
                            connectStream();
                        }}
                        className="p-2 rounded-xl border border-white/12 bg-black/20 text-white/80 active:scale-95 transition-all"
                        title="Reconnect"
                    >
                        <RefreshCcw size={16} />
                    </button>
                </div>
            </div>

            <div className="glass card p-3 space-y-3">
                <div className="flex items-center gap-2 flex-wrap">
                    {(services.length ? services : ["api", "scraper", "scheduler", "telegram-bot"]).map((svc) => (
                        <button
                            key={svc}
                            onClick={() => setSelectedService(svc)}
                            className={`rounded-xl border px-3 py-2 text-xs font-semibold transition ${
                                selectedService === svc
                                    ? "border-sky-300/55 bg-sky-500/25 text-sky-100"
                                    : "border-white/12 bg-black/15 text-white/75 hover:bg-black/25"
                            }`}
                        >
                            {svc}
                        </button>
                    ))}
                </div>

                <div className="flex items-center gap-2">
                    <div className="relative flex-1">
                        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/45" />
                        <input
                            value={draftFilter}
                            onChange={(e) => setDraftFilter(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === "Enter") applyFilter();
                            }}
                            placeholder="Server filter (LogQL contains)..."
                            className="w-full pl-9 pr-3 py-2 rounded-xl border border-white/12 bg-black/20 text-xs text-white outline-none focus:border-sky-300/35"
                        />
                    </div>
                    <button
                        onClick={applyFilter}
                        className="rounded-xl border border-emerald-400/45 bg-emerald-500/15 px-3 py-2 text-xs font-semibold text-emerald-100 active:scale-95 transition-all"
                    >
                        Apply
                    </button>
                </div>

                <div className="flex items-center justify-between text-[11px] text-white/65">
                    <span className="truncate">{header}</span>
                    <span className="inline-flex items-center gap-2">
                        {isConnecting ? <span className="text-sky-200">connecting…</span> : <span className="text-emerald-200">live</span>}
                        <span>{items.length} lines</span>
                    </span>
                </div>

                {error ? (
                    <div className="rounded-xl border border-rose-400/35 bg-rose-500/12 p-2 text-xs text-rose-100">
                        {error}
                    </div>
                ) : null}

                <div
                    ref={listRef}
                    className="max-h-[62vh] overflow-auto rounded-xl border border-white/10 bg-[#050c17] p-2 font-mono text-[11px] leading-5"
                    onScroll={() => {
                        const follow = isNearBottom();
                        shouldFollowRef.current = follow;
                        if (follow) setUnseen(0);
                    }}
                >
                    {items.length === 0 ? (
                        <div className="text-slate-300">
                            No logs yet. If this is the first run after enabling docker labels, wait ~10s.
                        </div>
                    ) : (
                        <div className="relative">
                            {items.map((it, idx) => {
                                const lvl = classifyLevel(it.line);
                                return (
                                    <div key={`${it.ts_ns || idx}-${idx}`} className={`py-0.5 ${levelClass(lvl)}`}>
                                        <span className="text-cyan-200/90">{it.ts}</span>
                                        <span className="text-white/35"> · </span>
                                        <span className="text-white/70">{it.service || selectedService}</span>
                                        {it.container ? (
                                            <>
                                                <span className="text-white/35"> · </span>
                                                <span className="text-white/55">{it.container}</span>
                                            </>
                                        ) : null}
                                        <span className="text-white/35"> · </span>
                                        <span className="whitespace-pre-wrap break-words">{it.line}</span>
                                    </div>
                                );
                            })}

                            {!paused && unseen > 0 ? (
                                <div className="sticky bottom-2 flex justify-end pointer-events-none">
                                    <button
                                        className="pointer-events-auto inline-flex items-center gap-2 rounded-xl border border-emerald-400/45 bg-emerald-500/15 px-3 py-2 text-[11px] font-semibold text-emerald-100 shadow-lg"
                                        onClick={() => {
                                            shouldFollowRef.current = true;
                                            setUnseen(0);
                                            scrollToBottom();
                                        }}
                                        title="Jump to latest"
                                    >
                                        <span>Jump to latest</span>
                                        <span className="rounded-md bg-emerald-500/20 px-2 py-0.5 text-[11px]">{`+${unseen}`}</span>
                                    </button>
                                </div>
                            ) : null}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
