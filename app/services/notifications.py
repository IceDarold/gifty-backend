from __future__ import annotations

import asyncio
import json
import logging
import pika
from datetime import datetime
from typing import Any, Dict, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.settings = get_settings()
        self.queue_name = "notifications"

    def _get_connection(self):
        params = pika.URLParameters(self.settings.rabbitmq_url)
        # Keep connection attempts bounded so API requests don't hang on notifications.
        params.connection_attempts = 2
        params.retry_delay = 1
        params.socket_timeout = 5
        params.blocked_connection_timeout = 5
        return pika.BlockingConnection(params)

    def _publish_sync(self, payload: Dict[str, Any]) -> bool:
        connection = self._get_connection()
        channel = connection.channel()

        channel.queue_declare(queue=self.queue_name, durable=True)

        channel.basic_publish(
            exchange="",
            routing_key=self.queue_name,
            body=json.dumps(payload, default=str),
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
            ),
        )
        connection.close()
        return True

    async def notify(self, topic: str, message: str, data: Optional[Dict[str, Any]] = None):
        """
        Publishes a notification message to the RabbitMQ 'notifications' queue.
        """
        # Helper to handle non-serializable objects (like HttpUrl)
        def json_serial(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            if hasattr(obj, "dict"): # Pydantic v1
                return obj.dict()
            if hasattr(obj, "model_dump"): # Pydantic v2
                return obj.model_dump()
            return str(obj)

        payload = {
            "topic": topic,
            "text": message,
            "data": data or {},
            "timestamp": datetime.utcnow().isoformat()
        }

        try:
            # NOTE: pika.BlockingConnection is synchronous and will block the asyncio event loop
            # if called directly from an async endpoint. Run it in a thread.
            def _payload_with_serializer() -> Dict[str, Any]:
                return json.loads(json.dumps(payload, default=json_serial))

            safe_payload = _payload_with_serializer()
            ok = await asyncio.to_thread(self._publish_sync, safe_payload)
            if ok:
                logger.info(f"Notification published to topic '{topic}': {message}")
            return bool(ok)
        except Exception as e:
            logger.error(f"Failed to publish notification: {e}")
            return False

def get_notification_service() -> NotificationService:
    return NotificationService()
