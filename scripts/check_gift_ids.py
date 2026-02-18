from app.db import SessionLocal
from app.models import Product
import asyncio

async def check():
    async with SessionLocal() as db:
        from sqlalchemy import select, func
        
        # Check ALL gift_ids and their prefix
        stmt = select(func.distinct(func.split_part(Product.gift_id, ':', 1)))
        res = await db.execute(stmt)
        print(f"DEBUG_UNIQUE_SITE_KEYS: {res.scalars().all()}")
        
        # Check nashi_podarki specifically
        stmt = select(func.count()).select_from(Product).where(Product.gift_id.like("nashi_podarki:%"))
        res = await db.execute(stmt)
        print(f"DEBUG_SITE_COUNT_RAW nashi_podarki: {res.scalar()}")

        # Check if they are inactive
        stmt = select(func.count()).select_from(Product).where(Product.gift_id.like("nashi_podarki:%")).where(Product.is_active.is_(False))
        res = await db.execute(stmt)
        print(f"DEBUG_INACTIVE_COUNT nashi_podarki: {res.scalar()}")

if __name__ == "__main__":
    asyncio.run(check())
