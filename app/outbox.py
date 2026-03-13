from __future__ import annotations

from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OutboxEvent


async def enqueue_outbox_event(
    session: AsyncSession,
    *,
    aggregate_type: str,
    aggregate_id: str,
    event_type: str,
    payload: dict[str, Any],
    headers: Optional[dict[str, Any]] = None,
) -> OutboxEvent:
    row = OutboxEvent(
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_type=event_type,
        payload_json=payload,
        headers_json=headers or {},
    )
    session.add(row)
    await session.flush()
    return row
