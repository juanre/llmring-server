# LLMRing Server API Documentation

## Overview

LLMRing Server provides a REST API for persistence, usage tracking, receipts, and MCP integration. All project-scoped endpoints require the `X-API-Key` header for authentication.

## Base URL

```
http://localhost:8000
```

## Authentication

Most endpoints require authentication via the `X-API-Key` header:

```http
X-API-Key: your-api-key-here
```

## API Endpoints

### Public Endpoints

These endpoints are accessible without authentication.

#### Service Info

```http
GET /
```

Returns basic service information.

**Response:**
```json
{
  "service": "llmring-server",
  "version": "0.1.0",
  "status": "healthy"
}
```

#### Health Check

```http
GET /health
```

Checks database connectivity and service health.

**Response:**
```json
{
  "status": "healthy",
  "database": "connected"
}
```

#### Registry

```http
GET /registry
GET /registry.json
```

Returns aggregated model registry from all providers.

**Response:**
```json
{
  "openai:gpt-4o": {
    "model_name": "gpt-4o",
    "display_name": "GPT-4 Optimized",
    "max_input_tokens": 128000,
    "max_output_tokens": 4096,
    "dollars_per_million_tokens_input": 5.0,
    "dollars_per_million_tokens_output": 15.0,
    "supports_vision": true,
    "supports_function_calling": true
  },
  ...
}
```

### Usage Tracking

#### Log Usage

```http
POST /api/v1/log
X-API-Key: required
```

Log LLM usage for tracking and billing.

**Request Body:**
```json
{
  "provider": "openai",
  "model": "gpt-4",
  "input_tokens": 100,
  "output_tokens": 50,
  "cached_input_tokens": 0,
  "alias": "summarizer",
  "profile": "production",
  "cost": 0.0025
}
```

**Response:**
```json
{
  "id": "uuid",
  "logged_at": "2025-08-26T12:00:00Z"
}
```

#### Get Statistics

```http
GET /api/v1/stats?start_date=2025-08-01&end_date=2025-08-26&group_by=day
X-API-Key: required
```

Get usage statistics for the project.

**Query Parameters:**
- `start_date` (optional): Start date (YYYY-MM-DD)
- `end_date` (optional): End date (YYYY-MM-DD)
- `group_by` (optional): Grouping period (day, week, month)

**Response:**
```json
[
  {
    "date": "2025-08-26",
    "total_calls": 150,
    "total_tokens": 45000,
    "total_cost": 2.25,
    "by_model": {
      "openai:gpt-4": {
        "calls": 50,
        "tokens": 25000,
        "cost": 1.75
      }
    }
  }
]
```

### Conversations

#### Create Conversation

```http
POST /conversations
X-API-Key: required
```

Create a new conversation.

**Request Body:**
```json
{
  "title": "Product Discussion",
  "system_prompt": "You are a helpful assistant",
  "model_alias": "claude-3-sonnet",
  "project_id": "uuid"
}
```

**Response:**
```json
{
  "id": "uuid",
  "title": "Product Discussion",
  "system_prompt": "You are a helpful assistant",
  "model_alias": "claude-3-sonnet",
  "created_at": "2025-08-26T12:00:00Z",
  "updated_at": "2025-08-26T12:00:00Z"
}
```

#### List Conversations

```http
GET /conversations?limit=20&offset=0
X-API-Key: required
```

List all conversations for the project.

#### Get Conversation

```http
GET /conversations/{conversation_id}
X-API-Key: required
```

Get a conversation with all its messages.

**Response:**
```json
{
  "id": "uuid",
  "title": "Product Discussion",
  "messages": [
    {
      "id": "uuid",
      "role": "user",
      "content": "Hello",
      "created_at": "2025-08-26T12:00:00Z"
    },
    {
      "id": "uuid",
      "role": "assistant",
      "content": "Hi! How can I help?",
      "created_at": "2025-08-26T12:00:01Z"
    }
  ]
}
```

#### Add Messages

```http
POST /conversations/{conversation_id}/messages/batch
X-API-Key: required
```

Add multiple messages to a conversation.

**Request Body:**
```json
[
  {
    "role": "user",
    "content": "What's the weather?"
  },
  {
    "role": "assistant",
    "content": "I don't have access to real-time weather data."
  }
]
```

### MCP Integration

#### Register MCP Server

```http
POST /api/v1/mcp/servers
X-API-Key: required
```

Register a new MCP server.

**Request Body:**
```json
{
  "name": "weather-server",
  "url": "http://localhost:8080",
  "transport_type": "http",
  "auth_config": {
    "api_key": "secret"
  },
  "capabilities": {
    "tools": true,
    "resources": true,
    "prompts": false
  },
  "project_id": "uuid"
}
```

#### List MCP Servers

```http
GET /api/v1/mcp/servers?project_id=uuid&is_active=true
X-API-Key: required
```

List all registered MCP servers.

#### List Tools

```http
GET /api/v1/mcp/tools?server_id=uuid&project_id=uuid
X-API-Key: required
```

List all available tools from MCP servers.

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "get_weather",
    "description": "Get current weather for a location",
    "input_schema": {
      "type": "object",
      "properties": {
        "location": {
          "type": "string",
          "description": "City name"
        }
      },
      "required": ["location"]
    },
    "server": {
      "id": "uuid",
      "name": "weather-server",
      "url": "http://localhost:8080"
    }
  }
]
```

#### Execute Tool

```http
POST /api/v1/mcp/tools/{tool_id}/execute
X-API-Key: required
```

Execute an MCP tool.

**Request Body:**
```json
{
  "input": {
    "location": "San Francisco"
  },
  "conversation_id": "uuid"
}
```

**Response:**
```json
{
  "execution_id": "uuid",
  "tool_id": "uuid",
  "result": {
    "temperature": 72,
    "conditions": "sunny"
  },
  "executed_at": "2025-08-26T12:00:00Z"
}
```

#### List Resources

```http
GET /api/v1/mcp/resources?server_id=uuid
X-API-Key: required
```

List all available resources from MCP servers.

#### Get Resource Content

```http
GET /api/v1/mcp/resources/{resource_id}/content
X-API-Key: required
```

Get the content of a specific resource.

#### List Prompts

```http
GET /api/v1/mcp/prompts?server_id=uuid
X-API-Key: required
```

List all available prompts from MCP servers.

#### Render Prompt

```http
POST /api/v1/mcp/prompts/{prompt_id}/render
X-API-Key: required
```

Render a prompt with arguments.

**Request Body:**
```json
{
  "arguments": {
    "language": "python",
    "task": "sorting algorithm"
  }
}
```

**Response:**
```json
{
  "messages": [
    {
      "role": "system",
      "content": "You are an expert Python developer..."
    },
    {
      "role": "user",
      "content": "Write a sorting algorithm..."
    }
  ]
}
```

### Conversation Templates

#### Create Template

```http
POST /api/v1/templates
X-API-Key: required
```

Create a reusable conversation template.

**Request Body:**
```json
{
  "name": "code-review",
  "description": "Template for code review",
  "system_prompt": "You are an expert code reviewer",
  "initial_messages": [
    {
      "role": "user",
      "content": "Please review the following code..."
    }
  ],
  "model_alias": "claude-3-opus"
}
```

#### List Templates

```http
GET /api/v1/templates
X-API-Key: required
```

List all available templates.

#### Get Template Statistics

```http
GET /api/v1/templates/stats
X-API-Key: required
```

Get usage statistics for templates.

### Receipts

#### Store Receipt

```http
POST /api/v1/receipts
X-API-Key: required
```

Store a signed receipt.

**Request Body:**
```json
{
  "receipt": {
    "id": "uuid",
    "timestamp": "2025-08-26T12:00:00Z",
    "model": "openai:gpt-4",
    "tokens": {
      "input": 100,
      "output": 50
    },
    "cost": {
      "amount": 0.0025,
      "calculation": "standard"
    },
    "signature": "ed25519:base64url_signature"
  }
}
```

#### Get Receipt

```http
GET /api/v1/receipts/{receipt_id}
X-API-Key: required
```

Retrieve a stored receipt.

#### Issue Receipt

```http
POST /api/v1/receipts/issue
X-API-Key: required
```

Issue a new signed receipt (requires signing key configuration).

## Error Responses

All endpoints use standard HTTP status codes and return errors in this format:

```json
{
  "detail": "Error message here"
}
```

Common status codes:
- `200 OK`: Success
- `201 Created`: Resource created
- `400 Bad Request`: Invalid request
- `401 Unauthorized`: Missing or invalid X-API-Key
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

## Rate Limiting

No built-in rate limiting is implemented. Deploy behind a reverse proxy (nginx, Cloudflare) for production rate limiting.

## CORS

CORS is configured via the `LLMRING_CORS_ORIGINS` environment variable. Set specific origins for production:

```bash
LLMRING_CORS_ORIGINS=https://app.example.com,https://www.example.com
```

## OpenAPI/Swagger

Interactive API documentation is available at:

```
http://localhost:8000/docs
```

ReDoc documentation at:

```
http://localhost:8000/redoc
```