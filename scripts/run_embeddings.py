import asyncio
import logging
import sys
from pathlib import Path

# Add project root to python path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from app.jobs.embeddings import process_embeddings_job

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

async def main():
    print("Starting manual embedding generation...")
    # Process in batches, maybe limited count for testing or run until exhaustion
    await process_embeddings_job(batch_size=32, limit_total=None)
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
