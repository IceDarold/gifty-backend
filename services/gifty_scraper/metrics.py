from prometheus_client import Counter

# Metrics for items scraped
scraped_items_total = Counter(
    "scraped_items_total",
    "Total number of items scraped",
    ["spider", "item_type"] # item_type: product, category
)

# Metrics for ingestion status
ingestion_batches_total = Counter(
    "ingestion_batches_total",
    "Total number of batches sent to Core API",
    ["spider", "status"] # status: success, error
)

ingestion_items_total = Counter(
    "ingestion_items_total",
    "Total number of items successfully ingested",
    ["spider"]
)
