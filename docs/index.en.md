# Welcome to Gifty Engineering Docs 🎁

This portal contains all technical documentation for the **Gifty** project — a smart gift recommendation platform. We aggregate product data from popular platforms, analyze it using AI, and provide a user-friendly interface for discovery.

---

## 🧭 Fast Navigation

| Section | Description | Link |
| :--- | :--- | :--- |
| :material-rocket-launch: **Onboarding** | Step-by-step plan for new members: access, chats, first tasks. | [Open →](onboarding/quick_start.md) |
| :material-application-cog: **Local Setup** | Boot up the entire system (Docker, API, Bot) in 5 minutes. | [Open →](onboarding/local_setup.md) |
| :material-graph: **Architecture** | High-level overview of how data turns into recommendations. | [Open →](overview/index.md) |
| :material-database: **Data & DB** | Data domains, PostgreSQL schemas, and migration rules. | [Open →](onboarding/database_work.md) |

---

## 🏗 Core Systems

### 🧠 Recommendation Engine
Our SOTA engine based on **Qwen2-VL** and **Vector Search**. We don't just search for products; we analyze them across 10 psychological axes (GUTG).
👉 [Read more about RecSys →](recommendation/overview.md)

### 🕷 Parsing System
Scalable data collection system using Scrapy and RabbitMQ. Features automatic category mapping and AI validation.
👉 [How parsers work →](parsing/architecture.md)

### 🤖 Telegram Admin Bot
Mission control center. Health monitoring, manual parsing control, and access management.
👉 [Bot guide →](analytics_monitoring/telegram_bot/user_guide.md)

---

## 🧪 Quality & Monitoring

We believe in TDD and Observability:

*   **Testing**: Every feature is covered by `pytest`. [Testing Guide →](onboarding/testing.md)
*   **Analytics**: We track business success via PostHog. [Why do we need analytics? →](analytics_monitoring/dashboard.md)
*   **CI/CD**: Automatic deployment on every push. [Deployment process →](engineering/deployment.md)

---

!!! tip "Any questions?"
    Reach out in Slack `#gifty-dev` or message your mentor. We are always happy to help!

!!! info "Contributing"
    If you find an error in the documentation or want to add a new section, feel free to create a Pull Request!
