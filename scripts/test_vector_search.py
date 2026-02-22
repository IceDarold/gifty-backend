import asyncio
import sys
from pathlib import Path

# Add project root to python path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from app.db import get_session_context
from app.repositories.catalog import PostgresCatalogRepository
from app.services.embeddings import EmbeddingService

async def main():
    query = "funny developer coffee"
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])

    print(f"Query: '{query}'")
    print("Loading model and generating query embedding...")
    
    # Init service and repo
    embedding_service = EmbeddingService() # Defaults to BAAI/bge-m3
    
    # Generate embedding
    embeddings_list = embedding_service.embed_batch([query])
    query_vector = embeddings_list[0]
    
    print(f"Vector generated (len={len(query_vector)}). Searching DB...")
    
    async with get_session_context() as session:
        repo = PostgresCatalogRepository(session)
        products = await repo.search_similar_products(query_vector, limit=5)
        
        print(f"\nTop {len(products)} results:")
        for i, p in enumerate(products, 1):
            print(f"{i}. {p.title} (ID: {p.gift_id})")
            print(f"   Merchant: {p.merchant}")
            print(f"   URL: {p.product_url}")
            print("-" * 50)

if __name__ == "__main__":
    asyncio.run(main())
