# 🕹 API Playground

Здесь вы можете выполнять запросы к API прямо из браузера.

!!! warning "CORS & Localhost"
    Для работы с **Localhost** убедитесь, что ваш бекенд запущен (`make run` или `docker compose up`) и доступен по адресу `http://localhost:8000`.
    Если вы видите ошибку "Failed to load", скорее всего, сервер не запущен или заблокирован CORS.

<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui.css" />
<style>
    .swagger-ui .topbar { display: none; }
    .swagger-ui .wrapper { padding: 0; }
    
    .backend-selector {
        background: #f5f5f5;
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 20px;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    
    .backend-selector h3 {
        margin: 0 0 12px 0;
        font-size: 16px;
        color: #333;
    }
    
    .backend-input-group {
        display: flex;
        gap: 8px;
        align-items: center;
    }
    
    .backend-input-group input {
        flex: 1;
        padding: 8px 12px;
        border: 1px solid #ccc;
        border-radius: 4px;
        font-size: 14px;
    }
    
    .backend-input-group button {
        padding: 8px 16px;
        background: #4051b5;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-size: 14px;
        font-weight: 500;
    }
    
    .backend-input-group button:hover {
        background: #303f9f;
    }
    
    .preset-buttons {
        display: flex;
        gap: 8px;
        margin-top: 8px;
    }
    
    .preset-buttons button {
        padding: 6px 12px;
        background: white;
        border: 1px solid #ccc;
        border-radius: 4px;
        cursor: pointer;
        font-size: 13px;
    }
    
    .preset-buttons button:hover {
        background: #f0f0f0;
    }
</style>

<div class="backend-selector">
    <h3>🔧 Backend URL</h3>
    <div class="backend-input-group">
        <input 
            type="text" 
            id="backend-url-input" 
            placeholder="https://api.giftyai.ru" 
            value="https://api.giftyai.ru"
        />
        <button onclick="loadSwagger()">Load API</button>
    </div>
    <div class="preset-buttons">
        <button onclick="setBackendUrl('https://api.giftyai.ru')">🌍 Production</button>
        <button onclick="setBackendUrl('http://localhost:8000')">🔒 Localhost</button>
    </div>
</div>

<div id="swagger-ui"></div>

<script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-bundle.js" crossorigin></script>
<script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-standalone-preset.js" crossorigin></script>

<script>
let ui = null;

// Load saved backend URL from localStorage or use default
function getBackendUrl() {
    return localStorage.getItem('api-playground-backend') || 'https://api.giftyai.ru';
}

// Save backend URL to localStorage
function saveBackendUrl(url) {
    localStorage.setItem('api-playground-backend', url);
}

// Set backend URL in input field
function setBackendUrl(url) {
    document.getElementById('backend-url-input').value = url;
    saveBackendUrl(url);
    loadSwagger();
}

// Load Swagger UI with current backend URL
function loadSwagger() {
    const backendUrl = document.getElementById('backend-url-input').value.trim();
    
    if (!backendUrl) {
        alert('Please enter a valid backend URL');
        return;
    }
    
    // Remove trailing slash if present
    const cleanUrl = backendUrl.replace(/\/$/, '');
    saveBackendUrl(cleanUrl);
    
    // Clear previous instance
    document.getElementById('swagger-ui').innerHTML = '';
    
    // Initialize Swagger UI
    ui = SwaggerUIBundle({
        url: `${cleanUrl}/openapi.json`,
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
        persistAuthorization: true,
        onComplete: function() {
            console.log('Swagger UI loaded successfully for:', cleanUrl);
        },
        onFailure: function(error) {
            console.error('Failed to load Swagger UI:', error);
            alert(`Failed to load API from ${cleanUrl}. Check console for details.`);
        }
    });
    
    window.ui = ui;
}

// Initialize on page load
window.onload = function() {
    const savedUrl = getBackendUrl();
    document.getElementById('backend-url-input').value = savedUrl;
    loadSwagger();
    
    // Allow Enter key to trigger load
    document.getElementById('backend-url-input').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            loadSwagger();
        }
    });
};
</script>
