import asyncio
import json
import logging
import os
import subprocess
import httpx
import aio_pika
import redis.asyncio as redis
import psutil
import socket
import signal
from datetime import datetime
from prometheus_client import start_http_server, Counter, Gauge

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ScraperWorker")

# Environment variables
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
INTERNAL_API_BASE_URL = os.getenv("CORE_API_URL", "http://api:8000/internal/ingest-batch").rsplit('/', 1)[0]
INTERNAL_API_TOKEN = os.getenv("INTERNAL_API_TOKEN", "default_internal_token")
MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", "4"))
METRICS_PORT = int(os.getenv("METRICS_PORT", "9410"))
SUBPROCESS_TIMEOUT = int(os.getenv("SUBPROCESS_TIMEOUT", "3600")) # 1 hour default
MEMORY_THRESHOLD_PCT = 85.0

# Metrics
TASKS_PROCESSED = Counter('scraper_tasks_total', 'Total tasks processed', ['site_key', 'status'])
CONCURRENT_TASKS = Gauge('scraper_concurrent_tasks', 'Number of tasks currently running')

class ScraperWorker:
    def __init__(self):
        self.available_spiders = []
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
        self.hostname = socket.gethostname()
        self.redis_client = None
        self.is_running = True
        self.active_processes = {} # {source_id: process}

    def get_available_spiders(self):
        """Discovers available Scrapy spiders."""
        cwd = "/app" if os.path.exists("/app/scrapy.cfg") else "services" if os.path.exists("services/scrapy.cfg") else "."
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

    async def report_api(self, endpoint, payload):
        """Sends status/error reports to the Core API."""
        url = f"{INTERNAL_API_BASE_URL}/{endpoint}"
        headers = {"X-Internal-Token": INTERNAL_API_TOKEN}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Failed to report to API ({endpoint}): {e}")
            return False

    async def heartbeat_loop(self):
        """Periodically records worker health in Redis."""
        logger.info("Heartbeat loop started.")
        while self.is_running:
            try:
                mem = psutil.virtual_memory()
                heartbeat_data = {
                    "hostname": self.hostname,
                    "last_seen": datetime.utcnow().isoformat(),
                    "status": "online",
                    "concurrent_tasks": CONCURRENT_TASKS._value.get(),
                    "ram_usage_pct": mem.percent,
                    "pid": os.getpid()
                }
                await self.redis_client.set(
                    f"worker_heartbeat:{self.hostname}",
                    json.dumps(heartbeat_data),
                    ex=60
                )
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
            await asyncio.sleep(30)

    async def sync_spiders(self):
        """Registers available spiders with the Core API."""
        self.available_spiders = self.get_available_spiders()
        logger.info(f"Available spiders: {self.available_spiders}")
        if self.available_spiders:
            await self.report_api("sources/sync-spiders", {"available_spiders": self.available_spiders})

    async def run_spider(self, task):
        """Executes a single Scrapy crawl in a subprocess with streaming logs."""
        async with self.semaphore:
            # Check resource constraints before starting
            mem = psutil.virtual_memory()
            if mem.percent > MEMORY_THRESHOLD_PCT:
                logger.warning(f"Memory usage high ({mem.percent}%). Delaying task {task.get('source_id')}")
                # We return the task to the queue (nack) or wait? 
                # Let's wait a bit and retry check
                while mem.percent > MEMORY_THRESHOLD_PCT:
                    await asyncio.sleep(30)
                    mem = psutil.virtual_memory()

            CONCURRENT_TASKS.inc()
            source_id = task.get("source_id")
            site_key = task.get("site_key")
            url = task.get("url")
            strategy = task.get("strategy", "deep")

            logger.info(f"Starting spider: {site_key} for {url} (ID: {source_id})")
            await self.report_api(f"sources/{source_id}/report-status", {"status": "running"})

            cwd = "/app" if os.path.exists("/app/scrapy.cfg") else "services" if os.path.exists("services/scrapy.cfg") else "."
            cmd = [
                "scrapy", "crawl", site_key,
                "-a", f"url={url}",
                "-a", f"strategy={strategy}",
                "-a", f"source_id={source_id}"
            ]

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd
                )
                self.active_processes[source_id] = process

                # Real-time log capture (last N lines)
                log_buffer = []
                async def read_stream(stream, is_stderr=False):
                    while True:
                        line = await stream.readline()
                        if line:
                            decoded = line.decode().strip()
                            if decoded:
                                log_buffer.append(decoded)
                                if len(log_buffer) > 50: log_buffer.pop(0)
                        else:
                            break

                log_task = asyncio.create_task(read_stream(process.stderr, True))
                
                try:
                    await asyncio.wait_for(process.wait(), timeout=SUBPROCESS_TIMEOUT)
                except asyncio.TimeoutError:
                    logger.error(f"Spider {site_key} timed out after {SUBPROCESS_TIMEOUT}s. Killing...")
                    process.kill()
                    await self.report_api(f"sources/{source_id}/report-error", {"error": "Subprocess timeout", "is_broken": False})
                
                await log_task
                
                last_logs = "\n".join(log_buffer)
                await self.report_api(f"sources/{source_id}/report-logs", {"logs": last_logs})

                if process.returncode == 0:
                    logger.info(f"Spider {site_key} completed successfully.")
                    await self.report_api(f"sources/{source_id}/report-status", {"status": "waiting"})
                    TASKS_PROCESSED.labels(site_key=site_key, status='success').inc()
                else:
                    err_hint = log_buffer[-1] if log_buffer else "Unknown error"
                    error_msg = f"Scrapy exit code {process.returncode}. Last line: {err_hint}"
                    logger.error(f"Spider {site_key} failed: {error_msg}")
                    await self.report_api(f"sources/{source_id}/report-error", {"error": error_msg, "is_broken": False})
                    TASKS_PROCESSED.labels(site_key=site_key, status='error').inc()

            except Exception as e:
                logger.error(f"Error running subprocess for {site_key}: {e}")
                await self.report_api(f"sources/{source_id}/report-error", {"error": str(e), "is_broken": False})
            finally:
                self.active_processes.pop(source_id, None)
                CONCURRENT_TASKS.dec()

    async def process_message(self, message: aio_pika.IncomingMessage):
        """Callback for incoming RabbitMQ messages."""
        async with message.process():
            try:
                task = json.loads(message.body.decode())
                asyncio.create_task(self.run_spider(task))
            except Exception as e:
                logger.error(f"Error decoding task message: {e}")

    async def shutdown(self, sig=None):
        """Cleanup on termination."""
        if sig:
            logger.info(f"Received exit signal {sig.name}...")
        self.is_running = False
        
        if self.active_processes:
            logger.info(f"Killing {len(self.active_processes)} active spiders...")
            for pid, p in self.active_processes.items():
                try:
                    p.terminate()
                except:
                    pass
                    
        if self.redis_client:
            await self.redis_client.close()
        logger.info("Worker shutdown complete.")

    async def run(self):
        """Starts the worker loop."""
        # 0. Setup Signal Handlers
        loop = asyncio.get_running_loop()
        for s in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(
                s, lambda s=s: asyncio.create_task(self.shutdown(s))
            )

        # 1. Start metrics server
        start_http_server(METRICS_PORT)
        logger.info(f"Metrics server started on port {METRICS_PORT}")

        # 2. Setup Redis and initial spiders sync
        self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        await self.sync_spiders()

        # 3. Start heartbeat
        asyncio.create_task(self.heartbeat_loop())

        # 4. Connect to RabbitMQ
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        async with connection:
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=MAX_CONCURRENT_TASKS * 2)
            
            queue = await channel.declare_queue("parsing_tasks", durable=True)
            logger.info(f"Worker connected. Waiting for tasks (Concurrency: {MAX_CONCURRENT_TASKS})...")
            
            await queue.consume(self.process_message)
            
            while self.is_running:
                await asyncio.sleep(1)

if __name__ == "__main__":
    worker = ScraperWorker()
    try:
        asyncio.run(worker.run())
    except (KeyboardInterrupt, SystemExit):
        pass
