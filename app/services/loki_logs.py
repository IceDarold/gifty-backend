from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

import httpx
import websockets

from app.config import get_settings

logger = logging.getLogger(__name__)


def _to_ws_url(http_url: str) -> str:
    url = http_url.rstrip("/")
    if url.startswith("https://"):
        return "wss://" + url[len("https://") :]
    if url.startswith("http://"):
        return "ws://" + url[len("http://") :]
    # Fallback: assume it's already ws-like.
    return url


def _now_ns() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1_000_000_000)


@dataclass(frozen=True)
class LokiLogLine:
    ts_ns: int
    line: str
    labels: dict[str, str]

    @property
    def ts_iso(self) -> str:
        return datetime.fromtimestamp(self.ts_ns / 1_000_000_000, tz=timezone.utc).isoformat()


class LokiLogsClient:
    def __init__(self, base_url: Optional[str] = None) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.loki_url or "http://loki:3100").rstrip("/")

    async def label_values(self, label: str) -> list[str]:
        url = f"{self.base_url}/loki/api/v1/label/{label}/values"
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
            values = data.get("data") or []
            return [str(v) for v in values if v]

    async def query_range(
        self,
        *,
        query: str,
        start_ns: int,
        end_ns: int,
        limit: int = 200,
        direction: str = "BACKWARD",
    ) -> list[LokiLogLine]:
        url = f"{self.base_url}/loki/api/v1/query_range"
        params = {
            "query": query,
            "start": str(int(start_ns)),
            "end": str(int(end_ns)),
            "limit": str(max(1, min(int(limit), 2000))),
            "direction": direction,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            payload = resp.json() if resp.content else {}
        result = (((payload or {}).get("data") or {}).get("result")) or []
        out: list[LokiLogLine] = []
        for stream in result:
            labels = stream.get("stream") or {}
            values = stream.get("values") or []
            for ts, line in values:
                try:
                    ts_ns = int(ts)
                except Exception:
                    continue
                out.append(LokiLogLine(ts_ns=ts_ns, line=str(line), labels={k: str(v) for k, v in labels.items()}))
        out.sort(key=lambda x: x.ts_ns, reverse=(direction.upper() == "BACKWARD"))
        return out

    async def tail(
        self,
        *,
        query: str,
        limit: int = 200,
    ) -> AsyncGenerator[LokiLogLine, None]:
        """
        Loki tail is a WebSocket endpoint. We connect to it and re-yield individual lines.

        Response frames look like:
        {
          "streams": [
            {"stream": {...labels...}, "values": [["ts","line"], ...]}
          ],
          "dropped_entries": [...]
        }
        """
        ws_base = _to_ws_url(self.base_url)
        url = f"{ws_base}/loki/api/v1/tail?query={httpx.QueryParams({'q': query})['q']}&limit={max(1, min(int(limit), 2000))}"
        # A bit conservative pings to keep the socket alive behind proxies.
        async with websockets.connect(url, ping_interval=20, ping_timeout=20, max_size=8 * 1024 * 1024) as ws:
            while True:
                raw = await ws.recv()
                if not raw:
                    continue
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                streams = msg.get("streams") or []
                for stream in streams:
                    labels = stream.get("stream") or {}
                    values = stream.get("values") or []
                    for ts, line in values:
                        try:
                            ts_ns = int(ts)
                        except Exception:
                            ts_ns = _now_ns()
                        yield LokiLogLine(ts_ns=ts_ns, line=str(line), labels={k: str(v) for k, v in labels.items()})


def build_logql_query(*, service: Optional[str] = None, container: Optional[str] = None, contains: Optional[str] = None) -> str:
    # Prefer "service" label (docker_sd_configs + compose labels).
    label_filters: list[str] = []
    if service:
        label_filters.append(f'service="{service}"')
    if container:
        label_filters.append(f'container="{container}"')
    if not label_filters:
        # Fallback to whatever promtail sends for docker logs.
        label_filters.append('job="docker"')
    selector = "{" + ",".join(label_filters) + "}"
    if contains:
        # Loki: |= "text"
        escaped = contains.replace("\\", "\\\\").replace('"', '\\"')
        return f'{selector} |= "{escaped}"'
    return selector

