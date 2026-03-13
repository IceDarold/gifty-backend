ALTER TABLE sync_state
    ADD COLUMN IF NOT EXISTS last_backfill_at Nullable(DateTime64(3, 'UTC'))
    AFTER last_bootstrap_at;
