# Git Flow & Deployment Rules

This document outlines the branching strategy and deployment workflow for the Gifty Backend.

## 1. Branch Structure

| Branch | Purpose | Environment | Stability |
| :--- | :--- | :--- | :--- |
| `main` | Production code. Only contains released versions. | Production | **Highest (Locked)** |
| `develop` | Integration branch for features. | Staging / Test | Stable |
| `feature/*` | New features or tasks (e.g., `feature/auth-yandex`). | Local / Dev | Experimental |
| `research/*` | ML experiments and data research (e.g., `research/scoring-v2`). | Kaggle / Local | Experimental |
| `hotfix/*` | Critical bug fixes for production. | Production | Stable |

---

## 2. Workflow Rules

### Feature Development
1. Create a branch from `develop`: `git checkout -b feature/my-feature`
2. Work and commit locally.
3. Open a Pull Request (PR) to `develop`.
4. After review and CI success, merge into `develop`.

### Research / ML Work
1. Create a branch from `develop` or `main`: `git checkout -b research/cool-new-vlm`
2. Use this branch for Jupyter notebooks and experimental logic.
3. When research is finalized, port the results to a `feature/` branch or merge via PR if the code is production-ready.

### Release to Production
1. When `develop` is ready for release, create a PR from `develop` to `main`.
2. **Tag the release**: `git tag -a v1.x.x -m "Release description"`
3. Push tags: `git push origin --tags`

---

## 3. Database Migrations (Alembic)

- **NEVER** edit existing migration files in `alembic/versions`.
- Always generate new migrations: `alembic revision --autogenerate -m "description"`
- Migrations are automatically applied in production during the Docker startup via `scripts/start.sh`.
- Test migrations on your local DB before merging into `develop`.

---

## 4. Environment Variables

Sensitive data must **NEVER** be committed to the repository. Use environment variables on the server:
- `DATABASE_URL`: Production DB connection string.
- `REDIS_URL`: Production Redis URL.
- `INTERNAL_API_TOKEN`: Token for inter-service communication.
- `SECRET_KEY`: Long random string for JWT/Security.
- `ENV`: Set to `prod` for production servers.
- `DEBUG`: Set to `false` in production.
---

## 5. Тестирование

Качество кода в Gifty обеспечивается через `pytest`. Тесты запускаются автоматически перед каждым деплоем.

### Запуск тестов локально
```bash
# Установка зависимостей для тестов
pip install pytest pytest-asyncio pytest-mock pyyaml

# Запуск всех доступных тестов
pytest
```

### Управление составом тестов (`tests_config.yaml`)
В корне проекта находится файл `tests_config.yaml`, который позволяет гибко включать и отключать группы тестов без изменения кода:

```yaml
test_groups:
  recommendations: true  # Тесты алгоритмов подбора
  routes: true           # Тесты API эндпоинтов
  ai_intelligence: false # Тяжелые тесты AI (по умолчанию выключены)
```

**Зачем это нужно:**
1.  **Скорость**: В CI/CD на `develop` можно отключать тяжелые/медленные тесты.
2.  **Экономия**: Тесты, требующие платных API (например, OpenAI/Amnesia), можно включать только вручную перед релизом.

### Динамический пропуск (Skipping)
Если группа тестов отключена в конфиге, `pytest` пометит их как `SKIPPED`. Это нормально и не ломает пайплайн.

