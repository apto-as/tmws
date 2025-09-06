"""
Memory Management Tools for TMWS MCP Server
Provides vector-based memory storage and semantic search
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from fastmcp import FastMCP

from .base_tool import BaseTool


class MemoryCreateRequest(BaseModel):
    """Memory creation parameters."""
    content: str = Field(..., description="The memory content to store")
    memory_type: str = Field(default="general", description="Type of memory")
    persona_id: Optional[str] = Field(None, description="Associated persona ID")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    importance: float = Field(default=0.5, ge=0.0, le=1.0, description="Importance score")


class MemorySearchRequest(BaseModel):
    """Memory search parameters."""
    query: str = Field(..., description="Search query")
    memory_type: Optional[str] = Field(None, description="Filter by memory type")
    persona_id: Optional[str] = Field(None, description="Filter by persona")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum results")
    semantic_search: bool = Field(default=True, description="Use semantic/vector search")
    min_similarity: float = Field(default=0.7, ge=0.0, le=1.0, description="Minimum similarity")


class MemoryUpdateRequest(BaseModel):
    """Memory update parameters."""
    memory_id: str = Field(..., description="Memory ID to update")
    content: Optional[str] = Field(None, description="New content")
    tags: Optional[List[str]] = Field(None, description="New tags")
    metadata: Optional[Dict[str, Any]] = Field(None, description="New metadata")
    importance: Optional[float] = Field(None, ge=0.0, le=1.0, description="New importance")


class MemoryTools(BaseTool):
    """Memory management tools for TMWS MCP server."""

    async def register_tools(self, mcp: FastMCP) -> None:
        """Register memory tools with FastMCP instance."""

        @mcp.tool()
        async def create_memory(
            content: str,
            memory_type: str = "general",
            persona_id: Optional[str] = None,
            tags: List[str] = None,
            metadata: Dict[str, Any] = None,
            importance: float = 0.5
        ) -> Dict[str, Any]:
            """
            Create a new memory with vector embedding.
            
            This tool stores knowledge in the Trinitas memory system with semantic search capabilities.
            Memory content is automatically vectorized for similarity search.
            
            Args:
                content: The memory content to store
                memory_type: Type of memory (general, technical, strategic, etc.)
                persona_id: Optional persona association
                tags: List of tags for categorization
                metadata: Additional structured data
                importance: Importance score from 0.0 to 1.0
                
            Returns:
                Dict containing memory ID, content, and creation details
            """
            request = MemoryCreateRequest(
                content=content,
                memory_type=memory_type,
                persona_id=persona_id,
                tags=tags or [],
                metadata=metadata or {},
                importance=importance
            )
            
            async def _create_memory(session, services):
                memory_service = services['memory_service']
                vectorization_service = services['vectorization_service']
                
                # Generate vector embedding
                embedding = await vectorization_service.vectorize_text(request.content)
                
                # Create memory
                memory = await memory_service.create_memory(
                    content=request.content,
                    memory_type=request.memory_type,
                    persona_id=request.persona_id,
                    tags=request.tags,
                    metadata=request.metadata,
                    embedding=embedding.tolist(),
                    importance=request.importance
                )
                
                return {
                    "id": str(memory.id),
                    "content": memory.content,
                    "memory_type": memory.memory_type,
                    "tags": memory.tags,
                    "importance": memory.importance,
                    "persona_id": str(memory.persona_id) if memory.persona_id else None,
                    "created_at": memory.created_at.isoformat(),
                    "vector_dimensions": len(embedding)
                }
            
            result = await self.execute_with_session(_create_memory)
            return self.format_success(result, "Memory created successfully")

        @mcp.tool()
        async def recall_memory(
            query: str,
            memory_type: Optional[str] = None,
            persona_id: Optional[str] = None,
            limit: int = 10,
            semantic_search: bool = True,
            min_similarity: float = 0.7
        ) -> Dict[str, Any]:
            """
            Recall memories based on query and filters.
            
            Supports both semantic (vector similarity) and keyword search.
            Semantic search uses vector embeddings for contextual similarity.
            
            Args:
                query: Search query string
                memory_type: Optional filter by memory type
                persona_id: Optional filter by persona
                limit: Maximum number of results (1-100)
                semantic_search: Use vector similarity search
                min_similarity: Minimum similarity score for results
                
            Returns:
                Dict containing search results and metadata
            """
            request = MemorySearchRequest(
                query=query,
                memory_type=memory_type,
                persona_id=persona_id,
                limit=limit,
                semantic_search=semantic_search,
                min_similarity=min_similarity
            )
            
            async def _recall_memory(session, services):
                memory_service = services['memory_service']
                
                if request.semantic_search:
                    # Vector similarity search
                    vectorization_service = services['vectorization_service']
                    query_embedding = await vectorization_service.vectorize_text(request.query)
                    
                    memories = await memory_service.search_similar_memories(
                        embedding=query_embedding.tolist(),
                        memory_type=request.memory_type,
                        persona_id=request.persona_id,
                        limit=request.limit,
                        min_similarity=request.min_similarity
                    )
                else:
                    # Keyword search
                    memories = await memory_service.search_memories(
                        query=request.query,
                        memory_type=request.memory_type,
                        persona_id=request.persona_id,
                        limit=request.limit
                    )
                
                return {
                    "query": request.query,
                    "search_type": "semantic" if request.semantic_search else "keyword",
                    "count": len(memories),
                    "memories": [
                        {
                            "id": str(m.id),
                            "content": m.content,
                            "memory_type": m.memory_type,
                            "tags": m.tags,
                            "importance": m.importance,
                            "persona_id": str(m.persona_id) if m.persona_id else None,
                            "similarity": getattr(m, 'similarity', None),
                            "created_at": m.created_at.isoformat(),
                            "updated_at": m.updated_at.isoformat() if m.updated_at else None
                        }
                        for m in memories
                    ]
                }
            
            result = await self.execute_with_session(_recall_memory)
            return self.format_success(result, f"Found {result.get('count', 0)} memories")

        @mcp.tool()
        async def update_memory(
            memory_id: str,
            content: Optional[str] = None,
            tags: Optional[List[str]] = None,
            metadata: Optional[Dict[str, Any]] = None,
            importance: Optional[float] = None
        ) -> Dict[str, Any]:
            """
            Update an existing memory.
            
            Updates memory content and regenerates vector embedding if content changes.
            Allows partial updates of tags, metadata, and importance.
            
            Args:
                memory_id: ID of memory to update
                content: New content (triggers embedding regeneration)
                tags: New tags list
                metadata: New metadata dict
                importance: New importance score
                
            Returns:
                Dict containing updated memory information
            """
            request = MemoryUpdateRequest(
                memory_id=memory_id,
                content=content,
                tags=tags,
                metadata=metadata,
                importance=importance
            )
            
            async def _update_memory(session, services):
                memory_service = services['memory_service']
                
                updates = {}
                if request.content is not None:
                    updates['content'] = request.content
                    # Regenerate embedding if content changed
                    vectorization_service = services['vectorization_service']
                    embedding = await vectorization_service.vectorize_text(request.content)
                    updates['embedding'] = embedding.tolist()
                
                if request.tags is not None:
                    updates['tags'] = request.tags
                if request.metadata is not None:
                    updates['metadata'] = request.metadata
                if request.importance is not None:
                    updates['importance'] = request.importance
                
                memory = await memory_service.update_memory(request.memory_id, updates)
                
                return {
                    "id": str(memory.id),
                    "content": memory.content,
                    "memory_type": memory.memory_type,
                    "tags": memory.tags,
                    "importance": memory.importance,
                    "persona_id": str(memory.persona_id) if memory.persona_id else None,
                    "updated_at": memory.updated_at.isoformat(),
                    "embedding_updated": request.content is not None
                }
            
            result = await self.execute_with_session(_update_memory)
            return self.format_success(result, "Memory updated successfully")

        @mcp.tool()
        async def delete_memory(memory_id: str) -> Dict[str, Any]:
            """
            Delete a memory by ID.
            
            Permanently removes memory and its vector embedding from the database.
            This operation cannot be undone.
            
            Args:
                memory_id: ID of memory to delete
                
            Returns:
                Dict confirming deletion
            """
            async def _delete_memory(session, services):
                memory_service = services['memory_service']
                await memory_service.delete_memory(memory_id)
                
                return {
                    "id": memory_id,
                    "deleted_at": datetime.utcnow().isoformat()
                }
            
            result = await self.execute_with_session(_delete_memory)
            return self.format_success(result, "Memory deleted successfully")

        @mcp.tool()
        async def get_memory_stats() -> Dict[str, Any]:
            """
            Get memory statistics and analytics.
            
            Provides insights into memory usage patterns, types, and distribution.
            
            Returns:
                Dict containing comprehensive memory statistics
            """
            async def _get_memory_stats(session, services):
                memory_service = services['memory_service']
                
                total_memories = await memory_service.count_memories()
                memory_by_type = await memory_service.get_memory_type_distribution()
                memory_by_persona = await memory_service.get_memory_persona_distribution()
                recent_memories = await memory_service.get_recent_memories(limit=5)
                
                return {
                    "total_memories": total_memories,
                    "memory_by_type": memory_by_type,
                    "memory_by_persona": memory_by_persona,
                    "recent_memories": [
                        {
                            "id": str(m.id),
                            "content_preview": m.content[:100] + "..." if len(m.content) > 100 else m.content,
                            "memory_type": m.memory_type,
                            "importance": m.importance,
                            "created_at": m.created_at.isoformat()
                        }
                        for m in recent_memories
                    ],
                    "generated_at": datetime.utcnow().isoformat()
                }
            
            result = await self.execute_with_session(_get_memory_stats)
            return self.format_success(result, "Memory statistics retrieved")

        # Vector optimization tools
        @mcp.tool()
        async def optimize_memory_vectors() -> Dict[str, Any]:
            """
            Optimize memory vector indices for better search performance.
            
            Rebuilds pgvector indices and analyzes query patterns for optimal performance.
            Should be run periodically or when search performance degrades.
            
            Returns:
                Dict containing optimization results and performance metrics
            """
            async def _optimize_vectors(session, services):
                # Analyze current vector statistics
                result = await session.execute("""
                    SELECT 
                        COUNT(*) as total_vectors,
                        AVG(array_length(embedding, 1)) as avg_dimensions
                    FROM memories 
                    WHERE embedding IS NOT NULL
                """)
                stats = result.fetchone()
                
                # Run VACUUM ANALYZE on memories table
                await session.execute("VACUUM ANALYZE memories;")
                await session.commit()
                
                # Reindex vector columns for optimal performance
                await session.execute("REINDEX INDEX ix_memories_embedding;")
                await session.commit()
                
                return {
                    "total_vectors": stats.total_vectors if stats else 0,
                    "avg_dimensions": float(stats.avg_dimensions) if stats and stats.avg_dimensions else 0,
                    "operations_completed": ["vacuum_analyze", "reindex_vectors"],
                    "optimized_at": datetime.utcnow().isoformat()
                }
            
            result = await self.execute_with_session(_optimize_vectors)
            return self.format_success(result, "Vector optimization completed")