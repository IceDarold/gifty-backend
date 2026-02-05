import pika
import json
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)

def publish_parsing_task(task_data: dict):
    settings = get_settings()
    try:
        params = pika.URLParameters(settings.rabbitmq_url)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()

        channel.queue_declare(queue='parsing_tasks', durable=True)
        
        channel.basic_publish(
            exchange='',
            routing_key='parsing_tasks',
            body=json.dumps(task_data),
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
            ))
        connection.close()
        logger.info(f"Published parsing task: {task_data}")
        return True
    except Exception as e:
        logger.error(f"Failed to publish parsing task: {e}")
        return False
