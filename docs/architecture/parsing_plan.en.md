# План реализации Scalable Parsing System

## Блок 1: Фундамент (Infrastructure & Core)
*Цель: Подготовить базу данных и брокер сообщений.*

- [ ] **Инфраструктура RabbitMQ**
    - [ ] Добавить сервис `rabbitmq` в `docker-compose.yml` (management plugin).
    - [ ] Настроить ENV-переменные для подключения.
- [ ] **База Данных (Schema Migration)**
    - [ ] Создать модель `ParsingSource` (поля: `url`, `type`, `strategy`, `priority`, `schedule_config`, `next_sync_at`).
    - [ ] Создать модель `CategoryMap` (поля: `external_name`, `internal_id`).
    - [ ] Сделать миграцию (Alembic).
- [ ] **Инициализация Scraper Service**
    - [ ] Создать папку `services/scraper`.
    - [ ] `scrapy startproject gifty_scraper`.
    - [ ] Создать `Dockerfile` и добавить сервис `scraper_worker` в `docker-compose.yml`.

## Блок 2: Воркеры и Пауки (Execution Layer)
*Цель: Научить систему парсить сайты через очередь.*

- [ ] **RabbitMQ Consumer**
    - [ ] Написать скрипт `run_worker.py` (или Management Command), который слушает очередь `parsing_tasks`.
    - [ ] Реализовать запуск Spider'а по сообщению из очереди.
- [ ] **MrGeek Spider (Migration)**
    - [ ] Реализовать `MrGeekSpider` на Scrapy (перенос логики селекторов).
    - [ ] Реализовать пагинацию (Strategy: `deep`).
    - [ ] Реализовать `ItemPipeline` для отправки данных (пока `print` в консоль или mock).
- [ ] **Тестирование**
    - [ ] Создать фикстуру (`tests/fixtures/mrgeek_list.html`).
    - [ ] Написать тест парсера на этой фикстуре.

## Блок 3: Оркестрация и Ingestion (The Brain)
*Цель: Замкнуть цикл "Запуск -> Парсинг -> Сохранение".*

- [ ] **Ingestion API**
    - [ ] Эндпоинт `POST /internal/ingest-batch` (FastAPI).
    - [ ] Валидация данных (Pydantic).
    - [ ] Логика Upsert (обновление цены, если товар есть; создание, если нет).
    - [ ] Обновление статистики `ParsingSource` (last_synced, items_count).
- [ ] **Scheduler**
    - [ ] Реализовать фоновую задачу (Celery/AsyncLoop), которая выбирает `ParsingSource` по времени (`next_sync_at`).
    - [ ] Публикация задач в RabbitMQ.
- [ ] **Интеграция Pipeline**
    - [ ] Переписать `ItemPipeline` в Scrapy, чтобы он слал реальные POST-запросы на Ingestion API.

## Блок 4: Умные функции (Smart Features)
*Цель: Автоматизация и защита.*

- [ ] **AI Category Mapper**
    - [ ] Логика в Ingestion API: сохранение новых категорий в `CategoryMap`.
    - [ ] Фоновая задача: отправка новых категорий в LLM для маппинга.
- [ ] **Middleware & Security**
    - [ ] Настроить `RetryMiddleware` (паузы при ошибках).
    - [ ] Подключить `UserAgentMiddleware`.
    - [ ] (Опционально) Интеграция Proxy-сервиса.
