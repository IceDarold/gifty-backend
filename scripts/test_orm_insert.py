import asyncio
import sys
import uuid
from pathlib import Path
from datetime import datetime

# Add project root to python path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from app.db import get_session_context
from app.models import Product, ProductEmbedding
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select

async def main():
    print("Testing ORM insert...")
    gift_id = f"test:{uuid.uuid4()}"
    
    async with get_session_context() as session:
        # 1. Create a dummy product (required for FK)
        print(f"Creating test product {gift_id}...")
        product = Product(
            gift_id=gift_id,
            title="Test Product",
            product_url="http://test.com",
            is_active=True,
            content_hash="hash123"
        )
        session.add(product)
        await session.commit()
        
    async with get_session_context() as session:
        # 2. Try inserting embedding via ORM Upsert logic matching Repository
        print("Inserting embedding via ORM Upsert...")
        
        embedding_data = {
            "gift_id": gift_id,
            "model_name": "test_model",
            "model_version": "1.0",
            "dim": 3,
            "embedding": [0.1, 0.2, 0.3], # Using 3 dims for test, hope DB allows if we created it as 1024? 
            # WAIT: DB creation uses 1024. If we insert 3 floats into vector(1024), Postgres will error.
            # We must use 1024 floats.
            "content_hash": "hash123"
        }
        
        # Generate dummy 1024 vector
        embedding_data["embedding"] = [0.1] * 1024
        
        stmt = insert(ProductEmbedding).values([embedding_data])
        
        update_dict = {
            "embedding": stmt.excluded.embedding,
            "content_hash": stmt.excluded.content_hash,
            "updated_at": datetime.now(),
        }

        stmt = stmt.on_conflict_do_update(
            constraint="pk_product_embeddings",
            set_=update_dict
        )
        
        try:
            await session.execute(stmt)
            await session.commit()
            print("ORM Upsert successful.")
        except Exception as e:
            print(f"ORM Upsert failed: {e}")
            
    # Cleanup
    print("Cleaning up...")
    async with get_session_context() as session:
        p = await session.get(Product, gift_id)
        if p:
            await session.delete(p)
            await session.commit()

if __name__ == "__main__":
    asyncio.run(main())
