from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


EventSource = Literal["api", "worker", "scheduler", "internal"]


class AnalyticsEventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    version: int = 1
    occurred_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: EventSource = "api"
    tenant_id: str = "default"
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    dims: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, float] = Field(default_factory=dict)
    payload: Dict[str, Any] = Field(default_factory=dict)


def build_event(
    *,
    event_type: str,
    source: EventSource,
    tenant_id: str = "default",
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    dims: Optional[Dict[str, Any]] = None,
    metrics: Optional[Dict[str, float]] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> AnalyticsEventEnvelope:
    return AnalyticsEventEnvelope(
        event_type=event_type,
        source=source,
        tenant_id=tenant_id,
        session_id=session_id,
        user_id=user_id,
        dims=dims or {},
        metrics=metrics or {},
        payload=payload or {},
    )
