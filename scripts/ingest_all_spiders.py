
import subprocess
import os
import sys
import time
import asyncio

# List of working spiders and example URLs (we will try to use DB URLs if possible)
SPIDERS = {
    "detmir": "https://www.detmir.ru/catalog/index/name/lego/",
    "inteltoys": "https://inteltoys.ru/catalog",
    "mrgeek": "https://mrgeek.ru/catalog/elektronika/",
    "vseigrushki": "https://vseigrushki.com/konstruktory/",
    "group_price": "https://groupprice.ru/categories/parfumeriya",
    "nashi_podarki": "https://nashipodarki.ru/catalog/matreshki/",
    "mvideo": "https://www.mvideo.ru/smartfony-i-svyaz-10",
    "letu": "https://www.letu.ru/browse/makiyazh",
    "pichshop": "https://pichshop.ru/catalog",
    "russian_legacy": "https://russianlegacy.com/winter-hats"
}

async def get_source_ids():
    """Fetch site_key -> source_id mapping from the database"""
    # Use localhost for native run
    os.environ["DATABASE_URL"] = os.getenv("DATABASE_URL", "postgresql+asyncpg://giftyai_user:kG7pZ3vQ2mL9sT4xN8wC@localhost:5432/giftyai").replace("@postgres", "@localhost")
    
    # Add project root to sys.path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.append(project_root)
        
    from app.db import get_db
    from app.models import ParsingSource
    from sqlalchemy import select
    
    mapping = {}
    try:
        async for db in get_db():
            stmt = select(ParsingSource.id, ParsingSource.site_key)
            result = await db.execute(stmt)
            for row in result.all():
                # Store the FIRST id found for each site_key
                if row[1] not in mapping:
                    mapping[row[1]] = row[0]
            break
    except Exception as e:
        print(f"⚠️ Warning: Could not fetch source IDs from DB: {e}")
        print("Scraping will proceed but ingestion might fail if API requires source_id.")
        
    return mapping

async def run_ingestion():
    print("🚀 Starting Production Ingestion for all Spiders...")
    
    source_ids = await get_source_ids()
    print(f"Found IDs for: {', '.join(source_ids.keys())}")
    print("-" * 60)

    # Set local API URL if not provided
    os.environ["CORE_API_URL"] = os.getenv("CORE_API_URL", "http://localhost:8000/internal/ingest-batch")
    os.environ["INTERNAL_API_TOKEN"] = os.getenv("INTERNAL_API_TOKEN", "25VwDZgr9PzYES4c3ZP2wPbp3")
    os.environ["SCRAPY_BATCH_SIZE"] = "5"
    
    # Change into services directory to ensure scrapy.cfg is found
    original_cwd = os.getcwd()
    services_dir = os.path.join(original_cwd, "services")
    
    if os.path.exists(services_dir):
        os.chdir(services_dir)
    else:
        print("Error: services/ directory not found.")
        return

    for spider, url in SPIDERS.items():
        source_id = source_ids.get(spider)
        if not source_id:
             print(f"⚠️  No source_id found for {spider}, skipping to avoid API errors.")
             continue

        print(f"\n🕷️  Running spider: {spider} (Source ID: {source_id})")
        print(f"    Target: {url}")
        
        # Construct command
        cmd = [
            "python3", "-m", "scrapy", "crawl", spider,
            "-a", f"url={url}",
            "-a", "strategy=deep",
            "-a", f"source_id={source_id}"
        ]
        
        limit = os.getenv("INGEST_LIMIT", "50")
        if limit != "0":
            cmd += ["-s", f"CLOSESPIDER_ITEMCOUNT={limit}"]

        env = os.environ.copy()
        env["PYTHONPATH"] = f"{original_cwd}/services:{original_cwd}"

        try:
            subprocess.run(cmd, check=True, env=env)
            print(f"✅ Spider {spider} finished successfully.")
        except subprocess.CalledProcessError as e:
            print(f"❌ Spider {spider} failed with exit code {e.returncode}")
        except Exception as e:
            print(f"🔥 Error running {spider}: {e}")

        print("-" * 40)

    os.chdir(original_cwd)
    print("\n✅ All ingestion tasks completed!")

if __name__ == "__main__":
    asyncio.run(run_ingestion())
