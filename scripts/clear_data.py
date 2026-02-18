
import asyncio
import os
os.environ["DATABASE_URL"] = "postgresql+asyncpg://giftyai_user:kG7pZ3vQ2mL9sT4xN8wC@localhost:5432/giftyai"

from app.db import get_db
from sqlalchemy import text

async def main():
    async for db in get_db():
        print("🚮 Clearing product-related tables...")
        # Order matters for foreign keys
        tables = ["product_embeddings", "parsing_runs", "products", "category_maps"]
        for table in tables:
            try:
                await db.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
                print(f"✅ Cleared {table}")
            except Exception as e:
                print(f"❌ Error clearing {table}: {e}")
        
        await db.commit()
        print("\n✨ Database cleared of products and history!")
        break

if __name__ == "__main__":
    asyncio.run(main())
