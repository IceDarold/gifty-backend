export const statusBadgeClass = (status?: string) => {
  switch (status) {
    case "running":
      return "bg-sky-500/20 text-sky-100 border-sky-400/45";
    case "completed":
      return "bg-emerald-500/20 text-emerald-100 border-emerald-400/45";
    case "error":
    case "rejected":
      return "bg-rose-500/20 text-rose-100 border-rose-400/45";
    case "queued":
      return "bg-amber-500/20 text-amber-100 border-amber-400/45";
    case "promoted":
      return "bg-violet-500/20 text-violet-100 border-violet-400/45";
    default:
      return "bg-white/10 text-white/85 border-white/20";
  }
};

export const isPlaceholderUrl = (url?: string | null) => {
  if (!url) return false;
  return /\.placeholder(?:\/|$)/i.test(url) || /placeholder/i.test(url);
};

export const parseIso = (value?: string | null) => {
  if (!value) return null;
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date : null;
};

export const formatDateTime = (value?: string | null) => {
  const date = parseIso(value);
  if (!date) return "-";
  return date.toLocaleString();
};

export const formatDuration = (seconds?: number | null) => {
  if (seconds == null || Number.isNaN(seconds)) return "-";
  const total = Math.max(0, Math.floor(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
};

export const SYNTHETIC_RUNNING_RUN_ID_PREFIX = 1_000_000_000;
export const SYNTHETIC_QUEUED_RUN_ID_PREFIX = 2_000_000_000;

export const getRunDisplayTitle = (runId: unknown, idx = 0) => {
  const idNum = Number(runId);
  if (!Number.isFinite(idNum)) return `Run #${String(runId ?? "?")}`;
  if (idNum >= SYNTHETIC_QUEUED_RUN_ID_PREFIX) {
    return `Queued task #${Math.max(1, idx + 1)}`;
  }
  if (idNum >= SYNTHETIC_RUNNING_RUN_ID_PREFIX) {
    return `Running task #${idNum - SYNTHETIC_RUNNING_RUN_ID_PREFIX}`;
  }
  return `Run #${idNum}`;
};

export const formatDayLabel = (value?: string | null) => {
  const date = parseIso(value);
  if (!date) return "-";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
};

export const formatTrendLabel = (
  value?: string | null,
  granularity: "week" | "day" | "hour" | "minute" = "day",
) => {
  const date = parseIso(value);
  if (!date) return "-";
  if (granularity === "week") {
    return `Wk ${date.toLocaleDateString(undefined, { month: "short", day: "numeric" })}`;
  }
  if (granularity === "day") {
    return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }
  if (granularity === "hour") {
    return date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  }
  return date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
};

export type ParsedLogLine = {
  id: string;
  raw: string;
  timestamp: string | null;
  level: "error" | "warn" | "success" | "info" | "default";
  message: string;
};

export type LogFilter = "all" | "errors" | "warnings" | "info" | "success";

export type LogItem =
  | { kind: "line"; id: string; line: ParsedLogLine }
  | { kind: "json"; id: string; lines: ParsedLogLine[]; summary: string; payload: string };

const LEVEL_KEYS = ["level", "levelname", "severity", "log_level", "lvl"];
const TIME_KEYS = ["timestamp", "time", "ts", "@timestamp", "asctime", "datetime"];
const MESSAGE_KEYS = ["message", "msg", "event", "text", "detail"];

export const stringifyValue = (value: unknown) => {
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return "";
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
};

export const detectLevel = (input: string): ParsedLogLine["level"] => {
  const v = input.toLowerCase();
  if (/(error|exception|traceback|failed|timeout|fatal|critical)/.test(v)) return "error";
  if (/(warn|warning|retry|redeliver)/.test(v)) return "warn";
  if (/(success|completed|done|saved|ingested)/.test(v)) return "success";
  if (/(info|progress|running|start|queued|scrap)/.test(v)) return "info";
  return "default";
};

export const parseLogLine = (line: string, idx: number): ParsedLogLine => {
  const trimmed = line.trim();
  if (!trimmed) {
    return {
      id: `log-${idx}`,
      raw: line,
      timestamp: null,
      level: "default",
      message: "",
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
      return {
        id: `log-${idx}`,
        raw: line,
        timestamp,
        level: detectLevel(`${levelText} ${message}`),
        message,
      };
    } catch {
      // keep as plain text
    }
  }

  const tsMatch = trimmed.match(
    /^(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+\-]\d{2}:?\d{2})?)\s+(.+)$/,
  );
  const timestamp = tsMatch ? tsMatch[1] : null;
  const message = tsMatch ? tsMatch[2] : trimmed;
  return {
    id: `log-${idx}`,
    raw: line,
    timestamp,
    level: detectLevel(message),
    message,
  };
};
