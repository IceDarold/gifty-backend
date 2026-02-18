
import asyncio
import os
os.environ["DATABASE_URL"] = "postgresql+asyncpg://giftyai_user:kG7pZ3vQ2mL9sT4xN8wC@localhost:5432/giftyai"

from app.db import get_db
from app.models import Product
from sqlalchemy import select, func

async def main():
    async for db in get_db():
        stmt = select(func.count(Product.gift_id))
        result = await db.execute(stmt)
        print(f"Total Products: {result.scalar()}")
        
        stmt = select(Product.merchant, func.count()).group_by(Product.merchant)
        result = await db.execute(stmt)
        for row in result:
            print(f"Merchant: {row[0]}, Count: {row[1]}")
        break

if __name__ == "__main__":
    asyncio.run(main())
