-- Ensure profile support and indexes; extend receipts schema (idempotent)

ALTER TABLE {{tables.aliases}} ADD COLUMN IF NOT EXISTS profile VARCHAR(64) NOT NULL DEFAULT 'default';

-- Ensure uniqueness on (profile, alias)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE table_name = split_part('{{tables.aliases}}', '.', 2) AND constraint_type = 'UNIQUE' AND constraint_name = 'uniq_alias_project_profile'
    ) THEN
        ALTER TABLE {{tables.aliases}} ADD CONSTRAINT uniq_alias_project_profile UNIQUE (project_id, profile, alias);
    END IF;
END$$;

-- Extend receipts (already present in initial schema, keep idempotent)
ALTER TABLE {{tables.receipts}} ADD COLUMN IF NOT EXISTS alias VARCHAR(128);
ALTER TABLE {{tables.receipts}} ADD COLUMN IF NOT EXISTS profile VARCHAR(64) DEFAULT 'default';
ALTER TABLE {{tables.receipts}} ADD COLUMN IF NOT EXISTS lock_digest VARCHAR(128);
ALTER TABLE {{tables.receipts}} ADD COLUMN IF NOT EXISTS key_id VARCHAR(64);

-- Extend usage logs (ensure alias/profile columns exist)
ALTER TABLE {{tables.usage_logs}} ADD COLUMN IF NOT EXISTS alias VARCHAR(128);
ALTER TABLE {{tables.usage_logs}} ADD COLUMN IF NOT EXISTS profile VARCHAR(64) DEFAULT 'default';

CREATE INDEX IF NOT EXISTS idx_usage_logs_api_key_profile ON {{tables.usage_logs}}(api_key_id, profile, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_logs_alias ON {{tables.usage_logs}}(alias, created_at DESC);


