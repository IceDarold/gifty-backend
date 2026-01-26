from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.routes import router as auth_router
from routes.recommendations import router as recommendations_router
from routes.internal import router as internal_router
from app.config import get_settings
from app.redis_client import init_redis
from app.utils.errors import install_exception_handlers
from app.services.embeddings import EmbeddingService

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize services
    app.state.redis = await init_redis()
    
    # Initialize Embedding Service (stub)
    app.state.embedding_service = EmbeddingService(model_name=settings.embedding_model)
    # No heavy loading here
    
    try:
        yield
    finally:
        await app.state.redis.close()


app = FastAPI(title="Gifty API", version="1.0.0", lifespan=lifespan)

origins = [o.strip() for o in settings.cors_origins.split(",")]
if str(settings.frontend_base) not in origins and "*" not in origins:
    origins.append(str(settings.frontend_base).rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

install_exception_handlers(app)
app.include_router(auth_router)
app.include_router(recommendations_router)
app.include_router(internal_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}

