import asyncio
from app.db import SessionLocal
from app.models import Product
from sqlalchemy import select, func

async def check():
    async with SessionLocal() as session:
        site_key = "mvideo"
        stmt = select(func.count()).select_from(Product).where(Product.gift_id.like(f"{site_key}:%"))
        res = await session.execute(stmt)
        count = res.scalar()
        print(f"Query for '{site_key}:%' returned: {count}")
        
        # Exact match check
        stmt = select(func.count()).select_from(Product).where(Product.merchant == "М.Видео")
        res = await session.execute(stmt)
        print(f"Merchant 'М.Видео' count: {res.scalar()}")

if __name__ == "__main__":
    asyncio.run(check())
