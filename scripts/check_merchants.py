from app.db import SessionLocal
from app.models import Product
import asyncio

async def check():
    async with SessionLocal() as db:
        from sqlalchemy import select, func
        
        stmt = select(func.distinct(Product.merchant))
        res = await db.execute(stmt)
        merchants = res.scalars().all()
        print(f"DEBUG_ALL_MERCHANTS: {merchants}")
        
        stmt = select(func.distinct(Product.category))
        res = await db.execute(stmt)
        categories = res.scalars().all()
        print(f"DEBUG_ALL_CATEGORIES: {categories}")

if __name__ == "__main__":
    asyncio.run(check())
