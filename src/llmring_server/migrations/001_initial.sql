-- Initial schema for llmring-server (simplified, project-key based)

CREATE TABLE IF NOT EXISTS {{tables.llm_models}} (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,
    model_name VARCHAR(255) NOT NULL,
    display_name VARCHAR(255),
    description TEXT,
    max_context INTEGER,
    max_output_tokens INTEGER,
    supports_vision BOOLEAN DEFAULT FALSE,
    supports_function_calling BOOLEAN DEFAULT FALSE,
    supports_json_mode BOOLEAN DEFAULT FALSE,
    supports_parallel_tool_calls BOOLEAN DEFAULT FALSE,
    tool_call_format VARCHAR(50),
    dollars_per_million_tokens_input DECIMAL(10, 6),
    dollars_per_million_tokens_output DECIMAL(10, 6),
    inactive_from TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provider, model_name)
);

CREATE INDEX idx_llm_models_provider ON {{tables.llm_models}}(provider);
CREATE INDEX idx_llm_models_active ON {{tables.llm_models}}(inactive_from);
CREATE INDEX idx_llm_models_provider_model ON {{tables.llm_models}}(provider, model_name);

CREATE TABLE IF NOT EXISTS {{tables.registry_versions}} (
    version VARCHAR(20) PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    models_snapshot JSONB NOT NULL,
    changelog JSONB,
    signature TEXT,
    github_release_url TEXT
);

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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_usage_logs_api_key_timestamp ON {{tables.usage_logs}}(api_key_id, created_at DESC);
CREATE INDEX idx_usage_logs_origin ON {{tables.usage_logs}}(origin, created_at DESC);
CREATE INDEX idx_usage_logs_model ON {{tables.usage_logs}}(model, created_at DESC);

-- Aliases per project
CREATE TABLE IF NOT EXISTS {{tables.aliases}} (
    id SERIAL PRIMARY KEY,
    project_id VARCHAR(255) NOT NULL,
    alias VARCHAR(64) NOT NULL,
    model VARCHAR(255) NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, alias)
);

CREATE INDEX idx_aliases_project ON {{tables.aliases}}(project_id);

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
    stored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_receipts_api_key ON {{tables.receipts}}(api_key_id);
CREATE INDEX idx_receipts_receipt_id ON {{tables.receipts}}(receipt_id);

CREATE TABLE IF NOT EXISTS {{tables.changelog}} (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version VARCHAR(20) NOT NULL,
    change_date DATE NOT NULL,
    change_type VARCHAR(50) NOT NULL,
    model VARCHAR(255),
    field VARCHAR(100),
    old_value TEXT,
    new_value TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_changelog_version ON {{tables.changelog}}(version);
CREATE INDEX idx_changelog_model ON {{tables.changelog}}(model);


