# API Reference Overview 🚀

Welcome to the Gifty Technical API Reference. Our system is built using a layered architecture, where each component has a clear area of responsibility.

## Interaction Architecture

```mermaid
graph TD
    UI[Frontend / Dashboard] --> API[API Layer]
    Bot[Telegram Bot] --> API
    Workers[Scrapy Workers] --> InternalAPI[Internal API]

    subgraph "Backend Core"
        API --> Services[Services Layer]
        InternalAPI --> Services
        Services --> Repositories[Repositories Layer]
        Repositories --> DB[(PostgreSQL + pgvector)]
        Models[Data Models] -.-> API
        Models -.-> Services
    end

    subgraph "External Systems"
        Services --> Weeek[Weeek CRM]
        API --> PostHog[PostHog Analytics]
    end
```

---

## Documentation Sections

### 🕹 [API Playground](playground.md)
Interactive Swagger UI console for testing endpoints in the browser (Localhost / Production).

### 📦 [Data Models](models.md)
Description of Pydantic schemas and SQLAlchemy models. This section defines the data structures transferred between frontend and backend, as well as how they are stored in the database.

### ⚙️ [Services](services.md)
The system's business logic. Services coordinate the work of repositories and external integrations to solve high-level tasks (e.g., product ingestion flow or recommendation logic).

### 🗄 [Repositories](repositories.md)
The data access layer. Direct interaction with the database via SQLAlchemy. Repositories encapsulate complex SQL queries and vector searches.

### 🌐 [Public API](public.md)
Interfaces for the external frontend: feedback forms (leads), team lists, and recommendation generation.

### 🔌 [Integrations & Weeek](weeek.md)
Integration with Weeek for task management: internal endpoints for the bot and public proxies for documentation.

### 🛡️ [Auth API](auth.md)
Session management and login via OAuth 2.0 (Google, Yandex, VK).

### 📊 [Analytics API](analytics.md)
A secure proxy layer for retrieving product metrics from PostHog and technical data from Prometheus/Loki.

### 🔐 [Internal API](internal.md)
Interfaces for internal needs: worker management, manual parser execution, product batch ingestion, and AI scoring tasks.

---

!!! info "Auto-generation"
    Most of this section is automatically generated from Python docstrings using `mkdocstrings`.
