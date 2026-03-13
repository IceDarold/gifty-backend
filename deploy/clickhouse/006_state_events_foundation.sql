CREATE TABLE IF NOT EXISTS state_events_raw (
  event_id String,
  aggregate_type String,
  aggregate_id String,
  event_type String,
  payload_json String,
  occurred_at DateTime64(3, 'UTC'),
  version UInt64,
  op LowCardinality(String),
  source LowCardinality(String) DEFAULT 'outbox'
) ENGINE = ReplacingMergeTree(version)
PARTITION BY toDate(occurred_at)
ORDER BY (aggregate_type, aggregate_id, event_id);

CREATE TABLE IF NOT EXISTS sync_state (
  sync_name String,
  last_bootstrap_at DateTime64(3, 'UTC'),
  last_bootstrap_version UInt64,
  last_event_applied_at DateTime64(3, 'UTC'),
  last_event_id String,
  lag_seconds Float64
) ENGINE = ReplacingMergeTree(last_bootstrap_version)
ORDER BY (sync_name);

CREATE TABLE IF NOT EXISTS sources_latest (
  source_id UInt64,
  site_key String,
  payload_json String,
  version UInt64,
  deleted UInt8
) ENGINE = ReplacingMergeTree(version)
ORDER BY (source_id);

CREATE TABLE IF NOT EXISTS subscribers_latest (
  subscriber_id UInt64,
  chat_id Int64,
  payload_json String,
  version UInt64,
  deleted UInt8
) ENGINE = ReplacingMergeTree(version)
ORDER BY (subscriber_id);

CREATE TABLE IF NOT EXISTS settings_runtime_latest (
  setting_key String,
  payload_json String,
  version UInt64,
  deleted UInt8
) ENGINE = ReplacingMergeTree(version)
ORDER BY (setting_key);

CREATE TABLE IF NOT EXISTS frontend_apps_latest (
  app_id UInt64,
  app_key String,
  payload_json String,
  version UInt64,
  deleted UInt8
) ENGINE = ReplacingMergeTree(version)
ORDER BY (app_id);

CREATE TABLE IF NOT EXISTS frontend_releases_latest (
  release_id UInt64,
  app_id UInt64,
  payload_json String,
  version UInt64,
  deleted UInt8
) ENGINE = ReplacingMergeTree(version)
ORDER BY (release_id);

CREATE TABLE IF NOT EXISTS frontend_profiles_latest (
  profile_id UInt64,
  profile_key String,
  payload_json String,
  version UInt64,
  deleted UInt8
) ENGINE = ReplacingMergeTree(version)
ORDER BY (profile_id);

CREATE TABLE IF NOT EXISTS frontend_rules_latest (
  rule_id UInt64,
  profile_id UInt64,
  payload_json String,
  version UInt64,
  deleted UInt8
) ENGINE = ReplacingMergeTree(version)
ORDER BY (rule_id);

CREATE TABLE IF NOT EXISTS frontend_allowed_hosts_latest (
  host_id UInt64,
  host String,
  payload_json String,
  version UInt64,
  deleted UInt8
) ENGINE = ReplacingMergeTree(version)
ORDER BY (host_id);


CREATE TABLE IF NOT EXISTS frontend_audit_log_latest (
    log_id UInt64,
    payload_json String,
    version UInt64,
    deleted UInt8 DEFAULT 0
) ENGINE = ReplacingMergeTree(version)
ORDER BY (log_id);


CREATE TABLE IF NOT EXISTS ops_discovery_latest (
    discovery_id UInt64,
    site_key String,
    payload_json String,
    version UInt64,
    deleted UInt8 DEFAULT 0
) ENGINE = ReplacingMergeTree(version)
ORDER BY (site_key, discovery_id);


CREATE TABLE IF NOT EXISTS ops_runs_latest (
    run_id UInt64,
    source_id UInt64,
    payload_json String,
    version UInt64,
    deleted UInt8 DEFAULT 0
) ENGINE = ReplacingMergeTree(version)
ORDER BY (source_id, run_id);


CREATE TABLE IF NOT EXISTS products_latest (
    product_id String,
    merchant String,
    category String,
    title String,
    payload_json String,
    version UInt64,
    deleted UInt8 DEFAULT 0
) ENGINE = ReplacingMergeTree(version)
ORDER BY (merchant, category, product_id);

CREATE TABLE IF NOT EXISTS categories_latest (
    category_id UInt64,
    site_key String,
    name String,
    payload_json String,
    version UInt64,
    deleted UInt8 DEFAULT 0
) ENGINE = ReplacingMergeTree(version)
ORDER BY (site_key, category_id);
