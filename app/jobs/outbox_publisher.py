from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.analytics_events.publisher import _publisher  # reuse NATS connection path
from app.config import get_settings
from app.db import get_session_context
from app.models import OutboxEvent
from app.state_events import build_state_event

logger = logging.getLogger("outbox_publisher")


async def publish_once(batch_size: int = 100) -> int:
    sent = 0
    async with get_session_context() as session:
        result = await session.execute(
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.created_at.asc())
            .limit(batch_size)
        )
        rows = list(result.scalars().all())
        for row in rows:
            try:
                envelope = build_state_event(
                    aggregate_type=row.aggregate_type,
                    aggregate_id=row.aggregate_id,
                    event_type=row.event_type,
                    operation=(row.event_type.rsplit('.', 1)[-1] if row.event_type.rsplit('.', 1)[-1] in {'created','updated','deleted'} else 'updated'),
                    payload=row.payload_json or {},
                    headers=row.headers_json or {},
                )
                nc = await _publisher._connect()
                if nc is None:
                    raise RuntimeError('nats unavailable')
                subject = f"state.events.v1.{row.aggregate_type}"
                await nc.publish(subject, envelope.model_dump_json().encode('utf-8'))
                row.published_at = datetime.now(timezone.utc)
                row.attempts = int(row.attempts or 0) + 1
                row.last_error = None
                sent += 1
            except Exception as exc:
                row.attempts = int(row.attempts or 0) + 1
                row.last_error = str(exc)[:2000]
        await session.commit()
    return sent


async def run_outbox_publisher_loop(interval_seconds: float = 2.0) -> None:
    logger.info("Outbox publisher started interval=%ss", interval_seconds)
    while True:
        try:
            sent = await publish_once()
            if sent:
                logger.info("Outbox publisher sent=%s", sent)
        except Exception:
            logger.exception("outbox publisher tick failed")
        await asyncio.sleep(interval_seconds)


if __name__ == "__main__":
    settings = get_settings()
    asyncio.run(run_outbox_publisher_loop(float(getattr(settings, 'outbox_publish_interval_seconds', 2))))
