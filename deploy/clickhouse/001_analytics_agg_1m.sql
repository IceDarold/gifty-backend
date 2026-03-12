CREATE TABLE IF NOT EXISTS analytics_agg_1m
(
  bucket_minute DateTime,
  metric String,
  scope String,
  scope_key String,
  dims_json String,
  cnt UInt64,
  sum_value Float64,
  min_value Float64,
  max_value Float64,
  p50_value Float64,
  p95_value Float64,
  updated_at DateTime,
  version UInt64
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toDate(bucket_minute)
ORDER BY (bucket_minute, metric, scope, scope_key)
TTL bucket_minute + INTERVAL 180 DAY;
