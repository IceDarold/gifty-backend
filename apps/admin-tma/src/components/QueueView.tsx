"use client";

import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { ArrowDown, ArrowUp, Braces, Check, ChevronDown, ChevronRight, Clock3, Copy, Download, FileText, ListChecks, Loader2, PlayCircle, Search, X } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { useQueueRunDetails } from "@/hooks/useDashboard";

interface QueueViewProps {
    queue?: any;
    tasksData?: any;
    isLoadingTasks?: boolean;
    historyData?: any;
    isLoadingHistory?: boolean;
}

type ParsedLogLine = {
    id: string;
    raw: string;
    timestamp: string | null;
    level: "error" | "warn" | "success" | "info" | "default";
    message: string;
    details: string | null;
    groupKey: string | null;
    jsonObject: Record<string, unknown> | null;
};

type LogItem =
    | { kind: "line"; id: string; line: ParsedLogLine }
    | { kind: "trace"; id: string; lines: ParsedLogLine[]; summary: string }
    | { kind: "json"; id: string; lines: ParsedLogLine[]; summary: string; payload: string };

type LogFilter = "all" | "errors" | "warnings" | "http" | "scrapy" | "db" | "info";

const LEVEL_KEYS = ["level", "levelname", "severity", "log_level", "lvl"];
const TIME_KEYS = ["timestamp", "time", "ts", "@timestamp", "asctime", "datetime"];
const MESSAGE_KEYS = ["message", "msg", "event", "text", "detail"];
const LOG_PREFS_KEY = "queue-log-prefs-v1";

const fmtAgo = (value?: string | null) => {
    if (!value) return "never";
    try {
        return formatDistanceToNow(new Date(value), { addSuffix: true });
    } catch {
        return "unknown";
    }
};

const fmtDuration = (value?: number | null) => {
    if (typeof value !== "number" || !Number.isFinite(value)) return "n/a";
    if (value < 1) return `${Math.round(value * 1000)}ms`;
    if (value < 60) return `${value.toFixed(1)}s`;
    const mins = Math.floor(value / 60);
    const secs = Math.round(value % 60);
    return `${mins}m ${secs}s`;
};

const stringifyValue = (value: unknown) => {
    if (typeof value === "string") return value;
    if (value === null || value === undefined) return "";
    try {
        return JSON.stringify(value);
    } catch {
        return String(value);
    }
};

const detectLevel = (input: string): ParsedLogLine["level"] => {
    const v = input.toLowerCase();
    if (/(error|exception|traceback|failed|timeout|fatal|critical)/.test(v)) return "error";
    if (/(warn|warning|retry|redeliver)/.test(v)) return "warn";
    if (/(success|completed|done|saved|ingested)/.test(v)) return "success";
    if (/(info|progress|running|start|queued|scrap)/.test(v)) return "info";
    return "default";
};

const parseLogLine = (line: string, idx: number): ParsedLogLine => {
    const trimmed = line.trim();
    if (!trimmed) {
        return {
            id: `log-${idx}`,
            raw: line,
            timestamp: null,
            level: "default",
            message: "",
            details: null,
            groupKey: null,
            jsonObject: null,
        };
    }

    if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
        try {
            const obj = JSON.parse(trimmed) as Record<string, unknown>;
            const tsKey = TIME_KEYS.find((k) => obj[k] !== undefined);
            const lvlKey = LEVEL_KEYS.find((k) => obj[k] !== undefined);
            const msgKey = MESSAGE_KEYS.find((k) => obj[k] !== undefined);
            const timestamp = tsKey ? stringifyValue(obj[tsKey]) : null;
            const levelText = lvlKey ? stringifyValue(obj[lvlKey]) : "";
            const message = msgKey ? stringifyValue(obj[msgKey]) : trimmed;
            const groupCandidate = obj.run_id ?? obj.source_id ?? obj.spider ?? obj.site_key ?? obj.task_id;

            const detailsEntries = Object.entries(obj)
                .filter(([k]) => ![...TIME_KEYS, ...LEVEL_KEYS, ...MESSAGE_KEYS].includes(k))
                .slice(0, 4)
                .map(([k, v]) => `${k}=${stringifyValue(v)}`);

            return {
                id: `log-${idx}`,
                raw: line,
                timestamp,
                level: detectLevel(`${levelText} ${message}`),
                message,
                details: detailsEntries.length ? detailsEntries.join(" • ") : null,
                groupKey: groupCandidate !== undefined ? String(groupCandidate) : null,
                jsonObject: obj,
            };
        } catch {
            // not json
        }
    }

    const tsMatch = trimmed.match(
        /^(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+\-]\d{2}:?\d{2})?)\s+(.+)$/
    );
    const timestamp = tsMatch ? tsMatch[1] : null;
    const message = tsMatch ? tsMatch[2] : trimmed;
    const bracketGroup = message.match(/\[(run_id|source_id|spider|site_key|task_id)=([^\]]+)\]/i);

    return {
        id: `log-${idx}`,
        raw: line,
        timestamp,
        level: detectLevel(message),
        message,
        details: null,
        groupKey: bracketGroup ? bracketGroup[2] : null,
        jsonObject: null,
    };
};

const isTraceStart = (line: ParsedLogLine) => /traceback \(most recent call last\):/i.test(line.raw);

const isTraceRelated = (line: ParsedLogLine) => {
    const raw = line.raw.trim();
    return (
        /^file\s+/i.test(raw) ||
        /^[a-z_]+(?:error|exception):/i.test(raw) ||
        /during handling of the above exception/i.test(raw) ||
        /traceback/i.test(raw) ||
        /^[\s\^~]+$/.test(raw) ||
        raw.startsWith("at ")
    );
};

const isJsonLikeStart = (line: ParsedLogLine) => {
    const raw = line.raw.trim();
    return raw.startsWith("{") || raw.startsWith("[") || raw.startsWith("{'") || raw.startsWith("[{");
};

const isJsonLikeLine = (line: ParsedLogLine) => {
    const raw = line.raw.trim();
    if (!raw) return false;
    if (raw.startsWith("{") || raw.startsWith("}") || raw.startsWith("[") || raw.startsWith("]")) return true;
    if (/^['"][^'"]+['"]\s*:/.test(raw)) return true;
    if (/^\"[^"]+\"\s*:/.test(raw)) return true;
    if (raw.endsWith(",") && raw.includes(":")) return true;
    return false;
};

const buildLogItems = (lines: ParsedLogLine[]): LogItem[] => {
    const items: LogItem[] = [];
    let i = 0;
    while (i < lines.length) {
        const current = lines[i];
        if (isJsonLikeStart(current)) {
            const jsonLines: ParsedLogLine[] = [current];
            let j = i + 1;
            while (j < lines.length && isJsonLikeLine(lines[j])) {
                jsonLines.push(lines[j]);
                j += 1;
            }
            if (jsonLines.length >= 2) {
                const summaryRaw = jsonLines[0].raw.trim();
                const summary = summaryRaw.length > 100 ? `${summaryRaw.slice(0, 100)}...` : summaryRaw;
                items.push({
                    kind: "json",
                    id: `json-${i}`,
                    lines: jsonLines,
                    summary,
                    payload: jsonLines.map((l) => l.raw).join("\n"),
                });
                i = j;
                continue;
            }
        }

        if (isTraceStart(current)) {
            const traceLines: ParsedLogLine[] = [current];
            let j = i + 1;
            while (j < lines.length && isTraceRelated(lines[j])) {
                traceLines.push(lines[j]);
                j += 1;
            }
            const tail = traceLines[traceLines.length - 1]?.message || "Exception";
            items.push({
                kind: "trace",
                id: `trace-${i}`,
                lines: traceLines,
                summary: tail.length > 120 ? `${tail.slice(0, 120)}...` : tail,
            });
            i = j;
            continue;
        }
        items.push({ kind: "line", id: current.id, line: current });
        i += 1;
    }
    return items;
};

const formatTimeColumn = (value: string | null) => {
    if (!value) return "--:--:--";
    const d = new Date(value);
    if (!Number.isNaN(d.valueOf())) {
        const hh = String(d.getHours()).padStart(2, "0");
        const mm = String(d.getMinutes()).padStart(2, "0");
        const ss = String(d.getSeconds()).padStart(2, "0");
        const ms = String(d.getMilliseconds()).padStart(3, "0");
        return `${hh}:${mm}:${ss}.${ms}`;
    }
    return value.slice(11, 23) || value;
};

const levelBadgeClass = (level: ParsedLogLine["level"]) => {
    switch (level) {
        case "error":
            return "text-red-300 bg-red-500/15 border-red-400/30";
        case "warn":
            return "text-amber-300 bg-amber-500/15 border-amber-400/30";
        case "success":
            return "text-emerald-300 bg-emerald-500/15 border-emerald-400/30";
        case "info":
            return "text-sky-200 bg-sky-500/15 border-sky-300/30";
        default:
            return "text-slate-300 bg-white/8 border-white/20";
    }
};

const levelTextClass = (level: ParsedLogLine["level"]) => {
    switch (level) {
        case "error":
            return "text-red-300";
        case "warn":
            return "text-amber-300";
        case "success":
            return "text-emerald-300";
        case "info":
            return "text-sky-200";
        default:
            return "text-slate-200";
    }
};

const inferLikelyCause = (lines: ParsedLogLine[]) => {
    const text = lines.map((l) => l.raw.toLowerCase()).join("\n");
    if (/status\/404|http status\/404| 404 |not found/.test(text)) {
        return "Likely cause: wrong endpoint path (404 Not Found). Check API base URL and route composition.";
    }
    if (/connection refused|connect_tcp|host='api'|host=\"api\"|name or service not known/.test(text)) {
        return "Likely cause: spider could not reach API service (network/hostname issue in docker network).";
    }
    if (/invalid internal token|unauthorized telegram session|forbidden/.test(text)) {
        return "Likely cause: auth mismatch. Verify internal token / Telegram session headers.";
    }
    if (/timeout|timed out/.test(text)) {
        return "Likely cause: timeout (service slow or unreachable). Increase timeout or inspect target service.";
    }
    if (/traceback|exception|error/.test(text)) {
        return "Likely cause: runtime exception. Expand traceback block and inspect the last exception line.";
    }
    return null;
};

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const renderJsonStyledLine = (input: string): ReactNode => {
    const text = input.trim();
    if (!text) return null;

    const tokenRegex =
        /("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\b-?\d+(?:\.\d+)?\b|\btrue\b|\bfalse\b|\bnull\b|[{}\[\],:])/gi;
    const nodes: ReactNode[] = [];
    let last = 0;
    let match: RegExpExecArray | null;
    let idx = 0;

    while ((match = tokenRegex.exec(text)) !== null) {
        const start = match.index;
        const token = match[0];

        if (start > last) {
            nodes.push(
                <span key={`plain-${idx++}`} className="text-slate-300">
                    {text.slice(last, start)}
                </span>
            );
        }

        const end = tokenRegex.lastIndex;
        const rest = text.slice(end);
        const nextNonSpace = rest.match(/^\s*(.)/)?.[1];
        let cls = "text-slate-300";

        if (/^["']/.test(token)) {
            cls = nextNonSpace === ":" ? "text-sky-300" : "text-orange-300";
        } else if (/^-?\d/.test(token)) {
            cls = "text-emerald-300";
        } else if (/^(true|false|null)$/i.test(token)) {
            cls = "text-emerald-300";
        } else if (/^[{}\[\]]$/.test(token)) {
            cls = "text-fuchsia-300";
        } else if (/^[:,]$/.test(token)) {
            cls = "text-slate-400";
        }

        nodes.push(
            <span key={`tok-${idx++}`} className={cls}>
                {token}
            </span>
        );

        last = end;
    }

    if (last < text.length) {
        nodes.push(
            <span key={`tail-${idx++}`} className="text-slate-300">
                {text.slice(last)}
            </span>
        );
    }

    return <>{nodes}</>;
};

export function QueueView({ queue, tasksData, isLoadingTasks, historyData, isLoadingHistory }: QueueViewProps) {
    const items = Array.isArray(tasksData?.items) ? tasksData.items : [];
    const hasTasksError = tasksData?.status && tasksData.status !== "ok";
    const historyItems = Array.isArray(historyData?.items) ? historyData.items : [];
    const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
    const selectedRun = useMemo(
        () => historyItems.find((run: any) => run.id === selectedRunId) || null,
        [historyItems, selectedRunId]
    );
    const runDetailsQuery = useQueueRunDetails(selectedRunId);
    const runDetails = runDetailsQuery.data?.item;
    const displayDuration = runDetails?.duration_seconds ?? selectedRun?.duration_seconds;

    const [logsCopied, setLogsCopied] = useState(false);
    const [activeFilter, setActiveFilter] = useState<LogFilter>("all");
    const [searchQuery, setSearchQuery] = useState("");
    const [activeMatchIndex, setActiveMatchIndex] = useState(0);
    const [autoScroll, setAutoScroll] = useState(true);
    const [expandedTraceIds, setExpandedTraceIds] = useState<Record<string, boolean>>({});
    const [expandedJsonIds, setExpandedJsonIds] = useState<Record<string, boolean>>({});
    const [jsonPreview, setJsonPreview] = useState<{ title: string; payload: string } | null>(null);
    const listRef = useRef<HTMLDivElement | null>(null);
    const lineRefs = useRef<Record<string, HTMLDivElement | null>>({});

    const parsedLogLines = useMemo(
        () =>
            String(runDetails?.logs || "")
                .split(/\r?\n/)
                .filter((line) => line.trim().length > 0)
                .map((line, idx) => parseLogLine(line, idx)),
        [runDetails?.logs]
    );

    const logItems = useMemo(() => buildLogItems(parsedLogLines), [parsedLogLines]);
    const likelyCause = useMemo(() => inferLikelyCause(parsedLogLines), [parsedLogLines]);

    useEffect(() => {
        if (typeof window === "undefined") return;
        const raw = window.localStorage.getItem(LOG_PREFS_KEY);
        if (!raw) return;
        try {
            const prefs = JSON.parse(raw) as Partial<{ filter: LogFilter; autoScroll: boolean; search: string }>;
            if (prefs.filter) setActiveFilter(prefs.filter);
            if (typeof prefs.autoScroll === "boolean") setAutoScroll(prefs.autoScroll);
            if (typeof prefs.search === "string") setSearchQuery(prefs.search);
        } catch {
            // ignore
        }
    }, []);

    useEffect(() => {
        if (typeof window === "undefined") return;
        window.localStorage.setItem(
            LOG_PREFS_KEY,
            JSON.stringify({ filter: activeFilter, autoScroll, search: searchQuery })
        );
    }, [activeFilter, autoScroll, searchQuery]);

    const linePassesFilter = (line: ParsedLogLine) => {
        const text = `${line.raw} ${line.message} ${line.details || ""}`.toLowerCase();
        if (activeFilter === "errors" && line.level !== "error") return false;
        if (activeFilter === "warnings" && line.level !== "warn") return false;
        if (activeFilter === "info" && line.level !== "info") return false;
        if (activeFilter === "http" && !/(http|status|request|response|connect_tcp)/.test(text)) return false;
        if (activeFilter === "scrapy" && !/scrapy/.test(text)) return false;
        if (activeFilter === "db" && !/(sql|postgres|db|database|redis)/.test(text)) return false;
        if (searchQuery.trim() && !text.includes(searchQuery.toLowerCase())) return false;
        return true;
    };

    const visibleItems = useMemo(
        () =>
            logItems.filter((item) => {
                if (item.kind === "line") return linePassesFilter(item.line);
                if (item.kind === "trace" || item.kind === "json") return item.lines.some(linePassesFilter);
                return false;
            }),
        [logItems, activeFilter, searchQuery]
    );

    const matchIds = useMemo(() => {
        const q = searchQuery.trim().toLowerCase();
        if (!q) return [] as string[];
        const ids: string[] = [];
        for (const item of visibleItems) {
            if (item.kind === "line") {
                if (`${item.line.raw} ${item.line.message} ${item.line.details || ""}`.toLowerCase().includes(q)) ids.push(item.id);
            } else {
                item.lines.forEach((line, idx) => {
                    if (`${line.raw} ${line.message} ${line.details || ""}`.toLowerCase().includes(q)) {
                        ids.push(`${item.id}-l${idx}`);
                    }
                });
            }
        }
        return ids;
    }, [visibleItems, searchQuery]);

    useEffect(() => {
        setActiveMatchIndex(0);
    }, [searchQuery, activeFilter, selectedRunId]);

    useEffect(() => {
        if (!matchIds.length) return;
        const id = matchIds[Math.min(activeMatchIndex, matchIds.length - 1)];
        const el = lineRefs.current[id];
        if (el) el.scrollIntoView({ block: "center", behavior: "smooth" });
    }, [activeMatchIndex, matchIds]);

    useEffect(() => {
        if (!autoScroll) return;
        const container = listRef.current;
        if (!container) return;
        container.scrollTop = container.scrollHeight;
    }, [parsedLogLines.length, autoScroll]);

    const logStats = useMemo(() => {
        let errors = 0;
        let warnings = 0;
        let infos = 0;
        let success = 0;
        for (const line of parsedLogLines) {
            if (line.level === "error") errors += 1;
            if (line.level === "warn") warnings += 1;
            if (line.level === "info") infos += 1;
            if (line.level === "success") success += 1;
        }
        return {
            errors,
            warnings,
            infos,
            success,
            lastEvent: parsedLogLines.at(-1)?.timestamp || null,
        };
    }, [parsedLogLines]);

    const copyLogs = async () => {
        const logs = String(runDetails?.logs || "").trim();
        if (!logs) return;
        try {
            await navigator.clipboard.writeText(logs);
            setLogsCopied(true);
            window.setTimeout(() => setLogsCopied(false), 1200);
        } catch {
            setLogsCopied(false);
        }
    };

    const copyErrorLogs = async () => {
        const content = parsedLogLines
            .filter((line) => line.level === "error")
            .map((line) => line.raw)
            .join("\n")
            .trim();
        if (!content) return;
        await navigator.clipboard.writeText(content);
        setLogsCopied(true);
        window.setTimeout(() => setLogsCopied(false), 1200);
    };

    const downloadLogs = () => {
        const logs = String(runDetails?.logs || "");
        const blob = new Blob([logs], { type: "text/plain;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `run-${selectedRunId || "logs"}.log`;
        a.click();
        URL.revokeObjectURL(url);
    };

    const highlightText = (text: string) => {
        const q = searchQuery.trim();
        if (!q) return <>{text}</>;
        const safe = escapeRegExp(q);
        const regex = new RegExp(`(${safe})`, "ig");
        return text.split(regex).map((part, idx) =>
            regex.test(part) ? (
                <mark key={idx} className="bg-yellow-300/30 text-yellow-100 rounded px-0.5">
                    {part}
                </mark>
            ) : (
                <span key={idx}>{part}</span>
            )
        );
    };

    const renderTextWithLinksAndCodes = (text: string) => {
        const urlRegex = /(https?:\/\/[^\s'\"]+)/g;
        const parts = text.split(urlRegex);
        return parts.map((part, idx) => {
            if (urlRegex.test(part)) {
                return (
                    <a key={idx} href={part} target="_blank" rel="noreferrer" className="underline text-cyan-300 hover:text-cyan-200">
                        {highlightText(part)}
                    </a>
                );
            }
            const codeRegex = /\b([1-5]\d{2})\b/g;
            const sub = part.split(codeRegex);
            return (
                <span key={idx}>
                    {sub.map((piece, pIdx) => {
                        if (/^[1-5]\d{2}$/.test(piece)) {
                            const n = Number(piece);
                            const cls = n >= 500 ? "text-red-300" : n >= 400 ? "text-amber-300" : n >= 200 ? "text-emerald-300" : "text-sky-300";
                            return (
                                <span key={pIdx} className={`${cls} font-semibold`}>
                                    {piece}
                                </span>
                            );
                        }
                        return <span key={pIdx}>{highlightText(piece)}</span>;
                    })}
                </span>
            );
        });
    };

    return (
        <div className="p-4 pb-24 space-y-4">
            <div>
                <h2 className="text-lg font-bold">Queue Tasks</h2>
                <p className="text-xs text-[var(--tg-theme-hint-color)]">
                    RabbitMQ queue and queued parser jobs
                </p>
            </div>

            <div className="grid grid-cols-2 gap-3">
                <div className="card">
                    <div className="text-[10px] uppercase font-bold text-[var(--tg-theme-hint-color)]">Ready</div>
                    <div className="mt-1 text-2xl font-black">{queue?.messages_ready || 0}</div>
                </div>
                <div className="card">
                    <div className="text-[10px] uppercase font-bold text-[var(--tg-theme-hint-color)]">In Progress</div>
                    <div className="mt-1 text-2xl font-black">{queue?.messages_unacknowledged || 0}</div>
                </div>
            </div>

            <div className="card space-y-2">
                <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold flex items-center gap-2">
                        <ListChecks size={15} className="text-[var(--tg-theme-button-color)]" />
                        Queue Messages (RabbitMQ)
                    </h3>
                    <span className="text-[10px] text-[var(--tg-theme-hint-color)]">{items.length} items</span>
                </div>

                {isLoadingTasks ? (
                    <div className="text-xs text-[var(--tg-theme-hint-color)] py-4 text-center inline-flex items-center gap-2 justify-center w-full">
                        <Loader2 size={12} className="animate-spin" />
                        Loading queue messages...
                    </div>
                ) : hasTasksError ? (
                    <div className="text-xs text-red-400 py-4 text-center">
                        Failed to load queue messages: {tasksData?.message || "unknown error"}
                    </div>
                ) : items.length === 0 ? (
                    <div className="text-xs text-[var(--tg-theme-hint-color)] py-4 text-center">
                        Queue is empty
                    </div>
                ) : (
                    <div className="space-y-2">
                        {items.map((item: any) => (
                            <div key={`${item.idx}-${item.payload_bytes}`} className="rounded-xl bg-[var(--tg-theme-secondary-bg-color)]/50 p-3 flex items-center justify-between">
                                <div>
                                    <div className="text-xs font-bold">{item.task?.site_key || item.task?.source_id || "task"}</div>
                                    <div className="text-[10px] text-[var(--tg-theme-hint-color)]">
                                        strategy: {item.task?.strategy || "deep"} • bytes: {item.payload_bytes || 0}
                                    </div>
                                </div>
                                <div className="text-[10px] font-bold px-2 py-1 rounded-md bg-amber-500/20 text-amber-500 flex items-center gap-1">
                                    {item.redelivered ? "RETRY" : "READY"}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div className="card space-y-2">
                <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold flex items-center gap-2">
                        <PlayCircle size={15} className="text-blue-400" />
                        Queue Throughput
                    </h3>
                    <span className="text-[10px] text-[var(--tg-theme-hint-color)]">live</span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                    <div className="rounded-xl bg-[var(--tg-theme-secondary-bg-color)]/50 p-3">
                        <div className="text-[10px] uppercase font-bold text-[var(--tg-theme-hint-color)]">Publish rate</div>
                        <div className="text-lg font-black mt-1">{Number(queue?.rate_publish || 0).toFixed(2)}/s</div>
                    </div>
                    <div className="rounded-xl bg-[var(--tg-theme-secondary-bg-color)]/50 p-3">
                        <div className="text-[10px] uppercase font-bold text-[var(--tg-theme-hint-color)]">Unacked</div>
                        <div className="text-lg font-black mt-1">{queue?.messages_unacknowledged || 0}</div>
                    </div>
                </div>
            </div>

            <div className="card text-xs text-[var(--tg-theme-hint-color)] flex items-center gap-2">
                <Clock3 size={14} />
                Queue total: {queue?.messages_total || 0}, consumers: {queue?.consumers || 0}
            </div>

            <div className="card space-y-2">
                <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold">Recent History</h3>
                    <span className="text-[10px] text-[var(--tg-theme-hint-color)]">{historyItems.length} runs</span>
                </div>
                {isLoadingHistory ? (
                    <div className="text-xs text-[var(--tg-theme-hint-color)] py-3 inline-flex items-center gap-2">
                        <Loader2 size={12} className="animate-spin" />
                        Loading history...
                    </div>
                ) : historyItems.length === 0 ? (
                    <div className="text-xs text-[var(--tg-theme-hint-color)] py-3 text-center">
                        No completed runs yet
                    </div>
                ) : (
                    <div className="space-y-2 max-h-72 overflow-auto pr-1">
                        {historyItems.map((run: any) => (
                            <button
                                key={run.id}
                                onClick={() => setSelectedRunId(run.id)}
                                className={`w-full text-left rounded-xl p-3 transition-colors border ${
                                    selectedRunId === run.id
                                        ? "bg-sky-500/15 border-sky-300/40"
                                        : "bg-[var(--tg-theme-secondary-bg-color)]/50 border-transparent hover:border-white/10"
                                }`}
                            >
                                <div className="flex items-center justify-between">
                                    <div className="text-xs font-bold">{run.site_key}</div>
                                    <span
                                        className={`text-[10px] font-bold px-2 py-1 rounded-md ${
                                            run.status === "completed"
                                                ? "bg-emerald-500/20 text-emerald-500"
                                                : run.status === "error"
                                                ? "bg-red-500/20 text-red-400"
                                                : "bg-slate-500/20 text-slate-300"
                                        }`}
                                    >
                                        {String(run.status || "unknown").toUpperCase()}
                                    </span>
                                </div>
                                <div className="mt-1 text-[10px] text-[var(--tg-theme-hint-color)]">
                                    scraped: {run.items_scraped || 0} • new: {run.items_new || 0}
                                    {typeof run.duration_seconds === "number" ? ` • ${run.duration_seconds.toFixed(1)}s` : ""}
                                </div>
                                <div className="mt-1 text-[10px] text-[var(--tg-theme-hint-color)]">
                                    {fmtAgo(run.created_at)}
                                </div>
                                {run.error_message ? (
                                    <div className="mt-1 text-[10px] text-red-400 line-clamp-2">{run.error_message}</div>
                                ) : null}
                            </button>
                        ))}
                    </div>
                )}
            </div>

            {selectedRunId ? (
                <div className="fixed inset-0 z-[70] flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
                    <div className="w-full max-w-4xl rounded-t-3xl sm:rounded-3xl overflow-hidden shadow-2xl glass border border-white/12 animate-in slide-in-from-bottom duration-200">
                        <div className="p-4 border-b border-white/10 flex items-start justify-between gap-2">
                            <div>
                                <h3 className="text-base font-bold">Run Details</h3>
                                <p className="text-[11px] text-[var(--tg-theme-hint-color)]">
                                    run #{selectedRunId} • {runDetails?.site_key || selectedRun?.site_key || "source"}
                                </p>
                            </div>
                            <button
                                onClick={() => setSelectedRunId(null)}
                                className="rounded-lg p-1.5 bg-white/5 hover:bg-white/10 border border-white/10"
                                aria-label="Close run details"
                            >
                                <X size={15} />
                            </button>
                        </div>

                        <div className="p-4 max-h-[82vh] overflow-y-auto space-y-3">
                            {runDetailsQuery.isLoading ? (
                                <div className="text-xs text-[var(--tg-theme-hint-color)] py-4 inline-flex items-center gap-2">
                                    <Loader2 size={12} className="animate-spin" />
                                    Loading run details...
                                </div>
                            ) : runDetailsQuery.isError ? (
                                <div className="text-xs text-red-400">Failed to load run details.</div>
                            ) : (
                                <>
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                                        <div className="rounded-xl bg-[var(--tg-theme-secondary-bg-color)]/45 p-3">
                                            <div className="text-[10px] uppercase font-bold text-[var(--tg-theme-hint-color)]">Duration</div>
                                            <div className="mt-1 font-black text-base">{fmtDuration(displayDuration)}</div>
                                        </div>
                                        <div className="rounded-xl bg-[var(--tg-theme-secondary-bg-color)]/45 p-3">
                                            <div className="text-[10px] uppercase font-bold text-[var(--tg-theme-hint-color)]">Status</div>
                                            <div className="mt-1 font-black text-base">{String(runDetails?.run_status || selectedRun?.status || "unknown").toUpperCase()}</div>
                                        </div>
                                        <div className="rounded-xl bg-[var(--tg-theme-secondary-bg-color)]/45 p-3">
                                            <div className="text-[10px] uppercase font-bold text-[var(--tg-theme-hint-color)]">Errors</div>
                                            <div className="mt-1 font-black text-base text-red-300">{logStats.errors}</div>
                                        </div>
                                        <div className="rounded-xl bg-[var(--tg-theme-secondary-bg-color)]/45 p-3">
                                            <div className="text-[10px] uppercase font-bold text-[var(--tg-theme-hint-color)]">Last Event</div>
                                            <div className="mt-1 font-black text-sm text-cyan-300">{formatTimeColumn(logStats.lastEvent)}</div>
                                        </div>
                                    </div>

                                    {likelyCause ? (
                                        <div className="rounded-xl border border-amber-400/30 bg-amber-500/10 p-3 text-xs text-amber-200">
                                            {likelyCause}
                                        </div>
                                    ) : null}

                                    {runDetails?.error_message ? (
                                        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-300">
                                            {runDetails.error_message}
                                        </div>
                                    ) : null}

                                    <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                                        <div className="text-[10px] uppercase font-bold text-[var(--tg-theme-hint-color)] inline-flex items-center gap-1 mb-2">
                                            <FileText size={12} />
                                            Logs
                                        </div>

                                        <div className="sticky top-0 z-10 bg-black/45 backdrop-blur-sm rounded-lg border border-white/10 p-2 mb-2 space-y-2">
                                            <div className="flex flex-wrap items-center gap-2">
                                                {(["all", "errors", "warnings", "http", "scrapy", "db", "info"] as LogFilter[]).map((f) => (
                                                    <button
                                                        key={f}
                                                        onClick={() => setActiveFilter(f)}
                                                        className={`text-[10px] uppercase px-2 py-1 rounded-md border ${
                                                            activeFilter === f ? "border-sky-300/40 bg-sky-500/20 text-sky-100" : "border-white/15 bg-white/5 text-slate-300"
                                                        }`}
                                                    >
                                                        {f}
                                                    </button>
                                                ))}
                                            </div>

                                            <div className="flex flex-wrap items-center gap-2">
                                                <div className="relative flex-1 min-w-[180px]">
                                                    <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-400" />
                                                    <input
                                                        value={searchQuery}
                                                        onChange={(e) => setSearchQuery(e.target.value)}
                                                        placeholder="Search logs..."
                                                        className="w-full h-8 pl-7 pr-2 rounded-md bg-white/5 border border-white/12 text-xs outline-none focus:border-sky-300/40"
                                                    />
                                                </div>
                                                <button
                                                    onClick={() => setActiveMatchIndex((prev) => (matchIds.length ? (prev - 1 + matchIds.length) % matchIds.length : 0))}
                                                    disabled={!matchIds.length}
                                                    className="h-8 px-2 rounded-md border border-white/12 bg-white/5 text-xs disabled:opacity-40"
                                                >
                                                    <ArrowUp size={12} />
                                                </button>
                                                <button
                                                    onClick={() => setActiveMatchIndex((prev) => (matchIds.length ? (prev + 1) % matchIds.length : 0))}
                                                    disabled={!matchIds.length}
                                                    className="h-8 px-2 rounded-md border border-white/12 bg-white/5 text-xs disabled:opacity-40"
                                                >
                                                    <ArrowDown size={12} />
                                                </button>
                                                <span className="text-[10px] text-slate-300 min-w-[64px] text-right">
                                                    {matchIds.length ? `${Math.min(activeMatchIndex + 1, matchIds.length)}/${matchIds.length}` : "0/0"}
                                                </span>
                                            </div>

                                            <div className="flex flex-wrap items-center gap-2">
                                                <button
                                                    onClick={copyLogs}
                                                    disabled={!runDetails?.logs?.trim()}
                                                    className="text-[10px] font-bold inline-flex items-center gap-1 px-2 py-1 rounded-md border border-white/12 bg-white/5 hover:bg-white/10 disabled:opacity-50"
                                                >
                                                    {logsCopied ? <Check size={12} /> : <Copy size={12} />} Copy all
                                                </button>
                                                <button
                                                    onClick={copyErrorLogs}
                                                    disabled={!logStats.errors}
                                                    className="text-[10px] font-bold inline-flex items-center gap-1 px-2 py-1 rounded-md border border-white/12 bg-white/5 hover:bg-white/10 disabled:opacity-50"
                                                >
                                                    <Copy size={12} /> Copy errors
                                                </button>
                                                <button
                                                    onClick={downloadLogs}
                                                    disabled={!runDetails?.logs?.trim()}
                                                    className="text-[10px] font-bold inline-flex items-center gap-1 px-2 py-1 rounded-md border border-white/12 bg-white/5 hover:bg-white/10 disabled:opacity-50"
                                                >
                                                    <Download size={12} /> Download .log
                                                </button>
                                                <button
                                                    onClick={() => setAutoScroll((prev) => !prev)}
                                                    className={`text-[10px] font-bold inline-flex items-center gap-1 px-2 py-1 rounded-md border ${
                                                        autoScroll ? "border-emerald-300/40 bg-emerald-500/20 text-emerald-100" : "border-white/12 bg-white/5 text-slate-300"
                                                    }`}
                                                >
                                                    Auto-scroll {autoScroll ? "ON" : "OFF"}
                                                </button>
                                            </div>
                                        </div>

                                        {visibleItems.length > 0 ? (
                                            <div ref={listRef} className="max-h-[52vh] overflow-auto pr-1 font-mono text-[11px] leading-relaxed space-y-1">
                                                {visibleItems.map((item) => {
                                                    if (item.kind === "line") {
                                                        return (
                                                            <div key={item.id} ref={(el) => { lineRefs.current[item.id] = el; }} className="py-0.5">
                                                                <div className="flex items-start gap-2">
                                                                    <span className="opacity-35 min-w-[1.8rem] text-right">{item.line.id.replace("log-", "")}</span>
                                                                    <span className="text-cyan-300/90 min-w-[7.8rem] whitespace-nowrap">{formatTimeColumn(item.line.timestamp)}</span>
                                                                    <span className={`uppercase text-[9px] px-1 py-[1px] rounded border ${levelBadgeClass(item.line.level)}`}>{item.line.level}</span>
                                                                    <span className={`break-words ${levelTextClass(item.line.level)}`}>{renderTextWithLinksAndCodes(item.line.message)}</span>
                                                                    {item.line.jsonObject ? (
                                                                        <button
                                                                            onClick={() => setJsonPreview({ title: `line ${item.line.id.replace("log-", "")}`, payload: JSON.stringify(item.line.jsonObject, null, 2) })}
                                                                            className="ml-auto shrink-0 text-slate-300 hover:text-white p-0.5"
                                                                            title="View JSON"
                                                                        >
                                                                            <Braces size={12} />
                                                                        </button>
                                                                    ) : null}
                                                                </div>
                                                                {item.line.details ? (
                                                                    <div className="ml-[13.2rem] text-[10px] text-slate-400 break-words">{renderTextWithLinksAndCodes(item.line.details)}</div>
                                                                ) : null}
                                                            </div>
                                                        );
                                                    }

                                                    if (item.kind === "json") {
                                                        const expanded = !!expandedJsonIds[item.id];
                                                        const visibleJsonLines = expanded ? item.lines : item.lines.slice(0, 1);
                                                        return (
                                                            <div key={item.id} className="py-1 border-l-2 border-violet-400/35 pl-2 bg-violet-500/[0.04] rounded-r-md">
                                                                <button
                                                                    onClick={() => setExpandedJsonIds((prev) => ({ ...prev, [item.id]: !expanded }))}
                                                                    className="text-[10px] uppercase tracking-[0.06em] text-violet-200 inline-flex items-center gap-1"
                                                                >
                                                                    {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                                                                    JSON block ({item.lines.length} lines) • {item.summary}
                                                                </button>
                                                                <div className="mt-1 space-y-0.5">
                                                                    {visibleJsonLines.map((line, idx) => {
                                                                        const lineId = `${item.id}-l${idx}`;
                                                                        return (
                                                                            <div key={lineId} ref={(el) => { lineRefs.current[lineId] = el; }} className="flex items-start gap-2">
                                                                                <span className="opacity-35 min-w-[1.8rem] text-right">{line.id.replace("log-", "")}</span>
                                                                                {line.timestamp ? (
                                                                                    <span className="text-cyan-300/90 min-w-[7.8rem] whitespace-nowrap">{formatTimeColumn(line.timestamp)}</span>
                                                                                ) : null}
                                                                                <span className="break-words">{renderJsonStyledLine(line.raw)}</span>
                                                                            </div>
                                                                        );
                                                                    })}
                                                                </div>
                                                            </div>
                                                        );
                                                    }

                                                    const expanded = !!expandedTraceIds[item.id];
                                                    const visibleTraceLines = expanded ? item.lines : item.lines.slice(0, 2);

                                                    return (
                                                        <div key={item.id} className="py-1 border-l-2 border-red-400/35 pl-2 bg-red-500/[0.03] rounded-r-md">
                                                            <button
                                                                onClick={() => setExpandedTraceIds((prev) => ({ ...prev, [item.id]: !expanded }))}
                                                                className="text-[10px] uppercase tracking-[0.06em] text-red-200 inline-flex items-center gap-1"
                                                            >
                                                                {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                                                                Python Traceback ({item.lines.length} lines) • {item.summary}
                                                            </button>
                                                            <div className="mt-1 space-y-0.5">
                                                                {visibleTraceLines.map((line, idx) => {
                                                                    const lineId = `${item.id}-l${idx}`;
                                                                    return (
                                                                        <div key={lineId} ref={(el) => { lineRefs.current[lineId] = el; }} className="flex items-start gap-2">
                                                                            <span className="opacity-35 min-w-[1.8rem] text-right">{line.id.replace("log-", "")}</span>
                                                                            <span className="text-cyan-300/90 min-w-[7.8rem] whitespace-nowrap">{formatTimeColumn(line.timestamp)}</span>
                                                                            <span className={`uppercase text-[9px] px-1 py-[1px] rounded border ${levelBadgeClass(line.level)}`}>{line.level}</span>
                                                                            <span className={`break-words ${levelTextClass(line.level)}`}>{renderTextWithLinksAndCodes(line.message)}</span>
                                                                        </div>
                                                                    );
                                                                })}
                                                            </div>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        ) : (
                                            <div className="mt-2 text-[11px] text-slate-300">No logs match current filters/search.</div>
                                        )}
                                    </div>
                                </>
                            )}
                        </div>
                    </div>
                </div>
            ) : null}

            {jsonPreview ? (
                <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/70 backdrop-blur-sm">
                    <div className="w-full max-w-2xl rounded-2xl border border-white/15 glass overflow-hidden">
                        <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
                            <div className="text-sm font-bold">JSON • {jsonPreview.title}</div>
                            <button onClick={() => setJsonPreview(null)} className="p-1.5 rounded-md bg-white/5 border border-white/10">
                                <X size={14} />
                            </button>
                        </div>
                        <pre className="max-h-[70vh] overflow-auto p-4 text-[12px] font-mono leading-relaxed text-slate-200 bg-black/30">
                            {jsonPreview.payload}
                        </pre>
                    </div>
                </div>
            ) : null}
        </div>
    );
}
