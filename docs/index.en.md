# Welcome to Gifty Engineering 🎁

This portal contains all technical documentation for the **Gifty** project — a smart gift recommendation platform.

## About the Project

Gifty helps users find perfect gifts using modern machine learning and vector search algorithms. We aggregate product data from popular platforms, analyze it using AI, and provide a user-friendly interface for discovery.

## Navigation

*   **[Architecture](architecture/overview.md)**: How everything works under the hood — from parsing to recommendations.
*   **[API Reference](api/services.md)**: Automatically generated Python class and function references.
*   **[Guides](guides/onboarding.md)**: Environment setup, development rules, and deployment instructions.

## Quick Start for Developers

1.  Clone the repository.
2.  Create a virtual environment: `python -m venv .venv`
3.  Install dependencies: `pip install -r requirements.txt`
4.  Configure the `.env` file (template in `.env.example`).
5.  Start the backend: `uvicorn app.main:app --reload`

---

> [!NOTE]
> If you find an error in the documentation or want to add a new section, feel free to create a Pull Request!
