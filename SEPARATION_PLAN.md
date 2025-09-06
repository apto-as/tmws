# TMWS Separation Plan

## Integration Interface Specification

### REST API Endpoints
```yaml
base_url: http://localhost:8000/api/v1
authentication: Bearer Token (JWT)

endpoints:
  tasks:
    - POST /tasks
    - GET /tasks
    - PUT /tasks/{id}
    - DELETE /tasks/{id}
    - POST /tasks/{id}/complete
    
  workflows:
    - POST /workflows
    - GET /workflows
    - POST /workflows/{id}/execute
    - GET /workflows/{id}/status
    
  memory:
    - POST /memory/store
    - POST /memory/search
    - GET /memory/recall
```

### MCP Tools (for Claude Desktop)
```yaml
mcp_server: tmws
tools:
  - semantic_search
  - store_memory
  - manage_task
  - execute_workflow
```

### Client Library Interface
```python
# tmws_client.py
from typing import Dict, Any, List, Optional
import httpx

class TMWSClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {api_key}"}
        self.client = httpx.AsyncClient()
    
    async def create_task(self, title: str, **kwargs) -> Dict[str, Any]:
        """Create a new task"""
        pass
    
    async def search_memory(self, query: str, limit: int = 10) -> List[Dict]:
        """Search semantic memory"""
        pass
    
    async def execute_workflow(self, workflow_id: str, params: Dict) -> Dict:
        """Execute a workflow"""
        pass
```

## Directory Structure After Separation

### Trinitas-Agents (Core)
```
trinitas-agents/
├── agents/
│   ├── athena/
│   ├── artemis/
│   ├── hestia/
│   ├── eris/
│   ├── hera/
│   └── muses/
├── commands/
│   ├── trinitas.md
│   └── README.md
├── hooks/
│   └── (event hooks)
├── docs/
│   └── tmws-integration.md
└── libs/
    └── tmws_client.py  # Client library
```

### TMWS (Standalone Service)
```
tmws/
├── src/
│   ├── api/
│   ├── core/
│   ├── models/
│   ├── services/
│   └── main.py
├── tests/
├── migrations/
├── docker/
│   └── Dockerfile
├── docs/
│   ├── api.md
│   ├── deployment.md
│   └── mcp-integration.md
├── .env.example
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## Migration Checklist

### Pre-Separation
- [ ] Full backup created
- [ ] Dependencies documented
- [ ] Git branches created
- [ ] Team notified

### Separation Process
- [ ] TMWS directory copied
- [ ] New repository initialized
- [ ] Documentation moved
- [ ] Dependencies updated

### Post-Separation
- [ ] Trinitas cleaned up
- [ ] Interface defined
- [ ] Client library created
- [ ] Integration tested
- [ ] Documentation updated

### Validation
- [ ] Trinitas agents work without TMWS directory
- [ ] TMWS runs independently
- [ ] API communication works
- [ ] MCP tools function
- [ ] All tests pass

## Rollback Plan

If issues arise during separation:

1. **Immediate Rollback**
   ```bash
   cd /Users/apto-as/workspace/github.com/apto-as/trinitas-agents/
   git checkout backup/pre-separation-$(date +%Y%m%d)
   git reset --hard
   ```

2. **Restore from Backup**
   ```bash
   cd /Users/apto-as/workspace/github.com/apto-as/
   tar -xzf trinitas-agents-backup-$(date +%Y%m%d).tar.gz
   ```

## Communication Plan

### For Trinitas → TMWS
- REST API for operations
- Bearer token authentication
- Async client library

### For TMWS → Trinitas
- No direct dependency
- Event webhooks (optional)
- Status callbacks (optional)

## Timeline Estimate

- **Phase 1 (Preparation)**: 30 minutes
- **Phase 2 (TMWS Extraction)**: 1 hour
- **Phase 3 (Cleanup)**: 30 minutes
- **Phase 4 (Interface)**: 1 hour
- **Phase 5 (Testing)**: 1 hour
- **Total**: ~4 hours

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Git history loss | Low | Use git filter-repo to preserve |
| Breaking changes | Medium | Comprehensive testing |
| Integration issues | Medium | Client library abstraction |
| Deployment complexity | Low | Docker Compose for dev |

## Success Criteria

1. ✅ Two independent Git repositories
2. ✅ Clean separation of concerns
3. ✅ Working API communication
4. ✅ All tests passing
5. ✅ Documentation updated
6. ✅ No regression in functionality