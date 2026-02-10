from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.routes import router as auth_router
from routes.recommendations import router as recommendations_router
from routes.internal import router as internal_router
from routes.analytics import router as analytics_router
from routes.public import router as public_router
from app.routes.integrations import router as integrations_router
from routes.weeek import router as weeek_router
from app.config import get_settings
from app.redis_client import init_redis
from app.utils.errors import install_exception_handlers
from app.services.embeddings import EmbeddingService
from prometheus_fastapi_instrumentator import Instrumentator

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


from scalar_fastapi import get_scalar_api_reference

app = FastAPI(
    title="Gifty Core API", 
    description="""
## Gifty: Умная система подбора подарков 🎁

Эта документация описывает API основного бэкенда Gifty. Система построена на базе микросервисной архитектуры и использует современные методы машинного обучения для обеспечения качественных рекомендаций.

### Архитектура системы:
1.  **Парсинг (Scrapers)**: Отдельные сервисы на базе Scrapy собирают актуальные данные о товарах с различных площадок (MrGeek и др.).
2.  **Очередь задач (RabbitMQ)**: Обеспечивает асинхронную передачу задач на парсинг и прием результатов.
3.  **Core API**: Настоящий сервис, который управляет базой данных, пользователями и бизнес-логикой.
4.  **AI Intelligence**: Внешний сервис (`api.giftyai.ru`), отвечающий за NLP-анализ, скоринг "подарочности" и автоматическую классификацию категорий.
5.  **Векторный поиск**: Реализован на базе `pgvector` в PostgreSQL. Позволяет находить подарки по смысловому описанию, а не просто по ключевым словам.

### Основные разделы API:
*   **Recommendations**: Публичные эндпоинты для получения подборок подарков на основе анкет.
*   **Auth**: Управление пользователями и OAuth2 авторизация (Google, Yandex, VK).
*   **Internal**: Технические эндпоинты для взаимодействия с парсерами и воркерами (требуют `X-Internal-Token`).
    """,
    summary="Центральный узел экосистемы Gifty",
    version="1.0.0", 
    lifespan=lifespan,
    docs_url=None, 
    redoc_url=None
)

@app.get("/docs", include_in_schema=False)
async def scalar_html():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title=app.title,
    )

frontend_origin = str(settings.frontend_base).rstrip("/")

# CORS configuration
origins = [
    frontend_origin,
    "https://giftyai.ru",
    "https://analytics.giftyai.ru",
    "https://aistudio.google.com",
    "http://localhost:5173",
    "http://localhost:8001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

install_exception_handlers(app)
app.include_router(auth_router)
app.include_router(recommendations_router)
app.include_router(internal_router)
app.include_router(analytics_router)
app.include_router(integrations_router)
app.include_router(public_router)
app.include_router(weeek_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


Instrumentator().instrument(app).expose(app)

