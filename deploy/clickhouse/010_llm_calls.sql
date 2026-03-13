CREATE TABLE IF NOT EXISTS llm_calls
(
  event_id String,
  created_at DateTime64(3, 'UTC'),
  provider LowCardinality(String),
  model LowCardinality(String),
  call_type LowCardinality(String),
  status LowCardinality(String),
  latency_ms Float64,
  total_tokens UInt64,
  prompt_tokens UInt64,
  completion_tokens UInt64,
  cost_usd Float64,
  session_id String,
  prompt_hash String,
  payload_json String,
  version UInt64
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toDate(created_at)
ORDER BY (event_id);
