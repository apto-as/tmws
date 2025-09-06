# TMWS (Trinitas Memory & Workflow Service) Overview

## System Architecture

TMWS is a unified server providing both REST API and MCP (Model Context Protocol) interfaces for the Trinitas AI agent system.

### Core Components

```
TMWS Server
├── FastAPI (REST API) - Port 8000
│   ├── /api/v1/tasks - Task management
│   ├── /api/v1/workflows - Workflow orchestration
│   ├── /api/v1/personas - Agent personas
│   └── /api/v1/memory - Semantic memory
│
└── FastMCP (MCP Server) - stdio/JSON-RPC
    ├── semantic_search - Vector similarity search
    ├── store_memory - Store semantic memories
    ├── task_operations - Task CRUD
    └── workflow_execution - Workflow management
```

## Key Features

### 1. Unified Memory System
- **PostgreSQL + pgvector**: Vector storage for semantic search
- **Redis**: Distributed caching and rate limiting
- **Hybrid memory**: Combines short-term and long-term storage

### 2. Task Management
- Full CRUD operations for task lifecycle
- Priority-based scheduling (LOW, MEDIUM, HIGH, URGENT)
- Status tracking (PENDING, IN_PROGRESS, COMPLETED, FAILED)
- Persona assignment for specialized handling

### 3. Workflow Orchestration
- Complex multi-step workflow execution
- Background task processing with monitoring
- Workflow history and audit trails
- Cancellation and retry mechanisms

### 4. Security Architecture
- **Unified Middleware**: Single security layer for all requests
- **Rate Limiting**: Redis-based distributed rate limiting
- **JWT Authentication**: Secure token-based auth (optional in dev)
- **Audit Logging**: Comprehensive security event logging

## Database Schema

### Core Models

```sql
-- Tasks
CREATE TABLE tasks (
    id UUID PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status task_status NOT NULL DEFAULT 'pending',
    priority task_priority NOT NULL DEFAULT 'medium',
    assigned_persona VARCHAR(100),
    progress INTEGER DEFAULT 0,
    metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Workflows
CREATE TABLE workflows (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    workflow_type VARCHAR(100) NOT NULL,
    status workflow_status NOT NULL DEFAULT 'pending',
    priority workflow_priority NOT NULL DEFAULT 'medium',
    config JSONB,
    result JSONB,
    error TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Memory Embeddings
CREATE TABLE memory_embeddings (
    id UUID PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(384) NOT NULL,
    metadata JSONB,
    importance FLOAT DEFAULT 0.5,
    persona_id VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Personas
CREATE TABLE personas (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    capabilities JSONB,
    configuration JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

## Environment Configuration

### Required Environment Variables

```bash
# Core Configuration
TMWS_DATABASE_URL=postgresql://user:pass@localhost:5432/tmws
TMWS_SECRET_KEY=<32+ char secure key>
TMWS_ENVIRONMENT=development|staging|production

# Redis Configuration
TMWS_REDIS_URL=redis://localhost:6379/0

# API Configuration
TMWS_API_HOST=0.0.0.0
TMWS_API_PORT=8000

# Security Settings
TMWS_AUTH_ENABLED=false  # Set true for production
TMWS_RATE_LIMIT_REQUESTS=100
TMWS_RATE_LIMIT_PERIOD=60

# Vector/Embedding Settings
TMWS_EMBEDDING_MODEL=all-MiniLM-L6-v2
TMWS_VECTOR_DIMENSION=384
```

## API Endpoints

### Task Management
- `GET /api/v1/tasks` - List tasks with filters
- `POST /api/v1/tasks` - Create new task
- `GET /api/v1/tasks/{id}` - Get task details
- `PUT /api/v1/tasks/{id}` - Update task
- `DELETE /api/v1/tasks/{id}` - Delete task
- `POST /api/v1/tasks/{id}/complete` - Mark as complete

### Workflow Management
- `GET /api/v1/workflows` - List workflows
- `POST /api/v1/workflows` - Create workflow
- `GET /api/v1/workflows/{id}` - Get workflow details
- `PUT /api/v1/workflows/{id}` - Update workflow
- `DELETE /api/v1/workflows/{id}` - Delete workflow
- `POST /api/v1/workflows/{id}/execute` - Execute workflow
- `POST /api/v1/workflows/{id}/cancel` - Cancel execution
- `GET /api/v1/workflows/{id}/status` - Get execution status

### Memory Operations
- `POST /api/v1/memory/store` - Store semantic memory
- `POST /api/v1/memory/search` - Semantic similarity search
- `GET /api/v1/memory/recall` - Recall memories by criteria
- `DELETE /api/v1/memory/{id}` - Delete memory

### System Health
- `GET /health` - System health check
- `GET /api/v1/stats` - System statistics

## MCP Tools

### Available Tools for Claude Desktop

1. **semantic_search**
   - Search memories using vector similarity
   - Parameters: query, limit, threshold

2. **store_memory**
   - Store new semantic memory
   - Parameters: content, importance, metadata

3. **manage_task**
   - Create, update, delete tasks
   - Parameters: operation, task_data

4. **execute_workflow**
   - Run workflow with parameters
   - Parameters: workflow_id, parameters

## Security Features

### 404 Security Standards
- No default credentials in production
- Mandatory authentication in production
- Cryptographically secure secret keys
- Rate limiting and brute force protection
- Comprehensive audit logging

### Middleware Stack
1. CORS handling with strict origins
2. Redis-based rate limiting
3. JWT authentication (when enabled)
4. Request/response audit logging
5. Security headers (HSTS, CSP, etc.)

## Development Setup

### Quick Start

```bash
# Clone and setup
git clone <repo>
cd tmws
./install.sh

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Initialize database
python -m alembic upgrade head

# Run server
python -m src.main
```

### Testing

```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# Full test suite
pytest tests/ -v --cov=src
```

## Production Deployment

### Requirements
- PostgreSQL 14+ with pgvector extension
- Redis 6+
- Python 3.11+
- 2GB+ RAM
- SSL/TLS certificates

### Security Checklist
- [ ] Set TMWS_ENVIRONMENT=production
- [ ] Set TMWS_AUTH_ENABLED=true
- [ ] Generate secure TMWS_SECRET_KEY
- [ ] Configure CORS origins explicitly
- [ ] Enable SSL on database connections
- [ ] Setup firewall rules
- [ ] Configure reverse proxy (nginx/traefik)
- [ ] Enable audit logging
- [ ] Setup monitoring and alerting

## Integration with Trinitas Agents

TMWS provides the backend infrastructure for Trinitas AI personas:

- **Athena**: Uses workflows for orchestration
- **Artemis**: Leverages task optimization features
- **Hestia**: Utilizes security audit logs
- **Eris**: Manages team coordination tasks
- **Hera**: Executes strategic planning workflows
- **Muses**: Stores and retrieves documentation

Each persona can interact through either REST API or MCP protocol based on the context.