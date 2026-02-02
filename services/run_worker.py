import pika
import json
import logging
import os
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from gifty_scraper.spiders.mrgeek import MrGeekSpider
from gifty_scraper.spiders.group_price import GroupPriceSpider
from gifty_scraper.spiders.nashi_podarki import NashiPodarkiSpider
from gifty_scraper.spiders.detmir import DetmirSpider
from gifty_scraper.spiders.inteltoys import IntelToysSpider
from gifty_scraper.spiders.vseigrushki import VseIgrushkiSpider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

SPIDERS = {
    "mrgeek": MrGeekSpider,
    "groupprice": GroupPriceSpider,
    "nashipodarki": NashiPodarkiSpider,
    "detmir": DetmirSpider,
    "inteltoys": IntelToysSpider,
    "vseigrushki": VseIgrushkiSpider
}

def callback(ch, method, properties, body):
    try:
        task = json.loads(body)
        logger.info(f"Received task: {task}")

        url = task.get("url")
        site_key = task.get("site_key")
        strategy = task.get("strategy", "deep")
        source_id = task.get("source_id")

        if site_key not in SPIDERS:
            logger.error(f"Unknown site_key: {site_key}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        spider_cls = SPIDERS[site_key]
        
        # In a real production environment, we might use a separate process 
        # for each crawl to prevent memory leaks or reactor issues.
        # Here is a simplified example.
        process = CrawlerProcess(get_project_settings())
        process.crawl(spider_cls, url=url, strategy=strategy, source_id=source_id)
        process.start() # Note: this blocks. In production better use separate processes.

        logger.info(f"Completed task: {task}")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        logger.error(f"Error processing task: {e}")
        # Depending on error, we might reject or requeue
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

def main():
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()

    channel.queue_declare(queue='parsing_tasks', durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='parsing_tasks', on_message_callback=callback)

    logger.info("Worker waiting for tasks. To exit press CTRL+C")
    channel.start_consuming()

if __name__ == "__main__":
    main()
