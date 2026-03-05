import { describe, expect, it } from "vitest";
import {
  SYNTHETIC_QUEUED_RUN_ID_PREFIX,
  SYNTHETIC_RUNNING_RUN_ID_PREFIX,
  detectLevel,
  formatDuration,
  getRunDisplayTitle,
  isPlaceholderUrl,
  parseIso,
  parseLogLine,
  statusBadgeClass,
  stringifyValue,
} from "./operationsUtils";

describe("operationsUtils", () => {
  it("statusBadgeClass maps known statuses", () => {
    expect(statusBadgeClass("running")).toContain("bg-sky");
    expect(statusBadgeClass("completed")).toContain("bg-emerald");
    expect(statusBadgeClass("error")).toContain("bg-rose");
    expect(statusBadgeClass("queued")).toContain("bg-amber");
    expect(statusBadgeClass("promoted")).toContain("bg-violet");
    expect(statusBadgeClass("unknown")).toContain("bg-white");
  });

  it("isPlaceholderUrl detects placeholders", () => {
    expect(isPlaceholderUrl(null)).toBe(false);
    expect(isPlaceholderUrl("https://example.com")).toBe(false);
    expect(isPlaceholderUrl("https://img.placeholder/foo")).toBe(true);
    expect(isPlaceholderUrl("https://example.com/placeholder.png")).toBe(true);
  });

  it("parseIso returns Date for valid ISO string", () => {
    expect(parseIso(null)).toBeNull();
    expect(parseIso("not-a-date")).toBeNull();
    const d = parseIso("2026-03-04T00:00:00Z");
    expect(d).not.toBeNull();
    expect(d?.toISOString()).toBe("2026-03-04T00:00:00.000Z");
  });

  it("formatDuration formats seconds", () => {
    expect(formatDuration(null)).toBe("-");
    expect(formatDuration(NaN)).toBe("-");
    expect(formatDuration(-1)).toBe("0s");
    expect(formatDuration(5)).toBe("5s");
    expect(formatDuration(65)).toBe("1m 5s");
    expect(formatDuration(3661)).toBe("1h 1m 1s");
  });

  it("getRunDisplayTitle handles synthetic ids", () => {
    expect(getRunDisplayTitle("x")).toBe("Run #x");
    expect(getRunDisplayTitle(SYNTHETIC_QUEUED_RUN_ID_PREFIX, 0)).toBe("Queued task #1");
    expect(getRunDisplayTitle(SYNTHETIC_QUEUED_RUN_ID_PREFIX + 5, 2)).toBe("Queued task #3");
    expect(getRunDisplayTitle(SYNTHETIC_RUNNING_RUN_ID_PREFIX)).toBe("Running task #0");
    expect(getRunDisplayTitle(SYNTHETIC_RUNNING_RUN_ID_PREFIX + 12)).toBe("Running task #12");
    expect(getRunDisplayTitle(42)).toBe("Run #42");
  });

  it("stringifyValue is stable for primitives and objects", () => {
    expect(stringifyValue("a")).toBe("a");
    expect(stringifyValue(null)).toBe("");
    expect(stringifyValue({ a: 1 })).toBe("{\"a\":1}");
  });

  it("detectLevel recognizes log severity by text", () => {
    expect(detectLevel("ERROR something failed")).toBe("error");
    expect(detectLevel("warning retrying")).toBe("warn");
    expect(detectLevel("completed successfully")).toBe("success");
    expect(detectLevel("info: queued")).toBe("info");
    expect(detectLevel("just a line")).toBe("default");
  });

  it("parseLogLine parses JSON and timestamp-prefixed lines", () => {
    const blank = parseLogLine("   ", 1);
    expect(blank.level).toBe("default");
    expect(blank.message).toBe("");

    const jsonLine = parseLogLine('{"timestamp":"2026-03-04T00:00:00Z","level":"error","message":"boom"}', 2);
    expect(jsonLine.timestamp).toBe("2026-03-04T00:00:00Z");
    expect(jsonLine.level).toBe("error");
    expect(jsonLine.message).toBe("boom");

    const tsLine = parseLogLine("2026-03-04T00:00:00Z something queued", 3);
    expect(tsLine.timestamp).toBe("2026-03-04T00:00:00Z");
    expect(tsLine.level).toBe("info");
    expect(tsLine.message).toBe("something queued");
  });
});

