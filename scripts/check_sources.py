import asyncio
import os
import sys

# Add the project root to sys.path
sys.path.append(os.getcwd())

from app.db import SessionLocal
from app.models import ParsingSource
from sqlalchemy import select

async def check_sources():
    async with SessionLocal() as session:
        result = await session.execute(select(ParsingSource))
        sources = result.scalars().all()
        print(f"Total sources found: {len(sources)}")
        for i, s in enumerate(sources):
            print(f"{i+1}. {s.url} (ID: {s.id})")

if __name__ == "__main__":
    asyncio.run(check_sources())
