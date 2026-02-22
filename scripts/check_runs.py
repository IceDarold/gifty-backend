from app.db import SessionLocal
from app.models import ParsingRun, ParsingSource
import asyncio

async def check():
    async with SessionLocal() as db:
        from sqlalchemy import select, func
        
        stmt = select(ParsingSource.id, ParsingSource.site_key).where(ParsingSource.site_key == "nashi_podarki")
        res = await db.execute(stmt)
        sources = res.all()
        print(f"DEBUG_SOURCES: {sources}")
        
        for s_id, s_key in sources:
            stmt = select(ParsingRun.items_new, ParsingRun.items_scraped, ParsingRun.created_at).where(ParsingRun.source_id == s_id).order_by(ParsingRun.created_at.desc()).limit(5)
            runs = (await db.execute(stmt)).all()
            print(f"DEBUG_RUNS for source {s_id}: {runs}")

if __name__ == "__main__":
    asyncio.run(check())
