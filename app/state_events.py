from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field


Operation = Literal["created", "updated", "deleted"]


class StateEventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    aggregate_type: str
    aggregate_id: str
    event_type: str
    operation: Operation
    version: int = 1
    occurred_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, Any] = Field(default_factory=dict)


def build_state_event(*, aggregate_type: str, aggregate_id: str, event_type: str, operation: Operation, payload: dict[str, Any], headers: dict[str, Any] | None = None) -> StateEventEnvelope:
    return StateEventEnvelope(
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_type=event_type,
        operation=operation,
        payload=payload,
        headers=headers or {},
    )
