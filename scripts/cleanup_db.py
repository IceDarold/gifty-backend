import asyncio
from app.db import SessionLocal
from app.models import ParsingSource
from sqlalchemy import update

async def cleanup_site_keys():
    async with SessionLocal() as session:
        # Map old/wrong keys to new correct ones
        mapping = {
            "goldapple": "goldenapple",
            "groupprice": "group_price",
            "nashipodarki": "nashi_podarki"
        }
        
        for old_key, new_key in mapping.items():
            print(f"Updating {old_key} -> {new_key}...")
            stmt = update(ParsingSource).where(ParsingSource.site_key == old_key).values(site_key=new_key)
            await session.execute(stmt)
        
        await session.commit()
        print("✅ Database cleanup complete.")

if __name__ == "__main__":
    asyncio.run(cleanup_site_keys())
