import json
import logging
from typing import Optional
from redis import asyncio as aioredis
from app.config import get_settings
from recommendations.models import RecommendationSession

logger = logging.getLogger(__name__)

class SessionStorage:
    def __init__(self):
        settings = get_settings()
        self.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        self.ttl = settings.session_ttl_seconds
        
        # Check connection or use fakeredis as fallback in dev
        if settings.env == "dev":
            try:
                import fakeredis.aioredis
                self.fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
                logger.info("SessionStorage: Using fakeredis for local development")
            except ImportError:
                self.fake_redis = None
        else:
            self.fake_redis = None

    async def _get_conn(self):
        if self.fake_redis:
            return self.fake_redis
        return self.redis

    async def save_session(self, session: RecommendationSession):
        """Saves session state to Redis."""
        try:
            conn = await self._get_conn()
            key = f"rec_session:{session.session_id}"
            data = session.model_dump_json()
            await conn.setex(key, self.ttl, data)
        except Exception as e:
            logger.error(f"Failed to save session to Redis: {e}")
            if self.fake_redis is None and get_settings().env == "dev":
                logger.warning("Failing over to temporary fakeredis")
                import fakeredis.aioredis
                self.fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
                await self.fake_redis.setex(f"rec_session:{session.session_id}", self.ttl, session.model_dump_json())

    async def get_session(self, session_id: str) -> Optional[RecommendationSession]:
        """Loads session state from Redis."""
        try:
            conn = await self._get_conn()
            key = f"rec_session:{session_id}"
            data = await conn.get(key)
            if not data:
                return None
            return RecommendationSession.model_validate_json(data)
        except Exception as e:
            logger.error(f"Failed to load session from Redis: {e}")
            return None

    async def delete_session(self, session_id: str):
        """Deletes session from Redis."""
        try:
            key = f"rec_session:{session_id}"
            await self.redis.delete(key)
        except Exception as e:
            logger.error(f"Failed to delete session from Redis: {e}")

_storage: Optional[SessionStorage] = None

def get_session_storage() -> SessionStorage:
    global _storage
    if _storage is None:
        _storage = SessionStorage()
    return _storage
