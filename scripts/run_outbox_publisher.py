from app.jobs.outbox_publisher import run_outbox_publisher_loop
import asyncio

if __name__ == "__main__":
    asyncio.run(run_outbox_publisher_loop())
