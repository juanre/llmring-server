-- Migration: Add conversation templates
-- Description: Add table for conversation templates functionality

-- Create conversation_templates table
CREATE TABLE IF NOT EXISTS {{tables.conversation_templates}} (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID,  -- NULL for global templates
    name VARCHAR(255) NOT NULL,
    description TEXT,
    system_prompt TEXT,
    model VARCHAR(255) NOT NULL DEFAULT 'claude-3-sonnet-20240229',
    temperature DECIMAL(3, 2) NOT NULL DEFAULT 0.7 CHECK (temperature >= 0 AND temperature <= 2),
    max_tokens INTEGER CHECK (max_tokens > 0),
    tool_config JSONB NOT NULL DEFAULT '{}',
    created_by VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    usage_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_conversation_templates_project_id ON {{tables.conversation_templates}}(project_id);
CREATE INDEX IF NOT EXISTS idx_conversation_templates_created_by ON {{tables.conversation_templates}}(created_by);
CREATE INDEX IF NOT EXISTS idx_conversation_templates_is_active ON {{tables.conversation_templates}}(is_active);
CREATE INDEX IF NOT EXISTS idx_conversation_templates_usage_count ON {{tables.conversation_templates}}(usage_count DESC);
CREATE INDEX IF NOT EXISTS idx_conversation_templates_name ON {{tables.conversation_templates}}(name);

-- Add trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION {{schema}}.update_conversation_templates_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_conversation_templates_updated_at
    BEFORE UPDATE ON {{tables.conversation_templates}}
    FOR EACH ROW
    EXECUTE FUNCTION {{schema}}.update_conversation_templates_updated_at();
