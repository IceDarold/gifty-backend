# Система конфигурации (Tiered Config)

В Gifty используется разделение настроек на два уровня для обеспечения безопасности, гибкости и удобства разработки.

---

## Уровень 1: Инфраструктура и Секреты (`.env`)

Этот уровень предназначен для данных, которые **не должны попадать в Git** и зависят от конкретной среды (dev, staging, prod).

**Файлы:** `.env`, `.env.prod`.

**Что здесь хранится:**
- **Секреты:** API ключи (Anthropic, RunPod, Google и т.д.).
- **Доступы к БД:** `DATABASE_URL`, `REDIS_URL`, `RABBITMQ_URL`.
- **Флаги окружения:** `DEBUG`, `ENV`.

**Доступ в коде:**
```python
from app.config import get_settings
settings = get_settings()
print(settings.anthropic_api_key)
```

---

## Уровень 2: Бизнес-логика и модели (`configs/logic.yaml`)

Этот уровень предназначен для настроек, которые определяют **поведение приложения**. Эти настройки одинаковы для всех сред и **должны быть в Git**.

**Файлы:** `configs/logic.yaml`.

**Что здесь хранится:**
- **Выбор провайдера:** Какую LLM или сервис эмбеддингов использовать по умолчанию.
- **Модели:** Названия конкретных моделей (`claude-3-haiku`, `bge-m3`).
- **Алгоритмы:** Пороги (thresholds), лимиты выдачи, коэффициенты бюджета.
- **Включение фич:** Feature flags.

**Структура `logic.yaml`:**
```yaml
recommendation:
  budget_margin_fraction: 0.1 # На сколько можно превысить бюджет
  items_per_query: 4          # Кол-во товаров на один запрос

llm:
  default_provider: "anthropic"
  embedding_provider: "runpod"
  model_fast: "claude-3-haiku-20240307"
```

**Доступ в коде:**
```python
from app.core.logic_config import logic_config

# Доступ к сгруппированным настройкам
print(logic_config.llm.default_provider)
print(logic_config.recommendation.items_per_query)

# Обратная совместимость (короткие алиасы)
print(logic_config.model_fast)
```

---

## Почему это удобно?

1.  **Безопасность:** Вы случайно не закоммитите API ключ в репозиторий, так как они отделены от настроек моделей.
2.  **Горячая замена:** Вы можете переключить провайдера LLM (например, с Anthropic на Groq или Gemini) простым изменением в YAML-файле.
3.  **Читаемость:** Все параметры алгоритма рекомендаций собраны в одном наглядном файле, а не разбросаны по длинному списку переменных окружения.
4.  **Типизация:** Благодаря Pydantic, если вы совершите опечатку в типе данных (например, напишете строку вместо числа) в YAML, приложение выдаст понятную ошибку при старте.

---

## Проверка интеграции (Smoke Tests)

Чтобы убедиться, что выбранный провайдер настроен верно и ключи работают, используйте специальные smoke-тесты:

```bash
# Проверить текущий настроенный LLM и Embedding провайдер
pytest tests/llm/test_providers_smoke.py -v -s
```

Вы можете проверять разных провайдеров, переопределяя переменные прямо в команде:

```bash
# Проверка Together AI для LLM
LLM_PROVIDER=together TOGETHER_API_KEY=xxx pytest tests/llm/test_providers_smoke.py

# Проверка RunPod для эмбеддингов
RUNPOD_API_KEY=xxx RUNPOD_ENDPOINT_ID=yyy pytest tests/llm/test_providers_smoke.py
```

Результаты тестов покажут, удалось ли получить ответ от API и корректны ли форматы данных.
