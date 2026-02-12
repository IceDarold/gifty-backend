import asyncio
import os
from datetime import datetime, timedelta
import random
from sqlalchemy import select
from app.db import SessionLocal
from app.models import ParsingSource, ParsingRun
from dotenv import load_dotenv

load_dotenv()

async def seed_stats():
    async with SessionLocal() as session:
        # Get all sources
        stmt = select(ParsingSource)
        result = await session.execute(stmt)
        sources = result.scalars().all()
        
        if not sources:
            print("No sources found to seed stats for.")
            return

        print(f"Seeding stats for {len(sources)} sources...")
        
        for source in sources:
            # Create a few runs for each source in the last 7 days
            for i in range(5):
                run_date = datetime.now() - timedelta(days=i, hours=random.randint(0, 23))
                items_scraped = random.randint(50, 200)
                items_new = random.randint(5, 50)
                
                run = ParsingRun(
                    source_id=source.id,
                    status="completed",
                    items_scraped=items_scraped,
                    items_new=items_new,
                    duration_seconds=float(random.randint(30, 300)),
                    created_at=run_date
                )

                session.add(run)
        
        await session.commit()
        print("Scraping stats seeded successfully!")

if __name__ == "__main__":
    asyncio.run(seed_stats())
