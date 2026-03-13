CREATE TABLE IF NOT EXISTS products_search
(
  product_id String,
  merchant String,
  category String,
  title String,
  payload_json String,
  version UInt64,
  deleted UInt8
)
ENGINE = ReplacingMergeTree(version)
ORDER BY (merchant, category, title, product_id);

CREATE MATERIALIZED VIEW IF NOT EXISTS products_search_mv
TO products_search AS
SELECT
  product_id,
  merchant,
  category,
  title,
  payload_json,
  version,
  deleted
FROM products_latest;
