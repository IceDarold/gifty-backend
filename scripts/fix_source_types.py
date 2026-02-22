#!/usr/bin/env python3
"""
Script to fix parsing sources that are misconfigured.
Changes hub/discovery sources to list/deep for product scraping.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app.db import get_session_context
from app.repositories.parsing import ParsingRepository


async def main():
    print("Fixing source configurations...")
    
    async with get_session_context() as session:
        repo = ParsingRepository(session)
        
        # Get all sources
        sources = await repo.get_all_sources()
        
        fixed_count = 0
        for source in sources:
            # Skip mvideo (it's working)
            if source.site_key == "mvideo":
                continue
                
            # If it's a hub with discovery strategy, change to list/deep
            if source.type == "hub" and source.strategy == "discovery":
                print(f"\nFixing {source.site_key} (ID: {source.id}):")
                print(f"  URL: {source.url}")
                print(f"  Old: type={source.type}, strategy={source.strategy}")
                
                # Update to list/deep for product scraping
                await repo.update_source(source.id, {
                    "type": "list",
                    "strategy": "deep"
                })
                
                print(f"  New: type=list, strategy=deep")
                fixed_count += 1
        
        await session.commit()
        
        print(f"\n✅ Fixed {fixed_count} sources")
        print("\nNow when you click 'Run Deep', these sources will actually scrape products!")


if __name__ == "__main__":
    asyncio.run(main())
