CREATE TABLE IF NOT EXISTS analytics_agg_5m
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

CREATE MATERIALIZED VIEW IF NOT EXISTS analytics_agg_5m_mv
TO analytics_agg_5m
AS
SELECT
  toStartOfFiveMinute(bucket_minute) AS bucket_minute,
  metric,
  scope,
  scope_key,
  dims_json,
  sum(cnt) AS cnt,
  sum(sum_value) AS sum_value,
  min(min_value) AS min_value,
  max(max_value) AS max_value,
  max(p50_value) AS p50_value,
  max(p95_value) AS p95_value,
  max(updated_at) AS updated_at,
  max(version) AS version
FROM analytics_agg_1m
GROUP BY bucket_minute, metric, scope, scope_key, dims_json;

CREATE TABLE IF NOT EXISTS analytics_agg_1h
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
TTL bucket_minute + INTERVAL 365 DAY;

CREATE MATERIALIZED VIEW IF NOT EXISTS analytics_agg_1h_mv
TO analytics_agg_1h
AS
SELECT
  toStartOfHour(bucket_minute) AS bucket_minute,
  metric,
  scope,
  scope_key,
  dims_json,
  sum(cnt) AS cnt,
  sum(sum_value) AS sum_value,
  min(min_value) AS min_value,
  max(max_value) AS max_value,
  max(p50_value) AS p50_value,
  max(p95_value) AS p95_value,
  max(updated_at) AS updated_at,
  max(version) AS version
FROM analytics_agg_1m
GROUP BY bucket_minute, metric, scope, scope_key, dims_json;
