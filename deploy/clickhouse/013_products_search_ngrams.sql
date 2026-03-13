ALTER TABLE products_search
    ADD COLUMN IF NOT EXISTS title_lc String MATERIALIZED lower(title);

ALTER TABLE products_search
    ADD INDEX IF NOT EXISTS title_ngram title_lc TYPE ngrambf_v1(3, 256, 2, 0) GRANULARITY 4;
