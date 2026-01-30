# Настройка GitHub Pages для документации

## Автоматическая публикация

Документация автоматически публикуется на GitHub Pages при каждом пуше в ветки `main` или `docs/*`.

### Шаги для первоначальной настройки:

1. **Включить GitHub Pages в репозитории:**
   - Перейдите в Settings → Pages
   - В разделе "Source" выберите "Deploy from a branch"
   - Выберите ветку `gh-pages` и папку `/ (root)`
   - Нажмите "Save"

2. **Проверить права доступа:**
   - Перейдите в Settings → Actions → General
   - В разделе "Workflow permissions" выберите "Read and write permissions"
   - Включите "Allow GitHub Actions to create and approve pull requests"
   - Нажмите "Save"

3. **Запустить первый деплой:**
   - Сделайте коммит в ветку `main` или `docs/*`
   - Или запустите workflow вручную: Actions → Deploy Documentation → Run workflow

### После настройки

Документация будет доступна по адресу:
**https://dev.giftyai.ru/**

## Локальная разработка

### Установка зависимостей
```bash
pip install -r requirements-docs.txt
```

### Запуск локального сервера
```bash
./scripts/docs.sh serve
# или
mkdocs serve
```

Документация будет доступна по адресу: http://127.0.0.1:8000

### Сборка статических файлов
```bash
./scripts/docs.sh build
# или
mkdocs build
```

## Структура документации

```
docs/
├── index.md                    # Главная страница
├── architecture/               # Архитектура системы
│   ├── overview.md
│   ├── parsing.md
│   ├── parsing_system.md
│   ├── parsing_plan.md
│   ├── recommendations.md
│   ├── gift_query_rules.md
│   └── intelligence.md
├── api/                        # API Reference
│   ├── models.md
│   ├── services.md
│   └── repositories.md
└── guides/                     # Руководства
    ├── development.md
    └── deployment.md
```

## Двуязычная поддержка

Документация поддерживает русский (по умолчанию) и английский языки.

Для каждого документа создаются две версии:
- `filename.md` - русская версия
- `filename.en.md` - английская версия

Переключение языка доступно в верхнем меню сайта.

## Кастомный домен (опционально)

Если у вас есть кастомный домен:

1. Раскомментируйте строку `cname` в `.github/workflows/docs.yml`:
   ```yaml
   cname: docs.gifty.ai
   ```

2. Настройте DNS записи у вашего провайдера:
   ```
   CNAME docs.gifty.ai -> icedarold.github.io
   ```

3. В настройках GitHub Pages укажите кастомный домен
