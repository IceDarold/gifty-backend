# Internal API Reference 🔐

The Internal API is designed for interaction between the core components of the Gifty system: the Admin Dashboard, parsing workers, and the Intelligence scoring system.

These endpoints require high privilege levels and are **not intended** to be called from the public frontend.

## Authentication

All requests to the Internal API must include the access token in the `X-Internal-Token` header.

| Header | Description |
| :--- | :--- |
| `X-Internal-Token` | Secret token defined in settings (`INTERNAL_API_TOKEN`). |

---

## 🕷 Parsing Management (Sources)

### 1. List Sources (`/sources`)
Returns all registered sites and categories for data collection.

*   **URL**: `/internal/sources`
*   **Method**: `GET`
*   **Response**: `List[ParsingSourceSchema]`

### 2. Detailed Info (`/sources/{source_id}`)
Returns full run history, current configuration, and statistics for a specific parser.

*   **URL**: `/internal/sources/{source_id}`
*   **Method**: `GET`
*   **Response**: `ParsingSourceSchema` (including `history` array and `total_items`).

### 3. Force Run (`/{id}/force-run`)
Immediately dispatches a parsing task to RabbitMQ, bypassing the schedule.

*   **URL**: `/internal/sources/{source_id}/force-run`
*   **Method**: `POST`
*   - `strategy` (optional): Strategy override (`discovery` or `deep`).

### 4. Enable/Disable (`/{id}/toggle`)
Activates or deactivates the automatic scheduled execution of a parser.

*   **URL**: `/internal/sources/{source_id}/toggle`
*   **Method**: `POST`
*   **Body**: `{ "is_active": bool }`

---

## 📦 Data Ingestion & Processing

### 1. Ingest Batch (`/ingest-batch`)
The primary endpoint for Scrapy workers to transmit collected products and categories to the main database.

*   **URL**: `/internal/ingest-batch`
*   **Method**: `POST`
*   **Body**: `IngestBatchRequest` (list of items and discovered categories).

### 2. Worker Stats (`/workers`)
Returns a list of currently running Scrapy containers and their current load.

*   **URL**: `/internal/workers`
*   **Method**: `GET`

---

## 🧠 Intelligence & Categorization

### 1. Scoring Tasks (`/scoring/tasks`)
Used by external LLM workers (e.g., in Kaggle/Colab) to fetch products that haven't been scored across the 10 GUTG axes.

*   **URL**: `/internal/scoring/tasks`
*   **Method**: `GET`
*   **Parameters**: `limit` (default: 50).

### 2. Category Mapping Tasks (`/categories/tasks`)
List of "raw" categories discovered by parsers that need to be mapped to Gifty's internal category tree using AI.

*   **URL**: `/internal/categories/tasks`
*   **Method**: `GET`

---

## 🛡 Access & Telegram

### 1. Subscriber Management (`/telegram/subscribers`)
Manage access permissions for Telegram bot users and the Dashboard (roles: `admin`, `superadmin`).

### 2. WebApp Auth (`/webapp/auth`)
Verifies `initData` from the Telegram Mini App for Dashboard login.

*   **URL**: `/internal/webapp/auth`
*   **Method**: `POST`
*   **Body**: `{ "init_data": "..." }`
