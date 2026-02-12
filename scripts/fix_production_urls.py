import asyncio
import os
from sqlalchemy import update
from app.db import SessionLocal
from app.models import ParsingSource
from dotenv import load_dotenv

load_dotenv()

REAL_URLS = {
    "detmir": "https://www.detmir.ru/catalog/index/name/smartfony-i-svyaz-10/smartfony-205",
    "mvideo": "https://www.mvideo.ru/smartfony-i-svyaz-10/smartfony-205",
    "goldapple": "https://goldapple.ru/parfjumerija",
    "letu": "https://www.letu.ru/browse/parfyumeriya",
    "kassir": "https://msk.kassir.ru/category/teatr",
    "mrgeek": "https://mrgeek.ru/category/podarki/",
    "inteltoys": "https://inteltoys.ru/catalog/nastolnye-igry/",
}

async def fix_urls():
    async with SessionLocal() as session:
        print("Updating source URLs to real ones...")
        for site_key, url in REAL_URLS.items():
            stmt = update(ParsingSource).where(ParsingSource.site_key == site_key).values(url=url, is_active=True)
            await session.execute(stmt)
        
        await session.commit()
        print("✅ URLs updated successfully.")

if __name__ == "__main__":
    asyncio.run(fix_urls())
