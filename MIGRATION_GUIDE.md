# TMWS v2.0 Migration Guide

## Overview

TMWS v2.0 introduces a shared server model that allows multiple Claude Code instances to connect to a single TMWS server. This resolves the database locking issues experienced with v1.0.

## Architecture Changes

### v1.0 (Direct stdio)
```
Claude Code Terminal 1 → MCP (stdio) → TMWS Process 1 → Database
Claude Code Terminal 2 → MCP (stdio) → TMWS Process 2 → Database (LOCKED!)
```

### v2.0 (Shared Server)
```
Claude Code Terminal 1 → MCP (stdio) → WebSocket Client → ┐
                                                            ├→ TMWS Server → Database
Claude Code Terminal 2 → MCP (stdio) → WebSocket Client → ┘
```

## Migration Steps

### Step 1: Start the TMWS Server

First, start the TMWS server in a separate terminal:

```bash
# Option 1: Using uvx (recommended)
uvx --from git+https://github.com/apto-as/tmws.git tmws-server

# Option 2: If installed locally
tmws-server --host 0.0.0.0 --port 8000

# Option 3: With auto-reload for development
tmws-server --reload --log-level debug
```

The server will start and display:
```
INFO: TMWS Server started
INFO: Uvicorn running on http://0.0.0.0:8000
```

### Step 2: Update Claude Code Configuration

Replace your current Claude Code MCP configuration with the WebSocket client version:

#### Old Configuration (v1.0)
```json
{
  "mcpServers": {
    "tmws": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "git+https://github.com/apto-as/tmws.git", "tmws"]
    }
  }
}
```

#### New Configuration (v2.0)
```json
{
  "mcpServers": {
    "tmws": {
      "type": "stdio",
      "command": "uvx",
      "args": [
        "--from", 
        "git+https://github.com/apto-as/tmws.git", 
        "tmws-ws-client",
        "--server",
        "ws://localhost:8000/ws/mcp"
      ],
      "env": {
        "TMWS_AGENT_ID": "athena-conductor",
        "TMWS_AGENT_NAMESPACE": "trinitas"
      }
    }
  }
}
```

### Step 3: Restart Claude Code

After updating the configuration, restart Claude Code to apply the changes.

## Multiple Connections

Now you can open multiple Claude Code terminals, and they will all connect to the same TMWS server:

1. Each terminal gets its own unique session ID
2. All terminals share the same database through the server
3. No more database locking issues
4. Real-time updates across all connected clients

## Server Management

### Starting the Server

```bash
# Basic start
tmws-server

# With custom host/port
tmws-server --host 0.0.0.0 --port 8080

# With debug logging
tmws-server --log-level debug
```

### Checking Server Status

```bash
# Health check
curl http://localhost:8000/health

# View connected clients
curl http://localhost:8000/api/v1/clients
```

### Stopping the Server

Press `Ctrl+C` in the terminal running the server. It will gracefully shutdown all connections.

## Environment Variables

The following environment variables can be used:

### Server Configuration
```bash
# Server settings
export TMWS_API_HOST=0.0.0.0
export TMWS_API_PORT=8000

# Database (required)
export TMWS_DATABASE_URL=postgresql://tmws_user:tmws_password@localhost:5432/tmws

# Optional
export TMWS_LOG_LEVEL=info
export TMWS_SECRET_KEY=your-secret-key-here
```

### Client Configuration
```bash
# WebSocket server URL (if not localhost)
export TMWS_SERVER_URL=ws://your-server:8000/ws/mcp

# Agent configuration
export TMWS_AGENT_ID=athena-conductor
export TMWS_AGENT_NAMESPACE=trinitas
```

## API Endpoints

The server provides both REST API and WebSocket endpoints:

### REST API
- `GET /` - Server info
- `GET /health` - Health check
- `GET /api/v1/tasks` - Task management
- `GET /api/v1/workflows` - Workflow management
- `GET /api/v1/memory` - Memory operations
- `GET /api/v1/personas` - Persona management

### WebSocket
- `ws://localhost:8000/ws` - General WebSocket endpoint
- `ws://localhost:8000/ws/mcp` - MCP protocol endpoint

## Troubleshooting

### Server won't start
- Check if port 8000 is already in use
- Verify PostgreSQL is running and accessible
- Check database credentials in `.env` file

### Claude Code can't connect
- Ensure the server is running
- Check the WebSocket URL in the configuration
- Verify firewall settings allow WebSocket connections

### Database errors
- Run database migrations: `alembic upgrade head`
- Check PostgreSQL logs for errors
- Verify pgvector extension is installed

## Rollback to v1.0

If you need to rollback to the direct connection:

1. Stop the TMWS server
2. Restore the original Claude Code configuration:
```json
{
  "mcpServers": {
    "tmws": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "git+https://github.com/apto-as/tmws.git", "tmws"]
    }
  }
}
```
3. Restart Claude Code

Note: You will experience database locking issues with multiple terminals again.

## Benefits of v2.0

1. **Multi-client support**: Multiple Claude Code instances can connect simultaneously
2. **No database locking**: Shared server handles all database operations
3. **Better performance**: Connection pooling and caching
4. **Real-time updates**: WebSocket enables push notifications
5. **Centralized management**: Single server to monitor and manage
6. **Session persistence**: Reconnect without losing context

## Known Limitations

1. Requires a separate server process to be running
2. Initial setup is slightly more complex
3. Network latency may affect responsiveness (minimal on localhost)

## Support

For issues or questions:
- GitHub Issues: https://github.com/apto-as/tmws/issues
- Documentation: https://github.com/apto-as/tmws/wiki