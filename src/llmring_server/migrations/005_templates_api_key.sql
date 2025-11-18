-- Migration: Change templates to use api_key_id instead of project_id
-- Description: Align templates table with other tables (MCP, conversations, usage) for consistent authentication

-- Rename project_id column to api_key_id and change type from UUID to VARCHAR(255)
ALTER TABLE {{tables.conversation_templates}}
    ALTER COLUMN project_id TYPE VARCHAR(255) USING project_id::text;

ALTER TABLE {{tables.conversation_templates}}
    RENAME COLUMN project_id TO api_key_id;

-- Update index to match new column name
DROP INDEX IF EXISTS idx_conversation_templates_project_id;
CREATE INDEX IF NOT EXISTS idx_conversation_templates_api_key_id ON {{tables.conversation_templates}}(api_key_id);

-- Add comment for clarity
COMMENT ON COLUMN {{tables.conversation_templates}}.api_key_id IS 'API key ID for filtering, NULL for global templates';
