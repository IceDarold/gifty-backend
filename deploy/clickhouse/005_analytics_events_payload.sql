ALTER TABLE analytics_events
    ADD COLUMN IF NOT EXISTS payload_json String DEFAULT '{}';
