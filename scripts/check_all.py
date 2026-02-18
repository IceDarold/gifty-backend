from app.db import SessionLocal
from app.models import Product
import asyncio

async def check():
    async with SessionLocal() as db:
        from sqlalchemy import select, func
        
        stmt = select(func.count()).select_from(Product)
        res = await db.execute(stmt)
        print(f"DEBUG_TOTAL_PRODUCTS_IN_DB: {res.scalar()}")
        
        stmt = select(Product.gift_id).limit(10)
        res = await db.execute(stmt)
        for row in res.scalars():
            print(f"DEBUG_SAMPLE_GIFT_ID: {row}")

if __name__ == "__main__":
    asyncio.run(check())
