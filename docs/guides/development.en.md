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
- `CORS_ORIGINS`: Comma-separated list of allowed frontend origins.

---

## 5. Testing

Code quality in Gifty is ensured through `pytest`. Tests are automatically run before every deployment.

### Running Tests Locally
```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-mock pyyaml

# Run all available tests
pytest
```

### Managing Test Suites (`tests_config.yaml`)
A `tests_config.yaml` file is located at the root of the project, allowing you to flexibly enable or disable test groups without changing the code:

```yaml
test_groups:
  recommendations: true  # Recommendation algorithm tests
  routes: true           # API endpoint tests
  ai_intelligence: false # Heavy AI tests (disabled by default)
```

**Why this is useful:**

1.  **Speed**: Heavily or slow tests can be disabled in CI/CD on the `develop` branch.
2.  **Cost**: Tests requiring paid APIs (e.g., OpenAI/Amnesia) can be enabled only manually before a release.

### Dynamic Skipping
If a test group is disabled in the config, `pytest` will mark them as `SKIPPED`. This is normal and does not break the pipeline.
