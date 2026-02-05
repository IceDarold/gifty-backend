window.WEEEK_STATIC_DATA = {
  "success": true,
  "tasks": [
    {
      "id": 52,
      "parentId": null,
      "title": "Разработать систему вопросов",
      "description": "<p></p>",
      "overdue": 0,
      "duration": null,
      "type": "action",
      "priority": null,
      "isCompleted": false,
      "isDeleted": false,
      "authorId": "a074c2d7-bae3-4deb-a660-dba18305c2ee",
      "userId": null,
      "assignees": [],
      "projectId": 4,
      "boardId": 17,
      "boardColumnId": 49,
      "locations": [
        {
          "projectId": 4,
          "boardId": 17,
          "boardColumnId": 49
        }
      ],
      "image": null,
      "isPrivate": false,
      "date": null,
      "time": null,
      "dateStart": null,
      "dateEnd": null,
      "timeStart": null,
      "timeEnd": null,
      "startDate": null,
      "startDateTime": null,
      "dueDate": null,
      "dueDateTime": null,
      "createdAt": "2026-01-31T08:41:38Z",
      "updatedAt": "2026-01-31T09:05:35Z",
      "tags": [
        7
      ],
      "subscribers": [
        "a074c2d7-bae3-4deb-a660-dba18305c2ee"
      ],
      "subTasks": [],
      "workloads": [],
      "timeEntries": [],
      "timer": null,
      "customFields": [],
      "attachments": []
    },
    {
      "id": 51,
      "parentId": null,
      "title": "Реализовать рекомендации для главной страницы сайта",
      "description": "<h2>Реализовать endpoint получения списка подарков (GET /api/v1/gifts)</h2>\n<h3>Контекст / Зачем</h3>\n<p>Фронтенду требуется публичный API для получения списка подарков (товаров), который используется:</p>\n<ol><li><p>на главной странице сайта (лента)</p></li></ol>\n<p>Endpoint должен поддерживать фильтрацию, лимитирование и возвращать данные в формате, совместимом с существующими DTO на фронтенде.</p>\n<hr>\n<h3>Endpoint</h3>\n<p><strong>Method:</strong> GET<br><strong>URL:</strong> <code>/api/v1/gifts</code><br><strong>Доступ:</strong> публичный (без авторизации)</p>\n<hr>\n<h3>Query parameters (все необязательные)</h3>\n<ol><li><p><code>limit: number</code><br>Максимальное количество возвращаемых товаров<br>Default: <code>20</code></p></li></ol>\n<ol><li><p><code>tag: string</code><br>Фильтр по тегу (частичное совпадение, case-insensitive)</p></li></ol>\n<ol><li><p><code>category: string</code><br>Фильтр по категории (точное или частичное совпадение, case-insensitive)</p></li></ol>\n<ol><li><p><code>ids: string[]</code><br>Список ID товаров для получения конкретных позиций (wishlist).<br>Если передан — остальные фильтры могут игнорироваться.</p></li></ol>\n<hr>\n<h3>Логика работы</h3>\n<ol><li><p>Если query-параметры не переданы — вернуть список последних или случайных товаров</p></li></ol>\n<ol><li><p>Если передан <code>ids</code>:</p>\n<ol><li><p>вернуть товары, ID которых входят в список</p></li></ol></li></ol>\n<ol><li><p>Если передан <code>category</code>:</p>\n<ol><li><p>отфильтровать товары по категории (без учета регистра)</p></li></ol></li></ol>\n<ol><li><p>Если передан <code>tag</code>:</p>\n<ol><li><p>вернуть товары, у которых в <code>tags_list</code> есть элемент, содержащий подстроку <code>tag</code></p></li></ol></li></ol>\n<ol><li><p>Применить ограничение по <code>limit</code></p></li></ol>\n<ol><li><p>Если товары не найдены — вернуть пустой массив <code>[]</code> со статусом <code>200 OK</code></p></li></ol>\n<hr>\n<h3>Формат ответа</h3>\n<p><strong>Content-Type:</strong> <code>application/json</code><br><strong>Status:</strong> <code>200 OK</code></p>\n<p>Возвращается массив объектов <code>GiftDTO</code>:</p>\n<pre><code>[\n  {\n    \"id\": \"string\",\n    \"title\": \"string\",\n    \"description\": \"string | null\",\n    \"price\": \"number | null\",\n    \"currency\": \"string\",\n    \"image_url\": \"string | null\",\n    \"product_url\": \"string\",\n    \"merchant\": \"string | null\",\n    \"category\": \"string | null\",\n    \"tags_list\": [\"string\"],\n    \"ai_reason\": \"string | null\",\n    \"reviews_data\": {\n      \"average_rating\": \"number\",\n      \"total_count\": \"number\",\n      \"source_platform\": \"string\",\n      \"top_highlights\": [\"string\"],\n      \"reviews_list\": [\n        {\n          \"id\": \"string\",\n          \"author_name\": \"string\",\n          \"rating_val\": \"number\",\n          \"created_at\": \"string\",\n          \"content\": \"string\",\n          \"tag_label\": \"string\",\n          \"photo_urls\": [\"string\"]\n        }\n      ]\n    }\n  }\n]</code></pre>\n<hr>\n<h3>Acceptance Criteria</h3>\n<ol><li><p>Endpoint доступен по <code>GET /api/v1/gifts</code></p></li></ol>\n<ol><li><p>Работает без авторизации</p></li></ol>\n<ol><li><p>Поддерживается <code>limit</code></p></li></ol>\n<ol><li><p>Поддерживается фильтрация по <code>category</code></p></li></ol>\n<ol><li><p>Поддерживается фильтрация по <code>tag</code> (по массиву <code>tags_list</code>)</p></li></ol>\n<ol><li><p>Поддерживается батч-загрузка по <code>ids</code></p></li></ol>\n<ol><li><p>При отсутствии результатов возвращается <code>[]</code> и <code>200 OK</code></p></li></ol>\n<ol><li><p>Ответ соответствует формату <code>GiftDTO</code></p></li></ol>\n<ol><li><p>Endpoint стабилен и не падает при пустых/некорректных параметрах</p></li></ol>\n<hr>\n<h3>Ошибки</h3>\n<ol><li><p><code>500 Internal Server Error</code></p></li></ol>\n<pre><code>{\n  \"error\": {\n    \"message\": \"Internal Server Error\"\n  }\n}</code></pre>\n<hr>\n<h3>Не входит в задачу (Non-goals)</h3>\n<ol><li><p>❌ Персонализация рекомендаций</p></li></ol>\n<ol><li><p>❌ Авторизация / ACL</p></li></ol>\n<ol><li><p>❌ Ранжирование или ML-логика</p></li></ol>\n<ol><li><p>❌ A/B тесты</p></li></ol>\n<hr>\n<h3>Технические примечания</h3>\n<ol><li><p>Поля <code>category</code> и <code>tags_list</code> должны быть проиндексированы в БД</p></li></ol>\n<ol><li><p>Endpoint относится к слою <strong>Public API / User Interaction</strong></p></li></ol>\n<ol><li><p>Фронтенд имеет fallback на mock-данные, но продакшен-реализация должна быть стабильной</p></li></ol>",
      "overdue": 0,
      "duration": null,
      "type": "action",
      "priority": null,
      "isCompleted": false,
      "isDeleted": false,
      "authorId": "a074c2d7-bae3-4deb-a660-dba18305c2ee",
      "userId": null,
      "assignees": [],
      "projectId": 2,
      "boardId": 11,
      "boardColumnId": 31,
      "locations": [
        {
          "projectId": 2,
          "boardId": 11,
          "boardColumnId": 31
        }
      ],
      "image": null,
      "isPrivate": false,
      "date": null,
      "time": null,
      "dateStart": null,
      "dateEnd": null,
      "timeStart": null,
      "timeEnd": null,
      "startDate": null,
      "startDateTime": null,
      "dueDate": null,
      "dueDateTime": null,
      "createdAt": "2026-01-30T15:51:26Z",
      "updatedAt": "2026-01-30T15:54:13Z",
      "tags": [],
      "subscribers": [
        "a074c2d7-bae3-4deb-a660-dba18305c2ee"
      ],
      "subTasks": [],
      "workloads": [],
      "timeEntries": [],
      "timer": null,
      "customFields": [],
      "attachments": []
    },
    {
      "id": 50,
      "parentId": null,
      "title": "Реализовать подписку на рассылку",
      "description": "<p>На публичных страницах Gifty (лендинг, маркетинговые блоки) требуется форма подписки на email-рассылку.<br>Подписка используется для сбора аудитории, отправки новостей, промо и продуктовых апдейтов.</p>\n<p>Необходимо реализовать backend-логику для приёма email, валидации и сохранения подписок.</p>\n<hr>\n<h3>Что нужно сделать</h3>\n<ol><li><p>Реализовать публичный endpoint для подписки на рассылку</p></li></ol>\n<ol><li><p>Принимать email от фронтенда</p></li></ol>\n<ol><li><p>Валидировать корректность email</p></li></ol>\n<ol><li><p>Сохранять подписку в базе данных</p></li></ol>\n<ol><li><p>Обрабатывать повторные подписки (idempotency)</p></li></ol>\n<hr>\n<h3>API</h3>\n<p><strong>Endpoint:</strong><br><code>POST /public/subscribe</code></p>\n<p><strong>Request body:</strong></p>\n<pre><code>{\n  \"email\": \"user@example.com\"\n}</code></pre>\n<p><strong>Response (200):</strong></p>\n<pre><code>{\n  \"status\": \"ok\"\n}</code></pre>\n<p><strong>Response (4xx):</strong></p>\n<ol><li><p>Некорректный email</p></li></ol>\n<ol><li><p>Email уже подписан</p></li></ol>\n<hr>\n<h3>Бизнес-логика</h3>\n<ol><li><p>Email должен быть валидным</p></li></ol>\n<ol><li><p>Один email может быть подписан только один раз (если идет повторный раз нужно возвращать response с ошибкой и пояснением)</p></li></ol>\n<ol><li><p>Повторный запрос с тем же email не должен создавать дубликаты</p></li></ol>\n<hr>\n<h3>Acceptance Criteria (критерии готовности)</h3>\n<ol><li><p>Endpoint доступен без авторизации</p></li></ol>\n<ol><li><p>Email валидируется на backend</p></li></ol>\n<ol><li><p>Подписка сохраняется в БД</p></li></ol>\n<ol><li><p>Повторная подписка не создаёт дубликат</p></li></ol>\n<ol><li><p>Endpoint корректно вызывается с фронтенда</p></li></ol>\n<ol><li><p>Возвращается понятный HTTP-статус и JSON-ответ</p></li></ol>\n<hr>\n<h3>Не входит в задачу (Non-goals)</h3>\n<ol><li><p>❌ Отправка писем</p></li></ol>\n<ol><li><p>❌ Double opt-in</p></li></ol>\n<ol><li><p>❌ Интеграция с внешними email-сервисами</p></li></ol>\n<hr>\n<h3>Примечания</h3>\n<ol><li><p>Endpoint относится к слою <strong>Public API / User Interaction</strong></p></li></ol>\n<ol><li><p>Структура БД может быть расширена в будущем (status, source, timestamps)</p></li></ol>",
      "overdue": 0,
      "duration": null,
      "type": "action",
      "priority": null,
      "isCompleted": false,
      "isDeleted": false,
      "authorId": "a074c2d7-bae3-4deb-a660-dba18305c2ee",
      "userId": null,
      "assignees": [],
      "projectId": 2,
      "boardId": 19,
      "boardColumnId": 55,
      "locations": [
        {
          "projectId": 2,
          "boardId": 19,
          "boardColumnId": 55
        }
      ],
      "image": null,
      "isPrivate": false,
      "date": null,
      "time": null,
      "dateStart": null,
      "dateEnd": null,
      "timeStart": null,
      "timeEnd": null,
      "startDate": null,
      "startDateTime": null,
      "dueDate": null,
      "dueDateTime": null,
      "createdAt": "2026-01-30T15:35:54Z",
      "updatedAt": "2026-01-30T15:40:21Z",
      "tags": [],
      "subscribers": [
        "a074c2d7-bae3-4deb-a660-dba18305c2ee"
      ],
      "subTasks": [],
      "workloads": [],
      "timeEntries": [],
      "timer": null,
      "customFields": [],
      "attachments": []
    },
    {
      "id": 49,
      "parentId": null,
      "title": "Реализовать LLM axes scoring",
      "description": "<p></p>",
      "overdue": 0,
      "duration": null,
      "type": "action",
      "priority": null,
      "isCompleted": false,
      "isDeleted": false,
      "authorId": "a074c2d7-bae3-4deb-a660-dba18305c2ee",
      "userId": null,
      "assignees": [],
      "projectId": 2,
      "boardId": 11,
      "boardColumnId": 31,
      "locations": [
        {
          "projectId": 2,
          "boardId": 11,
          "boardColumnId": 31
        }
      ],
      "image": null,
      "isPrivate": false,
      "date": null,
      "time": null,
      "dateStart": null,
      "dateEnd": null,
      "timeStart": null,
      "timeEnd": null,
      "startDate": null,
      "startDateTime": null,
      "dueDate": null,
      "dueDateTime": null,
      "createdAt": "2026-01-30T15:16:42Z",
      "updatedAt": "2026-01-30T15:20:47Z",
      "tags": [],
      "subscribers": [
        "a074c2d7-bae3-4deb-a660-dba18305c2ee"
      ],
      "subTasks": [],
      "workloads": [],
      "timeEntries": [],
      "timer": null,
      "customFields": [],
      "attachments": []
    },
    {
      "id": 48,
      "parentId": null,
      "title": "Yandex OAuth Integration",
      "description": "<p></p>",
      "overdue": 0,
      "duration": null,
      "type": "action",
      "priority": null,
      "isCompleted": false,
      "isDeleted": false,
      "authorId": "a074c2d7-bae3-4deb-a660-dba18305c2ee",
      "userId": null,
      "assignees": [],
      "projectId": 2,
      "boardId": 12,
      "boardColumnId": 34,
      "locations": [
        {
          "projectId": 2,
          "boardId": 12,
          "boardColumnId": 34
        }
      ],
      "image": null,
      "isPrivate": false,
      "date": null,
      "time": null,
      "dateStart": null,
      "dateEnd": null,
      "timeStart": null,
      "timeEnd": null,
      "startDate": null,
      "startDateTime": null,
      "dueDate": null,
      "dueDateTime": null,
      "createdAt": "2026-01-30T14:44:24Z",
      "updatedAt": "2026-01-30T14:44:29Z",
      "tags": [
        5
      ],
      "subscribers": [
        "a074c2d7-bae3-4deb-a660-dba18305c2ee"
      ],
      "subTasks": [],
      "workloads": [],
      "timeEntries": [],
      "timer": null,
      "customFields": [],
      "attachments": []
    },
    {
      "id": 46,
      "parentId": null,
      "title": "Google OAuth Integration",
      "description": "<p></p>",
      "overdue": 0,
      "duration": null,
      "type": "action",
      "priority": null,
      "isCompleted": false,
      "isDeleted": false,
      "authorId": "a074c2d7-bae3-4deb-a660-dba18305c2ee",
      "userId": null,
      "assignees": [],
      "projectId": 2,
      "boardId": 12,
      "boardColumnId": 34,
      "locations": [
        {
          "projectId": 2,
          "boardId": 12,
          "boardColumnId": 34
        }
      ],
      "image": null,
      "isPrivate": false,
      "date": null,
      "time": null,
      "dateStart": null,
      "dateEnd": null,
      "timeStart": null,
      "timeEnd": null,
      "startDate": null,
      "startDateTime": null,
      "dueDate": null,
      "dueDateTime": null,
      "createdAt": "2026-01-30T13:41:18Z",
      "updatedAt": "2026-01-30T14:44:19Z",
      "tags": [
        5
      ],
      "subscribers": [
        "a074c2d7-bae3-4deb-a660-dba18305c2ee"
      ],
      "subTasks": [],
      "workloads": [],
      "timeEntries": [],
      "timer": null,
      "customFields": [],
      "attachments": []
    },
    {
      "id": 45,
      "parentId": null,
      "title": "Реализовать LLM giftability scoring",
      "description": "<p>В нашей системе довольно большой ассортимент. Перед тем, как проводить дорогую оценку товара и индексировать его, необходимо откинуть \"неподарочные\" товары, чтобы не тратить ресурсы на ненужные вычисления</p>\n<h3>Особенности</h3>\n<ol><li><p>Так как пока у нас нет своих вычислительных ресурсов, единственный доступ к GPU есть через kaggle, поэтому в качестве результата нужен ноутбук с кодом, который можно автономно запустить на kaggle.</p></li></ol>\n<ol><li><p>У нас есть доступ только к двум T4 GPU (возможно несколько раз по 2, если использовать разные аккаунты), а обрабатывать необходимо сотни товаров в секунду, поэтому необходимо быстрая система</p></li></ol>\n<p></p>\n<h3>Список действий</h3>\n<ul><li value=\"1\"><p>Реализовать получение данных с эндпоинта (см. пример в ноутбуке)</p></li></ul>\n<ul><li value=\"2\"><p>Придумать способ быстро оценивать giftability товара (по названию и картинке. Лучше только название, потому что это быстрее)</p></li></ul>\n<ul><li value=\"3\"><p>Реализовать полностью готовый к автономной работе ноутбук</p></li></ul>\n<p></p>",
      "overdue": 0,
      "duration": null,
      "type": "action",
      "priority": null,
      "isCompleted": false,
      "isDeleted": false,
      "authorId": "a074c2d7-bae3-4deb-a660-dba18305c2ee",
      "userId": "a074c2d7-bae3-4deb-a660-dba18305c2ee",
      "assignees": [
        "a074c2d7-bae3-4deb-a660-dba18305c2ee"
      ],
      "projectId": 2,
      "boardId": 11,
      "boardColumnId": 32,
      "locations": [
        {
          "projectId": 2,
          "boardId": 11,
          "boardColumnId": 32
        }
      ],
      "image": null,
      "isPrivate": false,
      "date": null,
      "time": null,
      "dateStart": null,
      "dateEnd": null,
      "timeStart": null,
      "timeEnd": null,
      "startDate": null,
      "startDateTime": null,
      "dueDate": null,
      "dueDateTime": null,
      "createdAt": "2026-01-30T13:41:10Z",
      "updatedAt": "2026-01-30T14:55:40Z",
      "tags": [
        4
      ],
      "subscribers": [
        "a074c2d7-bae3-4deb-a660-dba18305c2ee"
      ],
      "subTasks": [],
      "workloads": [],
      "timeEntries": [],
      "timer": null,
      "customFields": [],
      "attachments": []
    },
    {
      "id": 44,
      "parentId": null,
      "title": "LLM Category Classifier",
      "description": "<p>При парсинге товаров с разных ресурсов, мы сталкиваемся с проблемой разнообразия категорий. Одни сайты пишут \"прикольные кружки\", другие \"кружки для чая\". Нам необходимо иметь универсальные категории.</p>\n<h3>Особенности</h3>\n<ol><li><p>Так как пока у нас нет своих вычислительных ресурсов, единственный доступ к GPU есть через kaggle, поэтому в качестве результата нужен ноутбук с кодом, который можно автономно запустить на kaggle.</p></li></ol>\n<h3>Список действий</h3>\n<ol><li><p>Настроить получение данных с эндпоинтов</p></li></ol>\n<ol><li><p>Написать ноутбук, которые будет мапить категории и отправлять через второй эндпоинт на сервер</p></li></ol>",
      "overdue": 0,
      "duration": null,
      "type": "action",
      "priority": null,
      "isCompleted": false,
      "isDeleted": false,
      "authorId": "a074c2d7-bae3-4deb-a660-dba18305c2ee",
      "userId": null,
      "assignees": [],
      "projectId": 2,
      "boardId": 11,
      "boardColumnId": 31,
      "locations": [
        {
          "projectId": 2,
          "boardId": 11,
          "boardColumnId": 31
        }
      ],
      "image": null,
      "isPrivate": false,
      "date": null,
      "time": null,
      "dateStart": null,
      "dateEnd": null,
      "timeStart": null,
      "timeEnd": null,
      "startDate": null,
      "startDateTime": null,
      "dueDate": null,
      "dueDateTime": null,
      "createdAt": "2026-01-30T13:41:07Z",
      "updatedAt": "2026-01-30T15:16:06Z",
      "tags": [
        4
      ],
      "subscribers": [
        "a074c2d7-bae3-4deb-a660-dba18305c2ee"
      ],
      "subTasks": [],
      "workloads": [],
      "timeEntries": [],
      "timer": null,
      "customFields": [],
      "attachments": []
    },
    {
      "id": 43,
      "parentId": null,
      "title": "Data Validation Schemas",
      "description": null,
      "overdue": 0,
      "duration": null,
      "type": "action",
      "priority": null,
      "isCompleted": true,
      "isDeleted": false,
      "authorId": "a074c2d7-bae3-4deb-a660-dba18305c2ee",
      "userId": null,
      "assignees": [],
      "projectId": 2,
      "boardId": 10,
      "boardColumnId": 30,
      "locations": [
        {
          "projectId": 2,
          "boardId": 10,
          "boardColumnId": 30
        }
      ],
      "image": null,
      "isPrivate": false,
      "date": null,
      "time": null,
      "dateStart": null,
      "dateEnd": null,
      "timeStart": null,
      "timeEnd": null,
      "startDate": null,
      "startDateTime": null,
      "dueDate": null,
      "dueDateTime": null,
      "createdAt": "2026-01-30T13:41:02Z",
      "updatedAt": "2026-01-30T13:41:05Z",
      "tags": [
        3
      ],
      "subscribers": [
        "a074c2d7-bae3-4deb-a660-dba18305c2ee"
      ],
      "subTasks": [],
      "workloads": [],
      "timeEntries": [],
      "timer": null,
      "customFields": [],
      "attachments": []
    },
    {
      "id": 42,
      "parentId": null,
      "title": "Ingestion API Endpoint",
      "description": null,
      "overdue": 0,
      "duration": null,
      "type": "action",
      "priority": null,
      "isCompleted": true,
      "isDeleted": false,
      "authorId": "a074c2d7-bae3-4deb-a660-dba18305c2ee",
      "userId": null,
      "assignees": [],
      "projectId": 2,
      "boardId": 10,
      "boardColumnId": 30,
      "locations": [
        {
          "projectId": 2,
          "boardId": 10,
          "boardColumnId": 30
        }
      ],
      "image": null,
      "isPrivate": false,
      "date": null,
      "time": null,
      "dateStart": null,
      "dateEnd": null,
      "timeStart": null,
      "timeEnd": null,
      "startDate": null,
      "startDateTime": null,
      "dueDate": null,
      "dueDateTime": null,
      "createdAt": "2026-01-30T13:40:57Z",
      "updatedAt": "2026-01-30T13:41:02Z",
      "tags": [
        3
      ],
      "subscribers": [
        "a074c2d7-bae3-4deb-a660-dba18305c2ee"
      ],
      "subTasks": [],
      "workloads": [],
      "timeEntries": [],
      "timer": null,
      "customFields": [],
      "attachments": []
    },
    {
      "id": 41,
      "parentId": null,
      "title": "Adaptive Scheduling Logic",
      "description": "<p>Очень крутая задача. Сложная</p>",
      "overdue": 0,
      "duration": null,
      "type": "action",
      "priority": null,
      "isCompleted": false,
      "isDeleted": false,
      "authorId": "a074c2d7-bae3-4deb-a660-dba18305c2ee",
      "userId": "a074c2d7-bae3-4deb-a660-dba18305c2ee",
      "assignees": [
        "a074c2d7-bae3-4deb-a660-dba18305c2ee"
      ],
      "projectId": 2,
      "boardId": 10,
      "boardColumnId": 28,
      "locations": [
        {
          "projectId": 2,
          "boardId": 10,
          "boardColumnId": 28
        }
      ],
      "image": null,
      "isPrivate": false,
      "date": "31.01.2026",
      "time": null,
      "dateStart": null,
      "dateEnd": null,
      "timeStart": null,
      "timeEnd": null,
      "startDate": null,
      "startDateTime": null,
      "dueDate": "2026-01-31",
      "dueDateTime": null,
      "createdAt": "2026-01-30T13:40:55Z",
      "updatedAt": "2026-01-30T13:53:40Z",
      "tags": [
        2
      ],
      "subscribers": [
        "a074c2d7-bae3-4deb-a660-dba18305c2ee"
      ],
      "subTasks": [],
      "workloads": [],
      "timeEntries": [],
      "timer": null,
      "customFields": [],
      "attachments": []
    },
    {
      "id": 40,
      "parentId": null,
      "title": "Proxy Rotation Middleware",
      "description": "",
      "overdue": 0,
      "duration": null,
      "type": "action",
      "priority": null,
      "isCompleted": false,
      "isDeleted": false,
      "authorId": "a074c2d7-bae3-4deb-a660-dba18305c2ee",
      "userId": null,
      "assignees": [],
      "projectId": 2,
      "boardId": 10,
      "boardColumnId": 28,
      "locations": [
        {
          "projectId": 2,
          "boardId": 10,
          "boardColumnId": 28
        }
      ],
      "image": null,
      "isPrivate": false,
      "date": null,
      "time": null,
      "dateStart": null,
      "dateEnd": null,
      "timeStart": null,
      "timeEnd": null,
      "startDate": null,
      "startDateTime": null,
      "dueDate": null,
      "dueDateTime": null,
      "createdAt": "2026-01-30T13:40:51Z",
      "updatedAt": "2026-01-30T13:40:51Z",
      "tags": [
        2
      ],
      "subscribers": [
        "a074c2d7-bae3-4deb-a660-dba18305c2ee"
      ],
      "subTasks": [],
      "workloads": [],
      "timeEntries": [],
      "timer": null,
      "customFields": [],
      "attachments": []
    },
    {
      "id": 39,
      "parentId": null,
      "title": "Base Scrapy Spider Class",
      "description": null,
      "overdue": 0,
      "duration": null,
      "type": "action",
      "priority": null,
      "isCompleted": true,
      "isDeleted": false,
      "authorId": "a074c2d7-bae3-4deb-a660-dba18305c2ee",
      "userId": null,
      "assignees": [],
      "projectId": 2,
      "boardId": 10,
      "boardColumnId": 30,
      "locations": [
        {
          "projectId": 2,
          "boardId": 10,
          "boardColumnId": 30
        }
      ],
      "image": null,
      "isPrivate": false,
      "date": null,
      "time": null,
      "dateStart": null,
      "dateEnd": null,
      "timeStart": null,
      "timeEnd": null,
      "startDate": null,
      "startDateTime": null,
      "dueDate": null,
      "dueDateTime": null,
      "createdAt": "2026-01-30T13:40:49Z",
      "updatedAt": "2026-01-30T13:40:50Z",
      "tags": [
        2
      ],
      "subscribers": [
        "a074c2d7-bae3-4deb-a660-dba18305c2ee"
      ],
      "subTasks": [],
      "workloads": [],
      "timeEntries": [],
      "timer": null,
      "customFields": [],
      "attachments": []
    },
    {
      "id": 38,
      "parentId": null,
      "title": "Implement CI/CD pipeline",
      "description": "<p></p>",
      "overdue": 0,
      "duration": null,
      "type": "action",
      "priority": null,
      "isCompleted": false,
      "isDeleted": false,
      "authorId": "a074c2d7-bae3-4deb-a660-dba18305c2ee",
      "userId": null,
      "assignees": [],
      "projectId": 2,
      "boardId": 9,
      "boardColumnId": 25,
      "locations": [
        {
          "projectId": 2,
          "boardId": 9,
          "boardColumnId": 25
        }
      ],
      "image": null,
      "isPrivate": false,
      "date": null,
      "time": null,
      "dateStart": null,
      "dateEnd": null,
      "timeStart": null,
      "timeEnd": null,
      "startDate": null,
      "startDateTime": null,
      "dueDate": null,
      "dueDateTime": null,
      "createdAt": "2026-01-30T13:40:48Z",
      "updatedAt": "2026-01-30T15:26:42Z",
      "tags": [
        6
      ],
      "subscribers": [
        "a074c2d7-bae3-4deb-a660-dba18305c2ee"
      ],
      "subTasks": [],
      "workloads": [],
      "timeEntries": [],
      "timer": null,
      "customFields": [],
      "attachments": []
    },
    {
      "id": 37,
      "parentId": null,
      "title": "Dockerize all services",
      "description": null,
      "overdue": 0,
      "duration": null,
      "type": "action",
      "priority": null,
      "isCompleted": false,
      "isDeleted": false,
      "authorId": "a074c2d7-bae3-4deb-a660-dba18305c2ee",
      "userId": null,
      "assignees": [],
      "projectId": 2,
      "boardId": 9,
      "boardColumnId": 25,
      "locations": [
        {
          "projectId": 2,
          "boardId": 9,
          "boardColumnId": 25
        }
      ],
      "image": null,
      "isPrivate": false,
      "date": null,
      "time": null,
      "dateStart": null,
      "dateEnd": null,
      "timeStart": null,
      "timeEnd": null,
      "startDate": null,
      "startDateTime": null,
      "dueDate": null,
      "dueDateTime": null,
      "createdAt": "2026-01-30T13:40:46Z",
      "updatedAt": "2026-01-30T14:08:36Z",
      "tags": [
        6
      ],
      "subscribers": [
        "a074c2d7-bae3-4deb-a660-dba18305c2ee"
      ],
      "subTasks": [],
      "workloads": [],
      "timeEntries": [],
      "timer": null,
      "customFields": [],
      "attachments": []
    },
    {
      "id": 36,
      "parentId": null,
      "title": "Setup RabbitMQ Cluster",
      "description": null,
      "overdue": 0,
      "duration": null,
      "type": "action",
      "priority": null,
      "isCompleted": false,
      "isDeleted": false,
      "authorId": "a074c2d7-bae3-4deb-a660-dba18305c2ee",
      "userId": null,
      "assignees": [],
      "projectId": 2,
      "boardId": 9,
      "boardColumnId": 25,
      "locations": [
        {
          "projectId": 2,
          "boardId": 9,
          "boardColumnId": 25
        }
      ],
      "image": null,
      "isPrivate": false,
      "date": null,
      "time": null,
      "dateStart": null,
      "dateEnd": null,
      "timeStart": null,
      "timeEnd": null,
      "startDate": null,
      "startDateTime": null,
      "dueDate": null,
      "dueDateTime": null,
      "createdAt": "2026-01-30T13:40:39Z",
      "updatedAt": "2026-01-30T14:08:32Z",
      "tags": [],
      "subscribers": [
        "a074c2d7-bae3-4deb-a660-dba18305c2ee"
      ],
      "subTasks": [],
      "workloads": [],
      "timeEntries": [],
      "timer": null,
      "customFields": [],
      "attachments": []
    },
    {
      "id": 19,
      "parentId": null,
      "title": "Data Validation Schemas",
      "description": "<p></p>",
      "overdue": 0,
      "duration": null,
      "type": "action",
      "priority": null,
      "isCompleted": true,
      "isDeleted": false,
      "authorId": "a074c2d7-bae3-4deb-a660-dba18305c2ee",
      "userId": null,
      "assignees": [],
      "projectId": 2,
      "boardId": 10,
      "boardColumnId": 30,
      "locations": [
        {
          "projectId": 2,
          "boardId": 10,
          "boardColumnId": 30
        }
      ],
      "image": null,
      "isPrivate": false,
      "date": null,
      "time": null,
      "dateStart": null,
      "dateEnd": null,
      "timeStart": null,
      "timeEnd": null,
      "startDate": null,
      "startDateTime": null,
      "dueDate": null,
      "dueDateTime": null,
      "createdAt": "2026-01-30T13:18:34Z",
      "updatedAt": "2026-01-30T13:34:21Z",
      "tags": [],
      "subscribers": [
        "a074c2d7-bae3-4deb-a660-dba18305c2ee"
      ],
      "subTasks": [],
      "workloads": [],
      "timeEntries": [],
      "timer": null,
      "customFields": [],
      "attachments": []
    },
    {
      "id": 18,
      "parentId": null,
      "title": "Ingestion API Endpoint",
      "description": null,
      "overdue": 0,
      "duration": null,
      "type": "action",
      "priority": null,
      "isCompleted": true,
      "isDeleted": false,
      "authorId": "a074c2d7-bae3-4deb-a660-dba18305c2ee",
      "userId": null,
      "assignees": [],
      "projectId": 2,
      "boardId": 10,
      "boardColumnId": 30,
      "locations": [
        {
          "projectId": 2,
          "boardId": 10,
          "boardColumnId": 30
        }
      ],
      "image": null,
      "isPrivate": false,
      "date": null,
      "time": null,
      "dateStart": null,
      "dateEnd": null,
      "timeStart": null,
      "timeEnd": null,
      "startDate": null,
      "startDateTime": null,
      "dueDate": null,
      "dueDateTime": null,
      "createdAt": "2026-01-30T13:18:33Z",
      "updatedAt": "2026-01-30T13:18:33Z",
      "tags": [],
      "subscribers": [
        "a074c2d7-bae3-4deb-a660-dba18305c2ee"
      ],
      "subTasks": [],
      "workloads": [],
      "timeEntries": [],
      "timer": null,
      "customFields": [],
      "attachments": []
    },
    {
      "id": 17,
      "parentId": null,
      "title": "Adaptive Scheduling Logic",
      "description": null,
      "overdue": 0,
      "duration": null,
      "type": "action",
      "priority": null,
      "isCompleted": false,
      "isDeleted": false,
      "authorId": "a074c2d7-bae3-4deb-a660-dba18305c2ee",
      "userId": null,
      "assignees": [],
      "projectId": 2,
      "boardId": 10,
      "boardColumnId": 28,
      "locations": [
        {
          "projectId": 2,
          "boardId": 10,
          "boardColumnId": 28
        }
      ],
      "image": null,
      "isPrivate": false,
      "date": null,
      "time": null,
      "dateStart": null,
      "dateEnd": null,
      "timeStart": null,
      "timeEnd": null,
      "startDate": null,
      "startDateTime": null,
      "dueDate": null,
      "dueDateTime": null,
      "createdAt": "2026-01-30T13:18:32Z",
      "updatedAt": "2026-01-30T13:18:32Z",
      "tags": [],
      "subscribers": [
        "a074c2d7-bae3-4deb-a660-dba18305c2ee"
      ],
      "subTasks": [],
      "workloads": [],
      "timeEntries": [],
      "timer": null,
      "customFields": [],
      "attachments": []
    },
    {
      "id": 16,
      "parentId": null,
      "title": "Proxy Rotation Middleware",
      "description": null,
      "overdue": 0,
      "duration": null,
      "type": "action",
      "priority": null,
      "isCompleted": false,
      "isDeleted": false,
      "authorId": "a074c2d7-bae3-4deb-a660-dba18305c2ee",
      "userId": null,
      "assignees": [],
      "projectId": 2,
      "boardId": 10,
      "boardColumnId": 28,
      "locations": [
        {
          "projectId": 2,
          "boardId": 10,
          "boardColumnId": 28
        }
      ],
      "image": null,
      "isPrivate": false,
      "date": null,
      "time": null,
      "dateStart": null,
      "dateEnd": null,
      "timeStart": null,
      "timeEnd": null,
      "startDate": null,
      "startDateTime": null,
      "dueDate": null,
      "dueDateTime": null,
      "createdAt": "2026-01-30T13:18:31Z",
      "updatedAt": "2026-01-30T13:18:31Z",
      "tags": [],
      "subscribers": [
        "a074c2d7-bae3-4deb-a660-dba18305c2ee"
      ],
      "subTasks": [],
      "workloads": [],
      "timeEntries": [],
      "timer": null,
      "customFields": [],
      "attachments": []
    }
  ],
  "workspaceId": "911018",
  "members": {
    "a074c2d7-bae3-4deb-a660-dba18305c2ee": {
      "logo": "https://storage.weeek.net/images/a0/f5/a0f5c526-81fc-4a22-97e9-5bd6f610de64/original.png",
      "firstName": "Artem Konukhov",
      "lastName": null
    }
  },
  "columns": {
    "25": "To Do",
    "26": "In Progress",
    "27": "Done",
    "28": "To Be Do",
    "29": "In Progress",
    "30": "Done",
    "31": "To Do",
    "32": "In Progress",
    "33": "Done",
    "34": "To Do",
    "35": "In Progress",
    "36": "Done",
    "49": "To Do",
    "50": "In Progress",
    "51": "Done",
    "55": "To Do",
    "56": "In Progress",
    "57": "Done"
  },
  "tags": [
    {
      "id": 1,
      "title": "Arch",
      "color": "#0231E8"
    },
    {
      "id": 2,
      "title": "Parsing",
      "color": "#0231E8"
    },
    {
      "id": 3,
      "title": "Ingestion",
      "color": "#81B1FF"
    },
    {
      "id": 4,
      "title": "AI",
      "color": "#02BCD4"
    },
    {
      "id": 5,
      "title": "Auth",
      "color": "#F9D900"
    },
    {
      "id": 6,
      "title": "Infrastructure",
      "color": "#BF55EC"
    },
    {
      "id": 7,
      "title": "GUTG",
      "color": "#FF4081"
    }
  ]
};
