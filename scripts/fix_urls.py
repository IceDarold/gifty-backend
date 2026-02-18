from app.db import SessionLocal
from app.models import ParsingSource
import asyncio

async def fix():
    async with SessionLocal() as db:
        from sqlalchemy import update
        
        # Update nashi_podarki URL
        stmt = update(ParsingSource).where(ParsingSource.site_key == "nashi_podarki").where(ParsingSource.type == "hub").values(
            url="https://nashipodarki.ru/catalog/podarki/"
        )
        await db.execute(stmt)
        await db.commit()
        print("Updated nashi_podarki URL")
        
        # Fix all other .placeholder URLs to have hyphens instead of underscores in domain
        from sqlalchemy import select
        stmt = select(ParsingSource).where(ParsingSource.url.like("%_%.placeholder"))
        res = await db.execute(stmt)
        sources = res.scalars().all()
        for s in sources:
            new_url = s.url.replace("_", "-")
            s.url = new_url
            print(f"Fixed URL for {s.site_key}: {new_url}")
        
        await db.commit()

if __name__ == "__main__":
    asyncio.run(fix())
