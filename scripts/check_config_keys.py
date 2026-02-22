from app.db import SessionLocal
from app.models import ParsingSource
import asyncio

async def check():
    async with SessionLocal() as db:
        from sqlalchemy import select
        stmt = select(ParsingSource)
        res = await db.execute(stmt)
        for s in res.scalars():
            print(f"ID: {s.id}, Site: {s.site_key}, Config: {s.config}")

if __name__ == "__main__":
    asyncio.run(check())
