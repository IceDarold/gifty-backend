CREATE TABLE IF NOT EXISTS analytics_events
(
  event_id String,
  occurred_at DateTime,
  event_type String,
  metric String,
  scope String,
  scope_key String,
  dims_json String,
  payload_json String,
  value Float64,
  version UInt64
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toDate(occurred_at)
ORDER BY (event_id, metric);
