# Weeek Integration API 🔌

The Weeek integration is used for two purposes:
1.  **Internal API**: For deep interaction between the Telegram bot and team tasks.
2.  **Integrations API**: Proxy endpoints for displaying task status directly within this documentation.

---

## 🛠 Internal Weeek API (Telegram Bot)

These endpoints require the `X-Internal-Token` header and are used by the bot to manage the workflow.

### 1. Connect Account (`/connect`)
Binds a Telegram Chat ID to a Weeek API token.

*   **URL**: `/internal/weeek/connect`
*   **Method**: `POST`
*   **Body**:
    ```json
    {
      "telegram_chat_id": 12345678,
      "weeek_api_token": "your_token_here"
    }
    ```

### 2. Task List (`/tasks`)
Retrieves tasks assigned to the user.

*   **URL**: `/internal/weeek/tasks`
*   **Method**: `GET`
*   **Parameters**:
    - `telegram_chat_id`: Telegram Chat ID.
    - `type`: `all`, `today`, `tomorrow`, `overdue`.

---

## 🌐 Integrations API (Public Proxy)

Used by the documentation frontend to embed widgets with live task status.

### 1. Task Proxy (`/weeek/tasks`)
Allows fetching a task list without exposing the API key to the frontend.

*   **URL**: `/api/v1/integrations/weeek/tasks`
*   **Method**: `GET`
*   **Parameters**: `projectId`, `boardId`, `tagNames`.
