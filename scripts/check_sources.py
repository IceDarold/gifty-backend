
import asyncio
import os
os.environ["DATABASE_URL"] = "postgresql+asyncpg://giftyai_user:kG7pZ3vQ2mL9sT4xN8wC@localhost:5432/giftyai"

from app.db import get_db
from app.models import ParsingSource
from sqlalchemy import select

async def main():
    async for db in get_db():
        stmt = select(ParsingSource.id, ParsingSource.site_key, ParsingSource.type, ParsingSource.url)
        result = await db.execute(stmt)
        sources = result.all()
        for s in sources:
            print(f"ID: {s[0]}, Site: {s[1]}, Type: {s[2]}, URL: {s[3]}")
        break

if __name__ == "__main__":
    asyncio.run(main())
