import pika
import json
import logging
import os
import subprocess
import httpx
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
INTERNAL_API_BASE_URL = os.getenv("CORE_API_URL", "http://api:8000/internal/ingest-batch").rsplit('/', 1)[0]
INTERNAL_API_TOKEN = os.getenv("INTERNAL_API_TOKEN", "default_internal_token")

def get_available_spiders():
    cwd = "."
    if os.path.exists("/app/scrapy.cfg"):
        cwd = "/app"
    elif os.path.exists("services/scrapy.cfg"):
        cwd = "services"
        
    try:
        result = subprocess.run(
            ["scrapy", "list"],
            cwd=cwd,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return [s.strip() for s in result.stdout.split('\n') if s.strip()]
    except Exception as e:
        logger.error(f"Error listing spiders: {e}")
    return []

# We'll refresh this or just check dynamically
AVAILABLE_SPIDERS = get_available_spiders()
logger.info(f"Available spiders: {AVAILABLE_SPIDERS}")

def sync_spiders_with_api():
    if not AVAILABLE_SPIDERS:
        return
    
    import time
    max_retries = 5
    for i in range(max_retries):
        try:
            url = f"{INTERNAL_API_BASE_URL}/sources/sync-spiders"
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    url, 
                    json={"available_spiders": AVAILABLE_SPIDERS},
                    headers={"X-Internal-Token": INTERNAL_API_TOKEN}
                )
                response.raise_for_status()
                logger.info("Spiders synchronized with API")
                break
        except Exception as e:
            logger.warning(f"Attempt {i+1}/{max_retries}: Error syncing spiders with API: {e}")
            time.sleep(5)
    else:
        logger.error("Failed to sync spiders after max retries")

# Run sync after a short delay to let API start
sync_spiders_with_api()

def report_error(source_id, error_msg):
    if not source_id:
        return
    try:
        url = f"{INTERNAL_API_BASE_URL}/sources/{source_id}/report-error"
        payload = {"error": error_msg, "is_broken": True}
        headers = {"X-Internal-Token": INTERNAL_API_TOKEN}
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            logger.info(f"Reported error for source_id {source_id}")
    except Exception as e:
        logger.error(f"Failed to report error: {e}")

def report_status(source_id, status):
    if not source_id: return
    try:
        url = f"{INTERNAL_API_BASE_URL}/sources/{source_id}/report-status"
        headers = {"X-Internal-Token": INTERNAL_API_TOKEN}
        with httpx.Client(timeout=10.0) as client:
            client.post(url, json={"status": status}, headers=headers)
    except Exception as e:
        logger.error(f"Failed to report status: {e}")

def report_logs(source_id, logs):
    if not source_id: return
    try:
        url = f"{INTERNAL_API_BASE_URL}/sources/{source_id}/report-logs"
        headers = {"X-Internal-Token": INTERNAL_API_TOKEN}
        with httpx.Client(timeout=10.0) as client:
            client.post(url, json={"logs": logs}, headers=headers)
    except Exception as e:
        logger.error(f"Failed to report logs: {e}")


def callback(ch, method, properties, body):
    global AVAILABLE_SPIDERS
    try:
        task = json.loads(body)
        logger.info(f"Received task: {task}")

        url = task.get("url")
        site_key = task.get("site_key")
        strategy = task.get("strategy", "deep")
        source_id = task.get("source_id")

        if site_key not in AVAILABLE_SPIDERS:
            # Try once more to refresh if not found (maybe a new spider was added without restart)
            refreshed_spiders = get_available_spiders()
            if site_key not in refreshed_spiders:
                logger.error(f"Unknown site_key: {site_key}")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
            else:
                AVAILABLE_SPIDERS = refreshed_spiders

        # Run scrapy in a separate process to avoid ReactorNotRestartable error
        cmd = [
            "scrapy", "crawl", site_key,
            "-a", f"url={url}",
            "-a", f"strategy={strategy}",
            "-a", f"source_id={source_id}"
        ]
        
        logger.info(f"Starting process: {' '.join(cmd)}")
        report_status(source_id, "running")
        
        # We assume the script is executed from the project root 
        # or we set the CWD to the directory containing scrapy.cfg
        # Try to find where scrapy.cfg is
        cwd = "."
        if os.path.exists("/app/scrapy.cfg"):
            cwd = "/app"
        elif os.path.exists("services/scrapy.cfg"):
            cwd = "services"
        
        result = subprocess.run(
            cmd, 
            cwd=cwd,
            capture_output=True,
            text=True
        )

        # Capture last 20 lines of logs
        log_output = (result.stderr or result.stdout or "")
        last_logs = "\n".join(log_output.splitlines()[-20:])
        report_logs(source_id, last_logs)

        if result.returncode == 0:
            report_status(source_id, "waiting")
            # Check if items were actually scraped
            if "'item_scraped_count':" not in result.stdout and "'item_scraped_count':" not in result.stderr:
                # If it's a deep crawl and no items, it might be broken or just empty
                if strategy == "deep":
                    logger.warning(f"No items scraped for {site_key}. Checking for errors...")
                    if "404 Not Found" in result.stderr or "404" in result.stdout:
                         report_error(source_id, "Broken: Start URL returned 404")
                    else:
                         # Just log it for now
                         logger.info(f"Task completed but 0 items scraped for {site_key}")

            logger.info(f"Completed task: {task}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        else:
            logger.error(f"Scrapy process failed with return code {result.returncode}")
            logger.error(f"STDOUT: {result.stdout}")
            logger.error(f"STDERR: {result.stderr}")
            
            # Report error and mark as broken
            error_msg = f"Scrapy exit code {result.returncode}. STDERR: {result.stderr[:500]}"
            report_error(source_id, error_msg)
            
            # Ack to avoid infinite loops if it's broken
            ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        logger.error(f"Error processing task: {e}")
        # For general code errors, we might want to retry, but let's report as well
        if 'source_id' in locals():
            report_error(source_id, f"Worker error: {str(e)}")
        ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()

    channel.queue_declare(queue='parsing_tasks', durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='parsing_tasks', on_message_callback=callback)

    # Start Prometheus metrics server
    from prometheus_client import start_http_server
    metrics_port = int(os.getenv("METRICS_PORT", "9410"))
    start_http_server(metrics_port)
    logger.info(f"Prometheus metrics server started on port {metrics_port}")

    logger.info("Worker waiting for tasks. To exit press CTRL+C")
    channel.start_consuming()

if __name__ == "__main__":
    main()
