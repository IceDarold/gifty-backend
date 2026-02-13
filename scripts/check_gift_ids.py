import asyncio
from app.db import SessionLocal
from app.models import Product
from sqlalchemy import select

async def check():
    async with SessionLocal() as session:
        res = await session.execute(select(Product.gift_id, Product.merchant).limit(5))
        for row in res.all():
            print(f"GiftID: {row.gift_id} | Merchant: {row.merchant}")

if __name__ == "__main__":
    asyncio.run(check())
