from __future__ import annotations

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
        return pika.BlockingConnection(params)

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
            # We use a context manager or local connection to avoid keeping long-lived pika connections
            # in the sync-in-async context of FastAPI without a proper connection manager.
            # For small load, this is acceptable.
            connection = self._get_connection()
            channel = connection.channel()
            
            channel.queue_declare(queue=self.queue_name, durable=True)
            
            channel.basic_publish(
                exchange='',
                routing_key=self.queue_name,
                body=json.dumps(payload, default=json_serial),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                )
            )
            connection.close()
            logger.info(f"Notification published to topic '{topic}': {message}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish notification: {e}")
            return False

def get_notification_service() -> NotificationService:
    return NotificationService()
