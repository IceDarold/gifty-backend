
import asyncio
import os
os.environ["DATABASE_URL"] = "postgresql+asyncpg://giftyai_user:kG7pZ3vQ2mL9sT4xN8wC@localhost:5432/giftyai"

from app.db import get_db
from app.models import Product
from sqlalchemy import select, func

async def main():
    async for db in get_db():
        # Count by merchant
        stmt = select(Product.merchant, func.count(Product.gift_id), func.max(Product.updated_at))\
               .group_by(Product.merchant)\
               .order_by(func.count(Product.gift_id).desc())
        result = await db.execute(stmt)
        rows = result.all()
        
        print(f"{'Merchant':<20} | {'Count':<10} | {'Last Updated'}")
        print("-" * 50)
        for row in rows:
            print(f"{str(row[0]):<20} | {row[1]:<10} | {row[2]}")
        break

if __name__ == "__main__":
    asyncio.run(main())
