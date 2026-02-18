from app.db import SessionLocal
from app.repositories.parsing import ParsingRepository
from app.schemas.parsing import ParsingSourceSchema
import asyncio

async def test():
    async with SessionLocal() as db:
        repo = ParsingRepository(db)
        sources = await repo.get_all_sources()
        result = []
        for source in sources:
            schema_data = ParsingSourceSchema.model_validate(source)
            cat_name = source.config.get("discovery_name")
            schema_data.total_items = await repo.get_products_count(
                site_key=source.site_key, 
                category=cat_name if source.type != "hub" else None
            )
            result.append(schema_data)
            print(f"Source {source.id}: total_items={schema_data.total_items}")
        print("SUCCESS")

if __name__ == "__main__":
    asyncio.run(test())
