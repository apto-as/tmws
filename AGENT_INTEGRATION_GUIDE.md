# TMWS Agent Integration Guide

## Overview
TMWS v3.0 provides a universal memory management system for any AI agent. Agents are automatically detected and registered when connecting via MCP protocol.

## Quick Start

### 1. Set Environment Variables

```bash
# Required: Set your agent identifier
export TMWS_AGENT_ID="your-agent-name"

# Optional: Set namespace (default: "default")
export TMWS_AGENT_NAMESPACE="your-project"

# Optional: Set capabilities (JSON string)
export TMWS_AGENT_CAPABILITIES='{"language_model": true, "code_generation": true}'
```

### 2. Connect via MCP

```bash
# Start the MCP server
python tmws/mcp_server.py
```

### 3. Use Memory Tools

The following tools are automatically available:

#### Create Memory
```python
await mcp_client.call_tool("create_memory", {
    "content": "Important information to remember",
    "tags": ["project", "important"],
    "importance": 0.8
})
```

#### Search Memories
```python
await mcp_client.call_tool("search_memories", {
    "query": "project requirements",
    "limit": 10
})
```

#### Get Agent Info
```python
await mcp_client.call_tool("get_agent_info")
# Returns: {
#   "agent_id": "your-agent-name",
#   "namespace": "your-project",
#   "capabilities": {...},
#   "auto_detected": true
# }
```

## Agent Auto-Registration

### How It Works

1. **Environment Detection**: On MCP connection, TMWS checks for agent ID in environment variables
2. **Automatic Registration**: Unknown agents are automatically registered with default settings
3. **Capability Recording**: Agent capabilities are stored for optimization
4. **Statistics Tracking**: All agent activities are tracked for analytics

### Supported Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TMWS_AGENT_ID` | Primary agent identifier | Yes (or MCP_AGENT_ID) |
| `MCP_AGENT_ID` | Alternative agent identifier | Yes (or TMWS_AGENT_ID) |
| `TMWS_AGENT_NAMESPACE` | Memory namespace | No (default: "default") |
| `TMWS_AGENT_CAPABILITIES` | JSON capabilities | No |
| `TMWS_ALLOW_DEFAULT_AGENT` | Allow testing without ID | No |

## Agent Types

TMWS automatically detects agent types based on the agent ID:

- **anthropic_llm**: Claude, Anthropic agents
- **openai_llm**: GPT, OpenAI agents  
- **google_llm**: Gemini, Bard agents
- **meta_llm**: Llama, Meta agents
- **custom_agent**: All other agents

## Memory Access Control

### Access Levels

- **private**: Only accessible by owner agent
- **team**: Accessible by agents in same namespace
- **shared**: Accessible by explicitly shared agents
- **public**: Accessible by all agents
- **system**: System-wide shared knowledge

### Sharing Memories

```python
await mcp_client.call_tool("share_memory", {
    "memory_id": "memory-uuid",
    "share_with_agents": ["agent-1", "agent-2"],
    "permission": "read"  # or "write", "delete"
})
```

## Statistics and Analytics

### Get Agent Statistics

```python
stats = await mcp_client.call_tool("get_agent_statistics")
# Returns comprehensive metrics including:
# - Total memories created
# - Average response time
# - Success rate
# - Access patterns
# - Learning statistics
```

### List All Agents

```python
agents = await mcp_client.call_tool("list_agents", {
    "namespace": "your-project",
    "limit": 100
})
```

## Security Considerations

### Agent ID Validation

Agent IDs must:
- Be 3-64 characters long
- Contain only alphanumeric, hyphens, underscores, dots
- Start with alphanumeric character
- Not contain path traversal or injection patterns

### API Key Authentication

For production use, set up API key authentication:

```python
# Generate API key for agent
api_key = auth_service.generate_api_key()

# Use in requests
headers = {"X-API-Key": api_key}
```

### Rate Limiting

Default limits per agent:
- 1000 requests/minute (general)
- 100 searches/minute
- 500 writes/minute

## Integration Examples

### Claude Desktop

Add to Claude Desktop configuration:

```json
{
  "mcpServers": {
    "tmws": {
      "command": "python",
      "args": ["-m", "tmws.mcp_server_v3"],
      "cwd": "/path/to/tmws",
      "env": {
        "TMWS_AGENT_ID": "claude-desktop",
        "TMWS_AGENT_NAMESPACE": "personal"
      }
    }
  }
}
```

### Custom Python Agent

```python
import os
import asyncio
from mcp import Client

# Set agent identity
os.environ["TMWS_AGENT_ID"] = "my-custom-agent"
os.environ["TMWS_AGENT_CAPABILITIES"] = json.dumps({
    "language": "python",
    "version": "3.11",
    "features": ["async", "ml"]
})

# Connect and use
async def main():
    client = Client()
    await client.connect()
    
    # Create memory
    await client.call_tool("create_memory", {
        "content": "Project initialized",
        "importance": 0.9
    })
    
    # Search memories
    results = await client.call_tool("search_memories", {
        "query": "initialization"
    })

asyncio.run(main())
```

### Node.js Agent

```javascript
const { MCPClient } = require('@modelcontextprotocol/client');

// Set environment
process.env.TMWS_AGENT_ID = 'nodejs-agent';
process.env.TMWS_AGENT_NAMESPACE = 'backend';

const client = new MCPClient();

async function main() {
    await client.connect();
    
    // Use memory tools
    const memory = await client.callTool('create_memory', {
        content: 'Server configuration',
        tags: ['config', 'server']
    });
    
    console.log('Memory created:', memory);
}

main();
```

## Troubleshooting

### Agent Not Detected

1. Check environment variables are set correctly
2. Verify agent ID format is valid
3. Check logs for detection attempts

### Access Denied

1. Verify agent is registered
2. Check memory access levels
3. Ensure proper namespace configuration

### Performance Issues

1. Monitor rate limits
2. Check database connection pool
3. Review agent statistics for bottlenecks

## API Reference

### MCP Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `get_agent_info` | Get current agent info | None |
| `create_memory` | Create new memory | content, tags, importance, access_level |
| `search_memories` | Semantic search | query, limit, include_shared |
| `share_memory` | Share with agents | memory_id, share_with_agents, permission |
| `get_agent_statistics` | Get agent metrics | None |
| `list_agents` | List all agents | namespace, agent_type, limit |
| `update_capabilities` | Update capabilities | capabilities |

## Migration from v2

If migrating from TMWS v2 (persona-based):

1. Run migration script: `alembic upgrade head`
2. Existing personas become agents in "trinitas" namespace
3. Update agent IDs in your code

## Support

For issues or questions:
- GitHub: https://github.com/apto-as/tmws
- Documentation: /docs/
- Examples: /examples/