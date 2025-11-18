-- Migration 006: Add project_id scoping for user/JWT flows
-- Rationale: Allow browser-authenticated traffic to persist data without API keys.

-- Conversations: add project_id for user-scoped storage
ALTER TABLE {{tables.conversations}}
    ADD COLUMN IF NOT EXISTS project_id UUID;
CREATE INDEX IF NOT EXISTS idx_conversations_project_id ON {{tables.conversations}}(project_id);

-- Usage logs: add project_id for user-scoped stats
ALTER TABLE {{tables.usage_logs}}
    ADD COLUMN IF NOT EXISTS project_id UUID;
CREATE INDEX IF NOT EXISTS idx_usage_logs_project_id ON {{tables.usage_logs}}(project_id, created_at DESC);

-- Conversation templates: support project scoping alongside API keys
ALTER TABLE {{tables.conversation_templates}}
    ADD COLUMN IF NOT EXISTS project_id UUID;
CREATE INDEX IF NOT EXISTS idx_conversation_templates_project_id ON {{tables.conversation_templates}}(project_id);

-- MCP tables: store project_id for user-scoped MCP resources
ALTER TABLE mcp_client.servers
    ADD COLUMN IF NOT EXISTS project_id UUID;
CREATE INDEX IF NOT EXISTS idx_mcp_servers_project ON mcp_client.servers(project_id);

ALTER TABLE mcp_client.tools
    ADD COLUMN IF NOT EXISTS project_id UUID;
CREATE INDEX IF NOT EXISTS idx_mcp_tools_project ON mcp_client.tools(project_id);

ALTER TABLE mcp_client.resources
    ADD COLUMN IF NOT EXISTS project_id UUID;
CREATE INDEX IF NOT EXISTS idx_mcp_resources_project ON mcp_client.resources(project_id);

ALTER TABLE mcp_client.prompts
    ADD COLUMN IF NOT EXISTS project_id UUID;
CREATE INDEX IF NOT EXISTS idx_mcp_prompts_project ON mcp_client.prompts(project_id);
