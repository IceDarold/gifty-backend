
import asyncio
import os
os.environ["DATABASE_URL"] = "postgresql+asyncpg://giftyai_user:kG7pZ3vQ2mL9sT4xN8wC@localhost:5432/giftyai"

from app.db import get_db
from app.models import ParsingRun
from sqlalchemy import select

async def main():
    async for db in get_db():
        stmt = select(ParsingRun).order_by(ParsingRun.created_at.desc()).limit(10)
        result = await db.execute(stmt)
        runs = result.scalars().all()
        
        print(f"{'Source ID':<10} | {'Status':<10} | {'New':<5} | {'Scraped':<7} | {'Created At'}")
        print("-" * 60)
        for run in runs:
            print(f"{run.source_id:<10} | {run.status:<10} | {run.items_new:<5} | {run.items_scraped:<7} | {run.created_at}")
        break

if __name__ == "__main__":
    asyncio.run(main())
