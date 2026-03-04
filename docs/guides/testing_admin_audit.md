# Аудит системы тестирования и план покрытия админки (apps/admin-tma)

Дата аудита: 2026-03-04  
Ветка: `tests-for-admin`

## 1) Контекст и что именно является «админкой»

В репозитории **нет** директории `apps/admin`. Вместо нее есть:

- `apps/admin-tma` — Next.js (Telegram Mini App) админка, запускается через `./start-dev.sh` (порт по умолчанию `3000`).
- `services/telegram_bot/dashboard` — отдельный Vite+React «дашборд» (порт по умолчанию `5173`), судя по `proxy.js` и `frontend_base` в настройках.

Дальше под «админкой» я рассматриваю **`apps/admin-tma`**, как вы запросили.

---

## 2) Текущая система тестирования (по репозиторию в целом)

### Backend (Python)

- Основной раннер: `pytest` (`pytest.ini` задает `testpaths=tests`, `asyncio_mode=strict`).
- Группировка/выключение тестов: `tests_config.yaml` + логика в `tests/conftest.py` (скип тестов по «группам» на базе 1-го сегмента пути).
- Маркеры:
  - `ai_test` — AI/LLM тесты
  - `slow` — медленные тесты
- CI (GitHub Actions): `.github/workflows/tests.yml` запускает `pytest --verbose -m "not ai_test"` на SQLite in-memory (без запуска фронта).

**Наблюдения/риски:**
- Тестовые зависимости (`pytest`, `pytest-asyncio`, `pytest-mock`) **не зафиксированы** в `requirements.txt` — в CI они ставятся отдельной командой. Это усложняет локальное воспроизведение и «одинаковость» окружений.
- В `coverage_report_clean.txt` видно, что запуск с `ai_test` может падать из‑за несовпадения настроек (`Settings.llm_provider`), т.е. часть тестов нестабильна/чувствительна к env.

### Frontend (JS/TS)

- В репозитории **нет** настроенной системы тестирования фронтенда:
  - ни unit/component (Jest/Vitest + RTL),
  - ни e2e (Playwright/Cypress),
  - ни CI‑джобы, которые бы это запускали.

---

## 3) Состояние `apps/admin-tma` с точки зрения тестируемости

### 3.1 Блокер: отсутствует модуль API

Многие файлы импортируют `@/lib/api`, но в `apps/admin-tma/src/lib` **нет** реализации (`find` нашел только `src/lib/grafana.ts`).

Это блокирует:
- сборку/запуск админки в чистом окружении,
- написание и запуск unit/component тестов,
- e2e тесты (так как не будет стартовать приложение).

### 3.2 Архитектурные особенности, которые важно учесть в тестах

- Авторизация и окружение Telegram: `TMAProvider` использует `@telegram-apps/sdk` и `window.Telegram.WebApp`.
- Сильная зависимость UI от асинхронного data‑fetching (React Query), и от SSE (`EventSource`).
- Большие компоненты «страница‑контейнер» (`src/app/page.tsx`) с логикой навигации/сайдбара/подписок.

Для удобных тестов понадобятся:
- тестовые провайдеры (QueryClientProvider + контексты языка/ops runtime/TMA),
- стаб/моки для `EventSource`, `@telegram-apps/sdk`, `next/navigation`,
- контрактная фиксация API слоя (`src/lib/api`).

---

## 4) Рекомендованная стратегия тестирования админки

Цель: получить предсказуемый пайплайн, который ловит регрессии UI/интеграций и не требует реального Telegram/реальных LLM.

### Слои тестов

1) **Unit (быстро, дешево)**
   - чистые функции/утилиты (парсинг, валидация, маппинг ошибок),
   - нормализация данных для таблиц/виджетов.

2) **Component/Integration (React Testing Library + Vitest)**
   - поведение компонентов с моками API (MSW или моки модулей),
   - сценарии на уровне хука/компонента: загрузка → успех/ошибка → ретраи → состояния кнопок/форм.

3) **E2E (Playwright)**
   - 2–5 «критических путей» (smoke): запуск, навигация, базовые мутации (вкл/выкл источника, запуск паука, обновление настроек, publish/rollback frontend‑конфига).
   - Telegram‑зависимость — обход через test mode (см. план ниже).

---

## 5) План по покрытию тестами `apps/admin-tma`

### Фаза 0 — Разблокировать сборку (обязательно)

- [x] Добавлен `apps/admin-tma/src/lib/api.ts` (единый API‑клиент + функции, которые импортирует UI).
- [x] Зафиксирован base URL: `NEXT_PUBLIC_API_BASE_URL` (fallback: `/api/v1`).

### Фаза 1 — Поднять unit/component тесты (Vitest)

- [x] Добавлены зависимости: `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`.
- [x] Добавлены `apps/admin-tma/vitest.config.ts` и `apps/admin-tma/src/test/setup.ts` (jest-dom + базовые browser mocks).
- [x] Добавлены `npm` скрипты: `test`, `test:watch`, `test:coverage`, `test:e2e`.
- [x] Добавлены `test-utils`:
  - `renderWithProviders` (React Query + LanguageContext + OpsRuntimeSettingsContext + TMAContext),
  - моки `EventSource` и `@telegram-apps/sdk`.

Минимальный стартовый набор тестов (первый PR):
- ✅ `ApiServerErrorBanner`
- ✅ `OpsRuntimeSettingsContext`
- ✅ `useFrontendRoutingData` (инвалидации + обработка ошибок)
- ✅ Smoke по ключевым view: `QueueView`, `ScrapersView`, `SpiderDetail`, `page.tsx` (табы)
- ✅ Coverage-gate: `statements>=30`, `lines>=30`, `branches>=20`, `functions>=20`

### Фаза 2 — Расширить покрытие ключевых экранов

Компоненты/фичи с максимальным ROI:
- ✅ `OperationsView` — добавлен smoke-тест без реального React Query / Recharts.
- ✅ `SpiderList`/`SpiderDetail` — добавлены smoke тесты.
- ✅ `SettingsView` — добавлен тест (restore defaults).
- ✅ `CatalogView` — добавлен тест (поиск/пагинация + apply new items).

### Фаза 3 — E2E smoke (Playwright)

- [x] Добавлен Playwright (E2E smoke) и запуск в CI.
- [x] Добавлен **test mode** для Telegram‑авторизации:
  - вариант A (предпочтительно): `TMAProvider` поддерживает env `NEXT_PUBLIC_TEST_MODE=1` и берет пользователя из `NEXT_PUBLIC_TEST_USER_JSON`;
  - вариант B: `TMAProvider` принимает проп `initialContext` (используется только в тестовой обвязке).

Smoke сценарии:
- ✅ открытие админки и навигация по вкладкам;
- ✅ Logs smoke (история + фильтр, SSE выключен);
- ✅ Settings critical (restore defaults).

### Фаза 4 — CI и «Definition of Done»

- [x] Добавлен job в GitHub Actions, который делает:
  - `npm ci` в `apps/admin-tma`,
  - `npm test`.
- [x] Coverage включен + пороги на первом этапе (30% statements/lines, 20% branches/functions).

---

## 6) Что я предлагаю сделать следующим шагом (если ок)

1) Довести E2E suite до 5–8 сценариев (publish/rollback frontend routing, operations retry, spider force run).
2) Поднять coverage до 60%: добавить component/integration тесты для `FrontendRoutingView` и `OperationsView` (не только smoke).
3) Поднять coverage до 80%: выделить “helpers-only” код в утилиты и покрыть их unit-тестами, минимизируя гигантские UI-smoke.
4) Убрать шум `console.error` в `TMAProvider.test.tsx` (замокать/подавить ожидаемую ошибку).
