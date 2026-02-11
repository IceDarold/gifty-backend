# 🕹 API Playground

Здесь вы можете выполнять запросы к API прямо из браузера.

!!! warning "CORS & Localhost"
    Для работы с **Localhost** убедитесь, что ваш бекенд запущен (`make run` или `docker compose up`) и доступен по адресу `http://localhost:8000`.
    Если вы видите ошибку "Failed to load", скорее всего, сервер не запущен или заблокирован CORS.

<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui.css" />
<style>
    .swagger-ui .topbar { display: none; } /* Скрываем верхнюю панель, т.к. мы управляем URL через конфиг */
    .swagger-ui .wrapper { padding: 0; }
</style>

<div id="swagger-ui"></div>

<script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-bundle.js" crossorigin></script>
<script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-standalone-preset.js" crossorigin></script>

<script>
window.onload = function() {
  const ui = SwaggerUIBundle({
    urls: [
      {url: "http://localhost:8000/openapi.json", name: "🔒 Localhost (Dev)"},
      {url: "https://api.giftyai.ru/openapi.json", name: "🌍 Production"}
    ],
    dom_id: '#swagger-ui',
    deepLinking: true,
    presets: [
      SwaggerUIBundle.presets.apis,
      SwaggerUIStandalonePreset
    ],
    plugins: [
      SwaggerUIBundle.plugins.DownloadUrl
    ],
    layout: "StandaloneLayout",
    persistAuthorization: true
  });
  window.ui = ui;
};
</script>
