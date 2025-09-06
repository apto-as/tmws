# TMWS Quick Start Guide

## Installation

```bash
# Clone repository
git clone https://github.com/apto-as/trinitas-agents.git
cd trinitas-agents/tmws

# Run installation script (installs to ~/.claude/tmws)
./install.sh
```

## Configuration for Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "tmws": {
      "command": "uv",
      "args": ["run", "python", "-m", "unified_server", "--mcp-mode"],
      "cwd": "~/.claude/tmws"
    }
  }
}
```

**Note:** After running `./install.sh`, TMWS will be installed at `~/.claude/tmws`.

## Starting Services

### API Server Only
```bash
cd ~/.claude/tmws
source .venv/bin/activate
uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
```

### Unified Server (MCP + API)
```bash
cd ~/.claude/tmws
uv run python -m unified_server
```

## Verification

1. Check API health:
```bash
curl http://localhost:8000/health
```

2. View API documentation:
Open http://localhost:8000/docs in your browser

## Why use `uv`?

- **Automatic virtual environment management**: uvが`.venv`を自動的に認識・使用
- **Dependency resolution**: `pyproject.toml`から依存関係を自動解決
- **Faster installation**: Rustベースで高速
- **Consistent execution**: 環境に依存しない一貫した実行

## Environment Variables

Key configuration in `.env`:
- `TMWS_DATABASE_URL` - PostgreSQL connection string
- `TMWS_REDIS_URL` - Redis connection string
- `TMWS_SECRET_KEY` - Application secret key
- `TMWS_JWT_SECRET` - JWT signing key