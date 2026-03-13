CREATE TABLE IF NOT EXISTS llm_calls_search
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
ORDER BY (created_at, provider, model, status, call_type, session_id, event_id);

CREATE MATERIALIZED VIEW IF NOT EXISTS llm_calls_search_mv
TO llm_calls_search AS
SELECT
  event_id,
  created_at,
  provider,
  model,
  call_type,
  status,
  latency_ms,
  total_tokens,
  prompt_tokens,
  completion_tokens,
  cost_usd,
  session_id,
  prompt_hash,
  payload_json,
  version
FROM llm_calls;
