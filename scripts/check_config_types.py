from app.db import SessionLocal
from app.models import ParsingSource
from sqlalchemy import select
import asyncio

async def check():
    async with SessionLocal() as db:
        res = await db.execute(select(ParsingSource))
        sources = res.scalars().all()
        for s in sources:
            print(f"ID: {s.id}, Site: {s.site_key}, ConfigType: {type(s.config)}")

if __name__ == "__main__":
    asyncio.run(check())
