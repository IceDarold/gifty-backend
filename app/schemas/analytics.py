from __future__ import annotations

from pydantic import BaseModel, Field


class PostHogStatsResponse(BaseModel):
    dau: int = 0
    quiz_completion_rate: float = 0.0
    gift_ctr: float = 0.0
    total_sessions: int = 0
    source: str = Field(default="live", description="live | cache | stale_cache | unavailable")
    stale: bool = False
    cache_age_seconds: int | None = None
    last_updated: str
