from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.routes import router as auth_router
from routes.recommendations import router as recommendations_router
from app.config import get_settings
from app.redis_client import init_redis
from app.utils.errors import install_exception_handlers

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = await init_redis()
    try:
        yield
    finally:
        await app.state.redis.close()


app = FastAPI(title="Gifty API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(settings.frontend_base)],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

install_exception_handlers(app)
app.include_router(auth_router)
app.include_router(recommendations_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}

