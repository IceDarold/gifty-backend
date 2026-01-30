# Gifty Recommendation System Architecture

This document describes the State-of-the-Art (SOTA) recommendation engine powered by Vision-Language Models (VLM) and Vector Search.

## 1. System Overview
The Gifty recommendation system transforms raw product data into high-quality gift suggestions by combining semantic search with a multi-dimensional psychological evaluation.

## 2. Core Components

### A. Data Ingestion (Catalog Sync)
- **Source**: TakProdam API.
- **Process**: Fetches products, cleans metadata, and persists them into a PostgreSQL database.
- **Deduplication**: Uses `content_hash` to avoid redundant processing of the same product data.

### B. Vector Embeddings (Stage 3)
- **Model**: `BAAI/bge-m3` (Multi-lingual, High-dimensional).
- **Function**: Converts product titles and descriptions into 1024-dimensional vectors.
- **Storage**: `product_embeddings` table with `pgvector` HNSW indices for ultra-fast cosine similarity search.

### C. Gifty 10-Dimensions Matrix (The Gifty DNA)
Instead of a binary "gift / not gift" flag, every product is evaluated by a **Qwen2-VL** model across 10 psychological axes (stored in `llm_gift_vector` JSONB):
1.  **Wow-Factor**: Surprise and delight level.
2.  **Warmth**: Emotional temperature (Handcrafted vs. Tech).
3.  **Romance**: Suitability for intimate relationships.
4.  **Practicality**: Utility value vs. purely aesthetic.
5.  **Usage Frequency**: Daily driver vs. seasonal/niche.
6.  **Occasion Versatility**: How universal is the gift (Birthday vs. Wedding).
7.  **Aesthetics**: Visual perception of quality and premium feel.
8.  **Social Risk**: Danger of missing the mark or awkwardness.
9.  **Age Suitability**: Multi-segment distribution.
10. **Gender Bias**: Masculine, Feminine, or Unisex.

## 3. The Recommendation Pipeline

### Step 1: User Profile (Quiz)
The user answers a quiz determining the recipient's age, interests, vibes, and relationship type.

### Step 2: Semantic Retrieval
The system generates a query vector from the quiz answers and performs a **vector search** against the product catalog to find items that are semantically relevant.

### Step 3: Psychological Filtering
Items are filtered and scored based on the 10-D Matrix. For example:
- If the relationship is "Professional", products with high **Romance** are penalized.
- If the vibe is "Practical", products with high **Practicality** are prioritized.

### Step 4: Reranking & Diversity
The final list is reranked to ensure a diverse mix of categories and price points, preventing a "unanimous" list (e.g., only showing 10 different types of socks).

## 4. Technical Stack
- **Backend**: FastAPI (Python 3.11+).
- **Database**: PostgreSQL + `pgvector`.
- **Cache/Queue**: Redis.
- **VLM Workers**: `Qwen2-VL-7B` running on GPU environments (Kaggle/Colab or dedicated GPU servers).
- **Deployment**: Dockerized, non-root user for security, Gunicorn + Uvicorn workers.

---
*Last Updated: January 2026*
