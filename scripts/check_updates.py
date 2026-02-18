
import asyncio
import os
os.environ["DATABASE_URL"] = "postgresql+asyncpg://giftyai_user:kG7pZ3vQ2mL9sT4xN8wC@localhost:5432/giftyai"

from app.db import get_db
from app.models import Product
from sqlalchemy import select

async def main():
    async for db in get_db():
        # Get the 5 most recently updated products
        stmt = select(Product.merchant, Product.title, Product.updated_at)\
               .order_by(Product.updated_at.desc())\
               .limit(5)
        result = await db.execute(stmt)
        rows = result.all()
        
        print(f"{'Merchant':<15} | {'Title':<40} | {'Updated At'}")
        print("-" * 80)
        for row in rows:
            print(f"{str(row[0]):<15} | {str(row[1])[:40]:<40} | {row[2]}")
        break

if __name__ == "__main__":
    asyncio.run(main())
