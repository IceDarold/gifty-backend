from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.analytics_events.publisher import publish_analytics_event
from app.analytics_events.schema import build_event

logger = logging.getLogger(__name__)


async def emit_event(
    *,
    event_type: str,
    source: str,
    tenant_id: str = "default",
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    dims: Optional[Dict[str, Any]] = None,
    metrics: Optional[Dict[str, float]] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> bool:
    try:
        envelope = build_event(
            event_type=event_type,
            source=source,  # type: ignore[arg-type]
            tenant_id=tenant_id,
            session_id=session_id,
            user_id=user_id,
            dims=dims,
            metrics=metrics,
            payload=payload,
        )
    except Exception as exc:
        logger.warning("invalid analytics event payload type=%s err=%s", event_type, exc)
        return False

    return await publish_analytics_event(envelope)
