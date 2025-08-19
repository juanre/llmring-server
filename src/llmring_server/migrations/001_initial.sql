-- Initial schema for llmring-server (simplified, project-key based)

-- Use 'project_id' instead of API key table
CREATE TABLE IF NOT EXISTS {{tables.usage_logs}} (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    api_key_id VARCHAR(255) NOT NULL, -- project_id in this simplified server
    model VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cached_input_tokens INTEGER DEFAULT 0,
    cost DECIMAL(10, 8) NOT NULL,
    latency_ms INTEGER,
    origin VARCHAR(255),
    id_at_origin VARCHAR(255),
    metadata JSONB DEFAULT '{}'::JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    alias VARCHAR(128),
    profile VARCHAR(64) DEFAULT 'default'
);

CREATE INDEX idx_usage_logs_api_key_timestamp ON {{tables.usage_logs}}(api_key_id, created_at DESC);
CREATE INDEX idx_usage_logs_origin ON {{tables.usage_logs}}(origin, created_at DESC);
CREATE INDEX idx_usage_logs_model ON {{tables.usage_logs}}(model, created_at DESC);
CREATE INDEX idx_usage_logs_api_key_profile ON {{tables.usage_logs}}(api_key_id, profile, created_at DESC);
CREATE INDEX idx_usage_logs_alias ON {{tables.usage_logs}}(alias, created_at DESC);

-- Aliases per project
CREATE TABLE IF NOT EXISTS {{tables.aliases}} (
    id SERIAL PRIMARY KEY,
    project_id VARCHAR(255) NOT NULL,
    profile VARCHAR(64) NOT NULL DEFAULT 'default',
    alias VARCHAR(64) NOT NULL,
    model VARCHAR(255) NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, profile, alias)
);

CREATE INDEX idx_aliases_project ON {{tables.aliases}}(project_id);
CREATE INDEX idx_aliases_project_profile ON {{tables.aliases}}(project_id, profile);

CREATE TABLE IF NOT EXISTS {{tables.receipts}} (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    receipt_id VARCHAR(255) UNIQUE NOT NULL,
    api_key_id VARCHAR(255) NOT NULL,
    registry_version VARCHAR(20) NOT NULL,
    model VARCHAR(255) NOT NULL,
    tokens JSONB NOT NULL,
    cost JSONB NOT NULL,
    signature TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::JSONB,
    receipt_timestamp TIMESTAMP NOT NULL,
    stored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    alias VARCHAR(128),
    profile VARCHAR(64) DEFAULT 'default',
    lock_digest VARCHAR(128),
    key_id VARCHAR(64)
);

CREATE INDEX idx_receipts_api_key ON {{tables.receipts}}(api_key_id);
CREATE INDEX idx_receipts_receipt_id ON {{tables.receipts}}(receipt_id);

-- Registry tables removed in v3.2; registry is fetched from GitHub Pages

