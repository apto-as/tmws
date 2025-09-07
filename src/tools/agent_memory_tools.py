"""
MCP tools for agent memory management in TMWS v2.0.
These tools allow external agents to interact with the memory system via MCP protocol.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID

from fastmcp import Tool


class AgentMemoryTools:
    """MCP tools for agent memory operations."""
    
    def __init__(self, memory_service, auth_service):
        self.memory_service = memory_service
        self.auth_service = auth_service
    
    async def create_memory_tool(
        self,
        agent_id: str,
        content: str,
        namespace: str = "default",
        access_level: str = "private",
        tags: List[str] = None,
        context: Dict[str, Any] = None,
        importance: float = 0.5
    ) -> Dict[str, Any]:
        """
        Create a new memory for an agent.
        
        This tool is called by external agents via MCP to store memories.
        The agent_id identifies the calling agent.
        """
        
        # Validate agent permissions
        if not await self._validate_agent(agent_id, namespace):
            return {"error": "Invalid agent credentials"}
        
        # Create memory
        memory = await self.memory_service.create_memory(
            content=content,
            agent_id=agent_id,
            namespace=namespace,
            access_level=access_level,
            tags=tags or [],
            context=context or {},
            importance_score=importance
        )
        
        return {
            "success": True,
            "memory_id": str(memory.id),
            "message": "Memory created successfully"
        }
    
    async def search_memories_tool(
        self,
        agent_id: str,
        query: str,
        namespace: str = "default",
        limit: int = 10,
        include_shared: bool = True,
        min_importance: float = 0.0
    ) -> Dict[str, Any]:
        """
        Search memories using semantic search.
        
        Returns memories that the agent has access to based on:
        - Owned memories
        - Team memories (same namespace)
        - Explicitly shared memories
        - Public memories
        """
        
        # Validate agent
        if not await self._validate_agent(agent_id, namespace):
            return {"error": "Invalid agent credentials"}
        
        # Search memories with access control
        results = await self.memory_service.search_memories(
            query=query,
            agent_id=agent_id,
            namespace=namespace,
            limit=limit,
            include_shared=include_shared,
            min_importance=min_importance
        )
        
        # Filter based on access permissions
        accessible_results = []
        for memory in results:
            if self.auth_service.check_memory_access(
                agent_id=agent_id,
                agent_namespace=namespace,
                memory_agent_id=memory.agent_id,
                memory_namespace=memory.namespace,
                memory_access_level=memory.access_level,
                shared_agents=memory.shared_with_agents
            ):
                accessible_results.append({
                    "id": str(memory.id),
                    "content": memory.content,
                    "summary": memory.summary,
                    "agent_id": memory.agent_id,
                    "importance": memory.importance_score,
                    "relevance": memory.relevance_score,
                    "tags": memory.tags,
                    "created_at": memory.created_at.isoformat() if memory.created_at else None
                })
        
        return {
            "success": True,
            "count": len(accessible_results),
            "memories": accessible_results
        }
    
    async def share_memory_tool(
        self,
        agent_id: str,
        memory_id: str,
        share_with_agents: List[str],
        permission: str = "read"
    ) -> Dict[str, Any]:
        """
        Share a memory with other agents.
        
        Only the owner of a memory can share it.
        """
        
        # Get memory
        memory = await self.memory_service.get_memory(memory_id)
        if not memory:
            return {"error": "Memory not found"}
        
        # Check ownership
        if memory.agent_id != agent_id:
            return {"error": "Only memory owner can share"}
        
        # Update sharing
        await self.memory_service.share_memory(
            memory_id=memory_id,
            shared_with_agents=share_with_agents,
            permission=permission
        )
        
        return {
            "success": True,
            "message": f"Memory shared with {len(share_with_agents)} agents"
        }
    
    async def consolidate_memories_tool(
        self,
        agent_id: str,
        memory_ids: List[str],
        consolidation_type: str = "summary",
        namespace: str = "default"
    ) -> Dict[str, Any]:
        """
        Consolidate multiple memories into a single memory.
        
        Types:
        - summary: Create a summary of all memories
        - merge: Combine related memories
        - compress: Reduce redundancy
        """
        
        # Validate agent
        if not await self._validate_agent(agent_id, namespace):
            return {"error": "Invalid agent credentials"}
        
        # Check access to all memories
        memories = []
        for mem_id in memory_ids:
            memory = await self.memory_service.get_memory(mem_id)
            if not memory:
                continue
                
            # Check access
            if self.auth_service.check_memory_access(
                agent_id=agent_id,
                agent_namespace=namespace,
                memory_agent_id=memory.agent_id,
                memory_namespace=memory.namespace,
                memory_access_level=memory.access_level,
                shared_agents=memory.shared_with_agents
            ):
                memories.append(memory)
        
        if len(memories) < 2:
            return {"error": "Need at least 2 accessible memories to consolidate"}
        
        # Perform consolidation
        consolidated = await self.memory_service.consolidate_memories(
            agent_id=agent_id,
            memories=memories,
            consolidation_type=consolidation_type
        )
        
        return {
            "success": True,
            "consolidated_memory_id": str(consolidated.id),
            "source_count": len(memories),
            "message": f"Consolidated {len(memories)} memories"
        }
    
    async def get_memory_patterns_tool(
        self,
        agent_id: str,
        pattern_type: Optional[str] = None,
        namespace: str = "default",
        min_confidence: float = 0.5
    ) -> Dict[str, Any]:
        """
        Get learning patterns extracted from agent's memories.
        
        Pattern types:
        - sequence: Temporal patterns
        - correlation: Related memories
        - cluster: Grouped memories
        """
        
        # Validate agent
        if not await self._validate_agent(agent_id, namespace):
            return {"error": "Invalid agent credentials"}
        
        # Get patterns
        patterns = await self.memory_service.get_patterns(
            agent_id=agent_id,
            namespace=namespace,
            pattern_type=pattern_type,
            min_confidence=min_confidence
        )
        
        pattern_list = []
        for pattern in patterns:
            pattern_list.append({
                "id": str(pattern.id),
                "type": pattern.pattern_type,
                "confidence": pattern.confidence,
                "frequency": pattern.frequency,
                "data": pattern.pattern_data,
                "memory_count": len(pattern.memory_ids)
            })
        
        return {
            "success": True,
            "count": len(pattern_list),
            "patterns": pattern_list
        }
    
    async def _validate_agent(self, agent_id: str, namespace: str) -> bool:
        """Validate agent exists and is active."""
        # In production, this would check against database
        # For now, simple validation
        return bool(agent_id and namespace)
    
    def register_tools(self) -> List[Tool]:
        """Register all MCP tools."""
        return [
            Tool(
                name="memory_create",
                description="Create a new memory",
                input_schema={
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "Agent identifier"},
                        "content": {"type": "string", "description": "Memory content"},
                        "namespace": {"type": "string", "default": "default"},
                        "access_level": {"type": "string", "enum": ["private", "team", "shared", "public"]},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "context": {"type": "object"},
                        "importance": {"type": "number", "minimum": 0, "maximum": 1}
                    },
                    "required": ["agent_id", "content"]
                },
                func=self.create_memory_tool
            ),
            Tool(
                name="memory_search",
                description="Search memories using semantic search",
                input_schema={
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "Agent identifier"},
                        "query": {"type": "string", "description": "Search query"},
                        "namespace": {"type": "string", "default": "default"},
                        "limit": {"type": "integer", "default": 10},
                        "include_shared": {"type": "boolean", "default": True},
                        "min_importance": {"type": "number", "minimum": 0, "maximum": 1}
                    },
                    "required": ["agent_id", "query"]
                },
                func=self.search_memories_tool
            ),
            Tool(
                name="memory_share",
                description="Share a memory with other agents",
                input_schema={
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "Owner agent identifier"},
                        "memory_id": {"type": "string", "description": "Memory ID to share"},
                        "share_with_agents": {"type": "array", "items": {"type": "string"}},
                        "permission": {"type": "string", "enum": ["read", "write", "delete"]}
                    },
                    "required": ["agent_id", "memory_id", "share_with_agents"]
                },
                func=self.share_memory_tool
            ),
            Tool(
                name="memory_consolidate",
                description="Consolidate multiple memories",
                input_schema={
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "Agent identifier"},
                        "memory_ids": {"type": "array", "items": {"type": "string"}},
                        "consolidation_type": {"type": "string", "enum": ["summary", "merge", "compress"]},
                        "namespace": {"type": "string", "default": "default"}
                    },
                    "required": ["agent_id", "memory_ids"]
                },
                func=self.consolidate_memories_tool
            ),
            Tool(
                name="memory_patterns",
                description="Get learning patterns from memories",
                input_schema={
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "Agent identifier"},
                        "pattern_type": {"type": "string", "enum": ["sequence", "correlation", "cluster"]},
                        "namespace": {"type": "string", "default": "default"},
                        "min_confidence": {"type": "number", "minimum": 0, "maximum": 1}
                    },
                    "required": ["agent_id"]
                },
                func=self.get_memory_patterns_tool
            )
        ]