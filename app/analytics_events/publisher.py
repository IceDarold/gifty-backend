from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from app.analytics_events.schema import AnalyticsEventEnvelope
from app.analytics_events.topics import subject_for_event
from app.config import get_settings

logger = logging.getLogger(__name__)


class NATSAnalyticsPublisher:
    def __init__(self) -> None:
        self._nc = None
        self._lock = asyncio.Lock()

    async def _connect(self):
        settings = get_settings()
        if self._nc is not None and not getattr(self._nc, "is_closed", False):
            return self._nc

        async with self._lock:
            if self._nc is not None and not getattr(self._nc, "is_closed", False):
                return self._nc
            try:
                from nats.aio.client import Client as NATS  # type: ignore
            except Exception:
                logger.warning("nats-py is unavailable, analytics events publishing is disabled")
                return None

            nc = NATS()
            try:
                timeout_sec = max(0.1, settings.analytics_events_timeout_ms / 1000.0)
                await nc.connect(servers=[settings.nats_url], connect_timeout=timeout_sec)
                self._nc = nc
            except Exception as exc:
                logger.warning("failed to connect to NATS (%s): %s", settings.nats_url, exc)
                return None

        return self._nc

    async def publish(self, event: AnalyticsEventEnvelope) -> bool:
        settings = get_settings()
        if not settings.analytics_events_enabled:
            return False

        nc = await self._connect()
        if nc is None:
            return False

        subject = subject_for_event(event.event_type, prefix=settings.analytics_events_subject_prefix)
        payload = event.model_dump_json().encode("utf-8")
        attempts = 3
        for i in range(attempts):
            try:
                await nc.publish(subject, payload)
                return True
            except Exception as exc:
                if i == attempts - 1:
                    logger.warning("analytics event publish failed subject=%s err=%s", subject, exc)
                    return False
                await asyncio.sleep(0.05 * (2 ** i))
        return False

    async def close(self) -> None:
        if self._nc is not None:
            try:
                await self._nc.drain()
            except Exception:
                pass
            self._nc = None


_publisher = NATSAnalyticsPublisher()


async def publish_analytics_event(event: AnalyticsEventEnvelope) -> bool:
    return await _publisher.publish(event)


async def close_analytics_publisher() -> None:
    await _publisher.close()
