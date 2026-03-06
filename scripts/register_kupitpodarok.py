import asyncio
import os
import sys

# Добавляем корневую папку в path для импорта app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config import get_settings
from app.repositories.parsing import ParsingRepository

async def register_kupitpodarok():
    settings = get_settings()
    # Используем URL из конфига, но заменяем host если нужно
    db_url = settings.database_url
    
    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        repo = ParsingRepository(session)
        
        spider_key = "kupitpodarok"
        source_url = "https://kupitpodarok.ru/catalog/neobychnye_podarki/"
        
        # Проверяем, существует ли уже
        existing = await repo.get_source_by_url(source_url)
        if existing:
            print(f"Source {source_url} already exists with ID {existing.id}")
            return
            
        data = {
            "url": source_url,
            "site_key": spider_key,
            "type": "hub",
            "strategy": "discovery",
            "priority": 70, # Высокий приоритет для нового источника
            "refresh_interval_hours": 24,
            "is_active": True,
            "status": "waiting",
            "config": {
                "name": "КупитьПодарок (наборы и впечатления)",
                "note": "Парсинг через window.catalog JSON"
            }
        }
        
        source = await repo.upsert_source(data)
        print(f"Successfully registered {spider_key} spider. Source ID: {source.id}")

if __name__ == "__main__":
    asyncio.run(register_kupitpodarok())
