from app.db import SessionLocal
from app.models import ParsingSource
from sqlalchemy import select, func
import asyncio

async def check():
    async with SessionLocal() as db:
        res = await db.execute(select(func.count(ParsingSource.id)))
        print(f"COUNT: {res.scalar()}")

if __name__ == "__main__":
    asyncio.run(check())
