from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import threading


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _format_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except Exception:
        return str(value)


@dataclass
class CheckItem:
    title: str
    status: str  # "pass" | "warn" | "fail"
    detail: Optional[str] = None


@dataclass
class LLMCall:
    name: str
    duration_s: float
    detail: Optional[str] = None


@dataclass
class ScenarioBlock:
    name: str
    input_data: Dict[str, Any]
    outputs: List[Dict[str, Any]] = field(default_factory=list)
    checks: List[CheckItem] = field(default_factory=list)
    llm_calls: List[LLMCall] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


class LLMReportWriter:
    def __init__(self, path: str):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._scenarios: List[ScenarioBlock] = []
        self._current: Optional[ScenarioBlock] = None
        self._started_at = _now_ts()

    def start_scenario(self, name: str, input_data: Dict[str, Any]) -> None:
        with self._lock:
            block = ScenarioBlock(name=name, input_data=input_data)
            self._scenarios.append(block)
            self._current = block

    def add_output(self, title: str, data: Any) -> None:
        with self._lock:
            if not self._current:
                return
            self._current.outputs.append({"title": title, "data": data})

    def add_check(self, title: str, status: str, detail: Optional[str] = None) -> None:
        with self._lock:
            if not self._current:
                return
            self._current.checks.append(CheckItem(title=title, status=status, detail=detail))

    def add_llm_call(self, name: str, duration_s: float, detail: Optional[str] = None) -> None:
        with self._lock:
            if not self._current:
                return
            self._current.llm_calls.append(LLMCall(name=name, duration_s=duration_s, detail=detail))

    def add_note(self, note: str) -> None:
        with self._lock:
            if not self._current:
                return
            self._current.notes.append(note)

    def finalize(self) -> str:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            content = self._render()
            self.path.write_text(content, encoding="utf-8")
            return str(self.path)

    def _render(self) -> str:
        total = len(self._scenarios)
        passed = sum(1 for s in self._scenarios if all(c.status == "pass" for c in s.checks))
        failed = sum(1 for s in self._scenarios if any(c.status == "fail" for c in s.checks))
        warned = total - passed - failed

        lines = []
        lines.append(f"# LLM Quality Report — {self._started_at}")
        lines.append("")
        lines.append("## Summary")
        lines.append(f"- Total scenarios: {total}")
        lines.append(f"- Pass: {passed}")
        lines.append(f"- Warning: {warned}")
        lines.append(f"- Fail: {failed}")
        lines.append("")
        lines.append("---")
        lines.append("")

        for scenario in self._scenarios:
            lines.append(f"## Scenario: {scenario.name}")
            lines.append("")
            lines.append("**Input**")
            lines.append("```json")
            lines.append(_format_json(scenario.input_data))
            lines.append("```")
            lines.append("")

            if scenario.llm_calls:
                lines.append("**LLM Timings**")
                for call in scenario.llm_calls:
                    detail = f" — {call.detail}" if call.detail else ""
                    lines.append(f"- `{call.name}`: {call.duration_s:.2f}s{detail}")
                lines.append("")

            if scenario.outputs:
                lines.append("**Outputs**")
                for output in scenario.outputs:
                    lines.append(f"- {output['title']}")
                    lines.append("```json")
                    lines.append(_format_json(output["data"]))
                    lines.append("```")
                lines.append("")

            if scenario.checks:
                lines.append("**Checks**")
                for check in scenario.checks:
                    label = "[PASS]" if check.status == "pass" else "[WARN]" if check.status == "warn" else "[FAIL]"
                    detail = f" — {check.detail}" if check.detail else ""
                    lines.append(f"- {label} {check.title}{detail}")
                lines.append("")

            if scenario.notes:
                lines.append("**Reviewer Notes**")
                for note in scenario.notes:
                    lines.append(f"- {note}")
                lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)
