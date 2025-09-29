-- MCP (Model Context Protocol) Schema for llmring-server
-- This migration adds MCP support to llmring-server

-- Create mcp_client schema if it doesn't exist
CREATE SCHEMA IF NOT EXISTS mcp_client;

-- =====================================================
-- MCP SERVERS REGISTRY
-- =====================================================

-- MCP servers registry
CREATE TABLE IF NOT EXISTS mcp_client.servers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    url VARCHAR(1000) NOT NULL,
    transport_type VARCHAR(50) NOT NULL CHECK (transport_type IN ('stdio', 'http', 'websocket')),
    auth_config JSONB,
    capabilities JSONB,
    is_active BOOLEAN DEFAULT true,
    api_key_id VARCHAR(255), -- NULL for local, set for SaaS
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- MCP tools registry
CREATE TABLE IF NOT EXISTS mcp_client.tools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    server_id UUID REFERENCES mcp_client.servers(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    input_schema JSONB NOT NULL,
    is_active BOOLEAN DEFAULT true,
    api_key_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(server_id, name)
);

-- MCP resources
CREATE TABLE IF NOT EXISTS mcp_client.resources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    server_id UUID REFERENCES mcp_client.servers(id) ON DELETE CASCADE,
    uri VARCHAR(1000) NOT NULL,
    name VARCHAR(255),
    description TEXT,
    mime_type VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    api_key_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(server_id, uri)
);

-- MCP prompts
CREATE TABLE IF NOT EXISTS mcp_client.prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    server_id UUID REFERENCES mcp_client.servers(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    arguments JSONB,
    is_active BOOLEAN DEFAULT true,
    api_key_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(server_id, name)
);

-- Tool execution history
CREATE TABLE IF NOT EXISTS mcp_client.tool_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_id UUID REFERENCES mcp_client.tools(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES {{tables.conversations}}(id) ON DELETE CASCADE,
    input JSONB,
    output JSONB,
    error TEXT,
    duration_ms INTEGER,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- INDEXES FOR PERFORMANCE
-- =====================================================

-- MCP servers indexes
CREATE INDEX IF NOT EXISTS idx_mcp_servers_name ON mcp_client.servers(name);
CREATE INDEX IF NOT EXISTS idx_mcp_servers_api_key ON mcp_client.servers(api_key_id);
CREATE INDEX IF NOT EXISTS idx_mcp_servers_active ON mcp_client.servers(is_active);

-- MCP tools indexes
CREATE INDEX IF NOT EXISTS idx_mcp_tools_server ON mcp_client.tools(server_id);
CREATE INDEX IF NOT EXISTS idx_mcp_tools_name ON mcp_client.tools(name);
CREATE INDEX IF NOT EXISTS idx_mcp_tools_api_key ON mcp_client.tools(api_key_id);
CREATE INDEX IF NOT EXISTS idx_mcp_tools_active ON mcp_client.tools(is_active);

-- MCP resources indexes
CREATE INDEX IF NOT EXISTS idx_mcp_resources_server ON mcp_client.resources(server_id);
CREATE INDEX IF NOT EXISTS idx_mcp_resources_uri ON mcp_client.resources(uri);
CREATE INDEX IF NOT EXISTS idx_mcp_resources_api_key ON mcp_client.resources(api_key_id);

-- MCP prompts indexes
CREATE INDEX IF NOT EXISTS idx_mcp_prompts_server ON mcp_client.prompts(server_id);
CREATE INDEX IF NOT EXISTS idx_mcp_prompts_name ON mcp_client.prompts(name);
CREATE INDEX IF NOT EXISTS idx_mcp_prompts_api_key ON mcp_client.prompts(api_key_id);

-- Tool execution indexes
CREATE INDEX IF NOT EXISTS idx_tool_executions_tool ON mcp_client.tool_executions(tool_id);
CREATE INDEX IF NOT EXISTS idx_tool_executions_conversation ON mcp_client.tool_executions(conversation_id);
CREATE INDEX IF NOT EXISTS idx_tool_executions_executed ON mcp_client.tool_executions(executed_at DESC);

-- =====================================================
-- TRIGGERS
-- =====================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION mcp_client.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Auto-update updated_at timestamp for servers
CREATE TRIGGER tr_mcp_servers_updated_at
    BEFORE UPDATE ON mcp_client.servers
    FOR EACH ROW EXECUTE FUNCTION mcp_client.update_updated_at();
