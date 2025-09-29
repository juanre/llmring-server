-- Complete schema for llmring-server with message support
-- Clean implementation with no technical debt

-- =====================================================
-- CORE TABLES: Usage tracking and receipts
-- =====================================================

CREATE TABLE IF NOT EXISTS {{tables.usage_logs}} (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    api_key_id VARCHAR(255),  -- Project key string, NULL for local usage
    model VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    alias VARCHAR(128),
    profile VARCHAR(64) DEFAULT 'default',

    -- Token counts
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cached_input_tokens INTEGER DEFAULT 0,

    -- Cost and performance
    cost DECIMAL(10, 8) NOT NULL,
    latency_ms INTEGER,

    -- Tracking
    origin VARCHAR(255),
    id_at_origin VARCHAR(255),
    conversation_id UUID,  -- Links to conversations if message logging enabled

    -- Metadata
    metadata JSONB DEFAULT '{}'::JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS {{tables.receipts}} (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    receipt_id VARCHAR(255) UNIQUE NOT NULL,
    api_key_id VARCHAR(255),  -- Project key string, NULL for local usage

    -- Model information
    alias VARCHAR(128),
    model VARCHAR(255) NOT NULL,
    profile VARCHAR(64) DEFAULT 'default',
    registry_version VARCHAR(20) NOT NULL,
    lock_digest VARCHAR(128),

    -- Usage data
    tokens JSONB NOT NULL,
    cost JSONB NOT NULL,

    -- Cryptographic proof
    signature TEXT NOT NULL,
    key_id VARCHAR(64),

    -- Tracking
    conversation_id UUID,  -- Links to conversations if message logging enabled
    metadata JSONB DEFAULT '{}'::JSONB,
    receipt_timestamp TIMESTAMP NOT NULL,
    stored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- MESSAGE LOGGING: Optional conversation tracking
-- =====================================================

CREATE TABLE IF NOT EXISTS {{tables.conversations}} (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    api_key_id VARCHAR(255),  -- Project key string, NULL for local usage

    -- Conversation metadata
    title VARCHAR(500),
    system_prompt TEXT,
    model_alias VARCHAR(255),

    -- Configuration
    temperature FLOAT DEFAULT 0.7 CHECK (temperature >= 0 AND temperature <= 2),
    max_tokens INTEGER CHECK (max_tokens > 0),

    -- Tracking
    message_count INTEGER DEFAULT 0,
    total_input_tokens INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    total_cost DECIMAL(10, 8) DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_message_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS {{tables.messages}} (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES {{tables.conversations}}(id) ON DELETE CASCADE,
    receipt_id UUID REFERENCES {{tables.receipts}}(id),  -- Links to receipt for this message

    -- Message content
    role VARCHAR(50) NOT NULL CHECK (role IN ('system', 'user', 'assistant', 'tool')),
    content TEXT,  -- NULL if privacy mode enabled
    content_hash VARCHAR(64),  -- SHA256 hash for deduplication/privacy

    -- Token tracking (for this specific message)
    input_tokens INTEGER,
    output_tokens INTEGER,

    -- Tool use (if applicable)
    tool_calls JSONB,  -- Array of tool calls made
    tool_results JSONB,  -- Results from tool execution

    -- Metadata
    metadata JSONB DEFAULT '{}'::JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- INDEXES for performance
-- =====================================================

-- Usage logs indexes
CREATE INDEX idx_usage_logs_api_key_timestamp ON {{tables.usage_logs}}(api_key_id, created_at DESC);
CREATE INDEX idx_usage_logs_origin ON {{tables.usage_logs}}(origin, created_at DESC);
CREATE INDEX idx_usage_logs_model ON {{tables.usage_logs}}(model, created_at DESC);
CREATE INDEX idx_usage_logs_api_key_profile ON {{tables.usage_logs}}(api_key_id, profile, created_at DESC);
CREATE INDEX idx_usage_logs_alias ON {{tables.usage_logs}}(alias, created_at DESC);
CREATE INDEX idx_usage_logs_conversation ON {{tables.usage_logs}}(conversation_id) WHERE conversation_id IS NOT NULL;

-- Receipts indexes
CREATE INDEX idx_receipts_api_key ON {{tables.receipts}}(api_key_id);
CREATE INDEX idx_receipts_receipt_id ON {{tables.receipts}}(receipt_id);
CREATE INDEX idx_receipts_conversation ON {{tables.receipts}}(conversation_id) WHERE conversation_id IS NOT NULL;

-- Conversations indexes
CREATE INDEX idx_conversations_api_key ON {{tables.conversations}}(api_key_id, created_at DESC);
CREATE INDEX idx_conversations_updated ON {{tables.conversations}}(updated_at DESC);

-- Messages indexes
CREATE INDEX idx_messages_conversation ON {{tables.messages}}(conversation_id, timestamp);
CREATE INDEX idx_messages_receipt ON {{tables.messages}}(receipt_id) WHERE receipt_id IS NOT NULL;
CREATE INDEX idx_messages_content_hash ON {{tables.messages}}(content_hash) WHERE content_hash IS NOT NULL;

-- =====================================================
-- TRIGGERS for automatic updates
-- =====================================================

CREATE OR REPLACE FUNCTION {{schema}}.update_conversation_stats()
RETURNS TRIGGER AS $$
BEGIN
    -- Update conversation statistics when a message is added
    UPDATE {{tables.conversations}}
    SET
        message_count = message_count + 1,
        total_input_tokens = total_input_tokens + COALESCE(NEW.input_tokens, 0),
        total_output_tokens = total_output_tokens + COALESCE(NEW.output_tokens, 0),
        last_message_at = NEW.timestamp,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.conversation_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_conversation_on_message
AFTER INSERT ON {{tables.messages}}
FOR EACH ROW
EXECUTE FUNCTION {{schema}}.update_conversation_stats();

-- =====================================================
-- FUNCTIONS for common operations
-- =====================================================

-- Function to get conversation with messages
CREATE OR REPLACE FUNCTION {{schema}}.get_conversation_with_messages(
    p_conversation_id UUID,
    p_limit INTEGER DEFAULT 100
)
RETURNS TABLE (
    conversation JSONB,
    messages JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        to_jsonb(c.*) as conversation,
        COALESCE(
            jsonb_agg(
                jsonb_build_object(
                    'id', m.id,
                    'role', m.role,
                    'content', m.content,
                    'timestamp', m.timestamp,
                    'tokens', jsonb_build_object(
                        'input', m.input_tokens,
                        'output', m.output_tokens
                    )
                ) ORDER BY m.timestamp
            ) FILTER (WHERE m.id IS NOT NULL),
            '[]'::jsonb
        ) as messages
    FROM {{tables.conversations}} c
    LEFT JOIN LATERAL (
        SELECT * FROM {{tables.messages}}
        WHERE conversation_id = p_conversation_id
        ORDER BY timestamp DESC
        LIMIT p_limit
    ) m ON true
    WHERE c.id = p_conversation_id
    GROUP BY c.id;
END;
$$ LANGUAGE plpgsql;

-- Function to clean up old messages (for retention policy)
CREATE OR REPLACE FUNCTION {{schema}}.cleanup_old_messages(
    p_retention_days INTEGER DEFAULT 30
)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM {{tables.messages}}
    WHERE timestamp < CURRENT_TIMESTAMP - (p_retention_days || ' days')::INTERVAL
    RETURNING COUNT(*) INTO deleted_count;

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;
