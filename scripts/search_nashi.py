from app.db import SessionLocal
from app.models import Product
import asyncio

async def check():
    async with SessionLocal() as db:
        from sqlalchemy import select, func
        
        # Get all site_keys (prefixes)
        stmt = select(func.distinct(func.split_part(Product.gift_id, ':', 1)))
        res = await db.execute(stmt)
        keys = res.scalars().all()
        print(f"DEBUG_ALL_SITE_KEYS: {keys}")
        
        # Look for ANYTHING related to nashi
        stmt = select(Product.gift_id).where(Product.gift_id.ilike("%nashi%")).limit(5)
        res = await db.execute(stmt)
        for row in res.scalars():
            print(f"DEBUG_NASHI_GIFT_ID: {row}")

if __name__ == "__main__":
    asyncio.run(check())
