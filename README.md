# Gifty Backend (FastAPI + OAuth)

Backend авторизации для SPA (React) c OAuth (Google/Yandex/VK), PKCE и серверными сессиями (Redis). Данные пользователей и привязок хранятся в Postgres.

## Быстрый старт
1. Скопировать переменные окружения:
   ```bash
   cp .env.example .env
   # заполните OAuth-креды и домены/куки
   ```
2. Поднять Postgres и Redis:
   ```bash
   docker compose up -d
   ```
3. Установить зависимости (локально):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
4. Применить миграции:
   ```bash
   alembic upgrade head
   ```
5. Запустить API:
   ```bash
   uvicorn app.main:app --reload
   # слушает по умолчанию 127.0.0.1:8000
   ```

## Полезные URL
- Старт OAuth: `GET /api/v1/auth/{google|yandex|vk}/start?return_to=/path`
- Callback (обрабатывается бекендом): `/api/v1/auth/{provider}/callback`
- Текущий пользователь: `GET /api/v1/auth/me`
- Выход: `POST /api/v1/auth/logout`
- Healthcheck: `GET /health`

## Тесты (базовые)
```bash
pytest -q
```

## Примечания
- Все секреты задаются через `.env`, в коде не хардкодятся.
- Сессия хранится в Redis (`gifty_session` HttpOnly cookie). `STATE` для OAuth хранится в Redis 10 минут.
- Ответы в snake_case, ошибки: `{ "error": { "code": "...", "message": "...", "fields": {...} } }`.
