from pydantic import BaseModel
from app.config import get_settings

settings = get_settings()

class RecommendationLogicConfig(BaseModel):
    # На сколько процентов можно превысить бюджет (0.1 = 10%)
    budget_margin_fraction: float = 0.1
    
    # Сколько товаров брать на каждый поисковый запрос в превью
    items_per_query: int = 4
    
    # Сколько всего запросов от модели обрабатывать для превью
    max_queries_for_preview: int = 3
    
    # Лимит кандидатов для реранкинга (на каждый запрос)
    rerank_candidate_limit: int = 15
    
    # Модели LLM
    model_fast: str = settings.anthropic_model_fast
    model_smart: str = settings.anthropic_model_smart
    
    # Модели эмбеддингов
    model_embedding: str = settings.embedding_model

# Создаем глобальный инстанс конфига
logic_config = RecommendationLogicConfig()
