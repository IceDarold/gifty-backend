CREATE TABLE IF NOT EXISTS llm_calls_agg_1m
(
  bucket_minute DateTime,
  provider LowCardinality(String),
  model LowCardinality(String),
  call_type LowCardinality(String),
  status LowCardinality(String),
  total UInt64,
  errors UInt64,
  total_cost Float64,
  total_latency Float64,
  latency_count UInt64,
  total_tokens UInt64,
  token_count UInt64,
  p50_latency_state AggregateFunction(quantileTiming, Float64),
  p95_latency_state AggregateFunction(quantileTiming, Float64),
  p50_tokens_state AggregateFunction(quantileTiming, Float64),
  p95_tokens_state AggregateFunction(quantileTiming, Float64)
)
ENGINE = AggregatingMergeTree
PARTITION BY toDate(bucket_minute)
ORDER BY (bucket_minute, provider, model, call_type, status);

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

CREATE MATERIALIZED VIEW IF NOT EXISTS llm_calls_agg_1m_mv
TO llm_calls_agg_1m AS
SELECT
  toStartOfMinute(occurred_at) AS bucket_minute,
  JSONExtractString(dims_json, 'provider') AS provider,
  JSONExtractString(dims_json, 'model') AS model,
  JSONExtractString(dims_json, 'call_type') AS call_type,
  JSONExtractString(dims_json, 'status') AS status,
  countIf(metric = 'llm.call_completed') AS total,
  countIf(metric = 'llm.call_completed' AND JSONExtractString(dims_json, 'status') NOT IN ('ok','success','completed','')) AS errors,
  sumIf(value, metric = 'llm.call_completed.cost_usd') AS total_cost,
  sumIf(value, metric = 'llm.call_completed.latency_ms') AS total_latency,
  countIf(metric = 'llm.call_completed.latency_ms') AS latency_count,
  sumIf(value, metric = 'llm.call_completed.total_tokens') AS total_tokens,
  countIf(metric = 'llm.call_completed.total_tokens') AS token_count,
  quantileTimingStateIf(0.5)(value, metric = 'llm.call_completed.latency_ms') AS p50_latency_state,
  quantileTimingStateIf(0.95)(value, metric = 'llm.call_completed.latency_ms') AS p95_latency_state,
  quantileTimingStateIf(0.5)(value, metric = 'llm.call_completed.total_tokens') AS p50_tokens_state,
  quantileTimingStateIf(0.95)(value, metric = 'llm.call_completed.total_tokens') AS p95_tokens_state
FROM analytics_events
WHERE metric LIKE 'llm.call_completed%'
GROUP BY bucket_minute, provider, model, call_type, status;
