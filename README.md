# TMWS - Universal Agent Memory System

Version: 3.1.0

## Overview

TMWS (Trinitas Memory & Workflow Service) is a universal multi-agent memory management system with MCP (Model Context Protocol) support. It provides persistent memory, semantic search, and agent context management for AI agents.

## Features

- 🧠 **Semantic Memory**: PostgreSQL + pgvector for intelligent memory storage and retrieval
- 🤖 **Multi-Agent Support**: Pre-configured with 6 Trinitas agents + custom agent registration
- 🔄 **Dynamic Agent Switching**: Runtime agent context switching via MCP tools
- 📋 **Task Management**: Workflow orchestration and task tracking
- 🔌 **MCP Protocol**: Full Model Context Protocol support
- 🔒 **Security**: Agent authentication, access control, and audit logging

## Installation & Usage

### Via uvx (Recommended)

```bash
# Install and run directly from GitHub
uvx --from git+https://github.com/apto-as/tmws.git tmws
```

### Claude Desktop Configuration

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "tmws": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/apto-as/tmws.git", "tmws"],
      "env": {
        "TMWS_AGENT_ID": "athena-conductor",
        "TMWS_AGENT_NAMESPACE": "trinitas",
        "TMWS_ALLOW_DEFAULT_AGENT": "true"
      }
    }
  }
}
```

## Default Agents

TMWS includes 6 pre-configured Trinitas agents:

- **Athena** - System orchestration and coordination
- **Artemis** - Performance optimization and technical excellence
- **Hestia** - Security analysis and audit
- **Eris** - Tactical planning and team coordination
- **Hera** - Strategic planning and architecture
- **Muses** - Documentation and knowledge management

## Custom Agents

You can register your own agents dynamically. See [CUSTOM_AGENTS_GUIDE.md](CUSTOM_AGENTS_GUIDE.md) for details.

## Environment Variables

- `TMWS_AGENT_ID` - Agent identifier (e.g., "athena-conductor")
- `TMWS_AGENT_NAMESPACE` - Agent namespace (default: "default")
- `TMWS_DATABASE_URL` - PostgreSQL connection string
- `TMWS_SECRET_KEY` - Security key (32+ characters)
- `TMWS_ALLOW_DEFAULT_AGENT` - Allow fallback agent for testing

## Requirements

- Python 3.11+
- PostgreSQL with pgvector extension
- uv package manager (for uvx installation)

## Documentation

- [Custom Agents Guide](CUSTOM_AGENTS_GUIDE.md) - How to register and manage custom agents
- [Example Configuration](custom_agents_example.json) - Sample custom agent definitions

## License

Copyright (c) 2025 Apto AS