from app.jobs.pg_ch_bootstrap import run_bootstrap
import asyncio

if __name__ == "__main__":
    asyncio.run(run_bootstrap())
