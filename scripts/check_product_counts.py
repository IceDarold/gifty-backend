import asyncio
from app.db import SessionLocal
from app.models import Product
from sqlalchemy import select, func

async def check():
    async with SessionLocal() as session:
        # Check total
        res = await session.execute(select(func.count()).select_from(Product))
        print(f"Total Products in DB: {res.scalar()}")
        
        # Breakdown by site_key (prefix of gift_id)
        # In SQL: split_part(gift_id, ':', 1)
        res = await session.execute(
            select(
                func.split_part(Product.gift_id, ':', 1).label("site"),
                func.count()
            ).group_by("site")
        )
        print("\nBreakdown by site_key:")
        for site, count in res.all():
            print(f"- {site}: {count} items")

if __name__ == "__main__":
    asyncio.run(check())
