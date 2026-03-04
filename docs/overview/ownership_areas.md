# Ownership Areas (2 Domains)

Этот документ нужен, чтобы **делегировать полную ответственность** за крупные части проекта новым сильным разработчикам.
Мы делим проект не по сервисам, а по **outcome** (качество, скорость, надежность и UX).

---

## Domain A: Parsing Platform

**Миссия:** обеспечить стабильный и управляемый поток данных *категория → очередь → run → ingestion → корректные данные в БД*.

### Зона ответственности
- Очередь и исполнение: RabbitMQ, workers, scheduler, retries/backoff, rate limiting, backpressure.
- Качество и инварианты данных: схемы, миграции, дедупликация, консистентность.
- Наблюдаемость: метрики, логирование, диагностика, авто-ремедиация (например auto-disable broken).
- Интеграции парсинга: scrapy pipeline → `api/v1/internal/ingest-batch`.

### What “Done” means
- Если в очереди есть задачи, worker не “idle” без причины (есть понятный диагноз).
- Run не может быть `completed`, если ingestion фактически упал (ошибка в логах/статусах корректно отражена).
- После повторного запуска категории система корректно дописывает происхождение товара (category links).

### Основные сущности (DB)
- `parsing_hubs`
- `discovered_categories`
- `parsing_sources`
- `parsing_runs`
- `product_category_links` (откуда товар был спарсен на сайте)
- `merchants` (метаданные магазинов; key = `site_key`)
- RabbitMQ queue: `parsing_tasks` (source of truth для “In queue”)

### Основные API точки (internal)
- `/api/v1/internal/ops/*` (Operations)
- `/api/v1/internal/queues/*` (RabbitMQ visibility)
- `/api/v1/internal/ingest-batch` (ingestion)

### KPI / SLO (пример)
- Success rate runs (%)
- Queue lag (ready/unacked, время ожидания)
- Throughput (new products/min, total products/min)
- MTTR: время от ошибки до восстановления
- Data quality: доля товаров без `product_category_links` после повторных прогонов

### Простор для исследований/улучшений
- Планирование: per-site квоты, приоритеты, “fair scheduling”.
- “Circuit breakers” на магазины/домены, quarantine очереди.
- Автоматическая классификация ошибок (network/ban/selector/ingest/db).

---

## Domain B: Operations & Admin UX

**Миссия:** сделать Operations Center “рабочим местом оператора” — быстро, понятно, realtime, без лишних запросов.

### Зона ответственности
- UX и workflow: как человек управляет парсерами/категориями/очередью и понимает статус.
- Realtime: SSE, версии snapshot’ов, минимизация polling.
- Понятная визуализация ошибок: 500/403/timeout, retry, лимит попыток.
- Global Catalog UX: поиск/пагинация, отображение scraped category, “n new items” уведомления.
- Runtime settings: интервалы обновлений, performance knobs.

### What “Done” means
- UI не делает “мегабайтные” запросы в цикле без причины.
- В момент ошибок API пользователь видит понятную причину и кнопку retry (не бесконечные запросы).
- Все long-running действия имеют feedback: pending → success/error + результат.

### Основные интерфейсы
- `apps/admin-tma` (Next.js / TMA)
- Internal API contracts (особенно `/api/v1/internal/ops/*`, `/api/v1/internal/products`, `/api/v1/internal/merchants`)
- SSE: `/api/v1/internal/ops/stream`

### KPI / SLO (пример)
- Time-to-action: открыть → запустить discovery/run (сек)
- UI update latency после события (сек)
- Кол-во запросов к API на пользователя (мин)
- Crash-free sessions / отсутствие hydration ошибок

### Простор для исследований/улучшений
- “Compute once, serve many” для аналитики (snapshots + versioning + SSE invalidation).
- Дизайн-система компонентов (cards, modals, tables, toasts, loading states).
- “Operator experience”: bulk actions, keyboard shortcuts, audit trail.

---

## Границы доменов (чтобы не было серых зон)

**Parsing Platform owner** отвечает за:
- корректность и финальный статус run’ов
- очереди, воркеры, scheduler
- модели/таблицы парсинга и ingestion

**Operations/Admin owner** отвечает за:
- то, как эти состояния и действия представлены в UI
- производительность фронта и “шум” запросов
- контракт ответов API, который нужен UI (additive changes и совместимость)

Пересечение допускается, но правило простое:
- если это *про “что правда в системе”* — Domain A,
- если это *про “как человек это видит/контролирует”* — Domain B.

---

## Ритуалы и управление ответственностью

- Каждый домен имеет “owner” (1 человек) и “backup” (второй).
- Раз в неделю 30 минут: *что сломано, что ускорили, что автоматизировали*.
- Любые изменения в своем домене owner может делать самостоятельно.
  Исключение: breaking API/DB changes — короткий review вторым owner’ом.

---

## Первые 30 дней (стартовый backlog)

### Domain A (Parsing Platform)
- Метрики и health: queue lag, worker utilization, ingest latency.
- Жесткие инварианты: “ingest error => run error”.
- Улучшить link’и происхождения товара (`product_category_links`) и покрыть тестами ingestion.

### Domain B (Operations/Admin UX)
- Свести polling к минимуму (SSE + version-driven refresh).
- Стандартизировать “error UI” + retry (макс 2 попытки) везде.
- Привести Catalog UX к рабочему: scraped category, merchants admin, быстрые фильтры.

