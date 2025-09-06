# TMWS - Trinitas Memory & Workflow Service

Version: 1.0.0

## Overview
Standalone MCP server providing memory management and workflow orchestration for Trinitas AI agents.

## Features
- 🧠 Semantic Memory: PostgreSQL + pgvector
- 📋 Task Management System
- ⚙️ Workflow Orchestration
- 🔌 MCP Protocol Support
- 🔒 Security Features

## Quick Start
```bash
./install.sh
python -m src.main
```

## MCP Registration
Add to Claude Desktop config:
```json
{
  "mcpServers": {
    "tmws": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/Users/apto-as/workspace/github.com/apto-as/tmws"
    }
  }
}
```

## License
Copyright (c) 2025 Apto AS
