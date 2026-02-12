import asyncio
import json
import aio_pika
import os
from dotenv import load_dotenv

load_dotenv()

async def trigger_sync(site_key="mvideo"):
    # Use localhost for RabbitMQ since we run this script natively
    rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    database_url = os.getenv("DATABASE_URL").replace('postgresql+asyncpg://', 'postgresql://')

    
    import asyncpg
    conn = await asyncpg.connect(database_url)
    row = await conn.fetchrow("SELECT id, url FROM parsing_sources WHERE site_key = $1 LIMIT 1", site_key)

    await conn.close()
    
    if not row:
        print(f"Error: Source for {site_key} not found in database.")
        return

    connection = await aio_pika.connect_robust(rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        
        task = {
            "source_id": row['id'], 
            "site_key": site_key,
            "url": row['url'],
            "strategy": "discovery"
        }
        
        await channel.default_exchange.publish(
            aio_pika.Message(body=json.dumps(task).encode()),
            routing_key="parsing_tasks"
        )
        print(f" [x] Sent discovery task for {site_key} (ID: {row['id']})")

if __name__ == "__main__":
    import sys
    spider = sys.argv[1] if len(sys.argv) > 1 else "mvideo"
    asyncio.run(trigger_sync(spider))

