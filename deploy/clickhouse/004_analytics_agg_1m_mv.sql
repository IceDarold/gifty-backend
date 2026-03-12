CREATE MATERIALIZED VIEW IF NOT EXISTS analytics_agg_1m_mv
TO analytics_agg_1m
AS
SELECT
  toStartOfMinute(occurred_at) AS bucket_minute,
  metric,
  scope,
  scope_key,
  dims_json,
  count() AS cnt,
  sum(value) AS sum_value,
  min(value) AS min_value,
  max(value) AS max_value,
  quantile(0.5)(value) AS p50_value,
  quantile(0.95)(value) AS p95_value,
  max(occurred_at) AS updated_at,
  max(version) AS version
FROM analytics_events
GROUP BY bucket_minute, metric, scope, scope_key, dims_json;
