"""
Unified Memory Service for TMWS
Works with the unified database manager for shared access
"""

import logging
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np

from ..models import Memory
from ..core.exceptions import NotFoundError, ValidationError
from ..core.unified_database import get_unified_db_manager

logger = logging.getLogger(__name__)


class UnifiedMemoryService:
    """
    Unified Memory Service that uses the shared database pool
    Optimized for concurrent access from both FastMCP and FastAPI
    """
    
    def __init__(self, db_manager=None):
        """
        Initialize the unified memory service
        
        Args:
            db_manager: Optional database manager, if None uses the global unified manager
        """
        self.db_manager = db_manager or get_unified_db_manager()
        self._memory_cache = {}  # Simple in-memory cache
        self._cache_ttl = 300  # 5 minutes
        
    async def initialize(self):
        """Initialize the memory service"""
        # Ensure database is initialized
        if not self.db_manager.is_initialized:
            await self.db_manager.initialize()
        
        logger.info("[UNIFIED] Memory service initialized with shared database pool")
        return True
    
    async def cleanup(self):
        """Cleanup resources"""
        self._memory_cache.clear()
        logger.info("[UNIFIED] Memory service cleanup complete")
    
    async def create_memory(
        self,
        content: str,
        memory_type: str = "general",
        persona_id: Optional[UUID] = None,
        tags: List[str] = None,
        metadata: Dict[str, Any] = None,
        embedding: List[float] = None,
        importance: float = 0.5,
        service_name: str = "unified"
    ) -> Memory:
        """Create a new memory using the unified database"""
        async with self.db_manager.get_session(f"{service_name}_create") as session:
            memory = Memory(
                content=content,
                memory_type=memory_type,
                persona_id=persona_id,
                tags=tags or [],
                metadata_json=metadata or {},
                embedding=embedding,
                importance=importance
            )
            
            session.add(memory)
            await session.commit()
            await session.refresh(memory)
            
            # Cache the memory
            self._cache_memory(memory)
            
            logger.info(f"[{service_name}] Created memory {memory.id} with type {memory_type}")
            return memory
    
    async def get_memory(
        self, 
        memory_id: UUID, 
        service_name: str = "unified",
        use_cache: bool = True
    ) -> Optional[Memory]:
        """Get a memory by ID with caching"""
        # Check cache first
        if use_cache and memory_id in self._memory_cache:
            cached = self._memory_cache[memory_id]
            if cached['expires'] > datetime.utcnow():
                logger.debug(f"[CACHE HIT] Memory {memory_id}")
                return cached['memory']
        
        async with self.db_manager.get_session(f"{service_name}_get") as session:
            result = await session.execute(
                select(Memory).where(Memory.id == memory_id)
            )
            memory = result.scalar_one_or_none()
            
            if memory:
                self._cache_memory(memory)
            
            return memory
    
    async def update_memory(
        self, 
        memory_id: UUID,
        updates: Dict[str, Any],
        service_name: str = "unified"
    ) -> Memory:
        """Update an existing memory"""
        async with self.db_manager.get_session(f"{service_name}_update") as session:
            result = await session.execute(
                select(Memory).where(Memory.id == memory_id)
            )
            memory = result.scalar_one_or_none()
            
            if not memory:
                raise NotFoundError(f"Memory {memory_id} not found")
            
            for key, value in updates.items():
                if hasattr(memory, key):
                    setattr(memory, key, value)
            
            memory.updated_at = datetime.utcnow()
            await session.commit()
            await session.refresh(memory)
            
            # Invalidate cache
            self._invalidate_cache(memory_id)
            
            logger.info(f"[{service_name}] Updated memory {memory_id}")
            return memory
    
    async def delete_memory(
        self, 
        memory_id: UUID,
        service_name: str = "unified"
    ) -> bool:
        """Delete a memory"""
        async with self.db_manager.get_session(f"{service_name}_delete") as session:
            result = await session.execute(
                select(Memory).where(Memory.id == memory_id)
            )
            memory = result.scalar_one_or_none()
            
            if not memory:
                raise NotFoundError(f"Memory {memory_id} not found")
            
            await session.delete(memory)
            await session.commit()
            
            # Invalidate cache
            self._invalidate_cache(memory_id)
            
            logger.info(f"[{service_name}] Deleted memory {memory_id}")
            return True
    
    async def search_memories(
        self,
        query: str = None,
        memory_type: str = None,
        persona_id: UUID = None,
        tags: List[str] = None,
        limit: int = 10,
        offset: int = 0,
        service_name: str = "unified"
    ) -> List[Memory]:
        """Search memories with filters"""
        async with self.db_manager.get_session(f"{service_name}_search") as session:
            stmt = select(Memory)
            
            conditions = []
            if query:
                conditions.append(Memory.content.ilike(f"%{query}%"))
            if memory_type:
                conditions.append(Memory.memory_type == memory_type)
            if persona_id:
                conditions.append(Memory.persona_id == persona_id)
            if tags:
                tag_conditions = []
                for tag in tags:
                    tag_conditions.append(Memory.tags.contains([tag]))
                conditions.append(or_(*tag_conditions))
            
            if conditions:
                stmt = stmt.where(and_(*conditions))
            
            stmt = stmt.order_by(Memory.importance.desc(), Memory.created_at.desc())
            stmt = stmt.limit(limit).offset(offset)
            
            result = await session.execute(stmt)
            memories = result.scalars().all()
            
            # Cache results
            for memory in memories:
                self._cache_memory(memory)
            
            logger.info(f"[{service_name}] Found {len(memories)} memories matching search criteria")
            return memories
    
    async def search_similar_memories(
        self,
        embedding: List[float],
        memory_type: str = None,
        persona_id: UUID = None,
        limit: int = 10,
        min_similarity: float = 0.7,
        service_name: str = "unified"
    ) -> List[Memory]:
        """Search for similar memories using vector similarity"""
        async with self.db_manager.get_session(f"{service_name}_vector_search") as session:
            # Convert embedding to numpy array for pgvector
            query_vector = np.array(embedding)
            
            # Build the similarity search query
            stmt = select(
                Memory,
                Memory.embedding.cosine_distance(query_vector).label('distance')
            )
            
            # Add filters
            conditions = []
            if memory_type:
                conditions.append(Memory.memory_type == memory_type)
            if persona_id:
                conditions.append(Memory.persona_id == persona_id)
            
            if conditions:
                stmt = stmt.where(and_(*conditions))
            
            # Order by similarity (lower distance = higher similarity)
            stmt = stmt.order_by('distance')
            stmt = stmt.limit(limit)
            
            result = await session.execute(stmt)
            results = result.all()
            
            # Filter by minimum similarity and add similarity score
            memories = []
            for memory, distance in results:
                similarity = 1 - distance  # Convert distance to similarity
                if similarity >= min_similarity:
                    memory.similarity = similarity
                    memories.append(memory)
                    # Cache the memory
                    self._cache_memory(memory)
            
            logger.info(f"[{service_name}] Found {len(memories)} similar memories")
            return memories
    
    async def get_memory_stats(self, service_name: str = "unified") -> Dict[str, Any]:
        """Get comprehensive memory statistics"""
        async with self.db_manager.get_session(f"{service_name}_stats") as session:
            # Total count
            total_count = await session.scalar(select(func.count(Memory.id)))
            
            # Count by type
            type_counts_stmt = select(
                Memory.memory_type,
                func.count(Memory.id).label('count')
            ).group_by(Memory.memory_type)
            
            type_counts_result = await session.execute(type_counts_stmt)
            type_counts = {row.memory_type: row.count for row in type_counts_result}
            
            # Average importance
            avg_importance = await session.scalar(select(func.avg(Memory.importance)))
            
            # Cache statistics
            cache_stats = {
                "cache_size": len(self._memory_cache),
                "cache_hit_rate": self._calculate_cache_hit_rate()
            }
            
            return {
                "total_memories": total_count or 0,
                "memories_by_type": type_counts,
                "average_importance": float(avg_importance or 0.0),
                "cache_stats": cache_stats,
                "db_health": await self.db_manager.health_check()
            }
    
    # Cache management methods
    def _cache_memory(self, memory: Memory):
        """Cache a memory with TTL"""
        self._memory_cache[memory.id] = {
            'memory': memory,
            'expires': datetime.utcnow() + timedelta(seconds=self._cache_ttl)
        }
    
    def _invalidate_cache(self, memory_id: UUID):
        """Invalidate a cached memory"""
        if memory_id in self._memory_cache:
            del self._memory_cache[memory_id]
    
    def _calculate_cache_hit_rate(self) -> float:
        """Calculate cache hit rate (placeholder)"""
        # In a real implementation, track hits and misses
        return 0.0 if not self._memory_cache else len(self._memory_cache) / 100.0
    
    async def cleanup_old_memories(
        self,
        days_old: int = 90,
        min_importance: float = 0.3,
        service_name: str = "unified"
    ) -> int:
        """Clean up old, low-importance memories"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        async with self.db_manager.get_session(f"{service_name}_cleanup") as session:
            stmt = select(Memory).where(
                and_(
                    Memory.created_at < cutoff_date,
                    Memory.importance < min_importance
                )
            )
            
            result = await session.execute(stmt)
            memories_to_delete = result.scalars().all()
            
            for memory in memories_to_delete:
                await session.delete(memory)
                self._invalidate_cache(memory.id)
            
            await session.commit()
            
            deleted_count = len(memories_to_delete)
            logger.info(f"[{service_name}] Cleaned up {deleted_count} old memories")
            
            return deleted_count