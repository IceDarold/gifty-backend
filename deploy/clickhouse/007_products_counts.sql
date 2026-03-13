CREATE TABLE IF NOT EXISTS products_count_by_site (
    site_key String,
    cnt UInt64,
    updated_at DateTime
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY site_key;
