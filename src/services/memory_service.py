"""
Memory Service for TMWS
Handles memory CRUD operations and vector search
"""

import logging
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import numpy as np

from ..models import Memory
from ..core.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


class MemoryService:
    """Service for managing memories with vector search capabilities."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_memory(
        self,
        content: str,
        memory_type: str = "general",
        persona_id: Optional[UUID] = None,
        tags: List[str] = None,
        metadata: Dict[str, Any] = None,
        embedding: List[float] = None,
        importance: float = 0.5
    ) -> Memory:
        """Create a new memory."""
        memory = Memory(
            content=content,
            memory_type=memory_type,
            persona_id=persona_id,
            tags=tags or [],
            metadata_json=metadata or {},
            embedding=embedding,
            importance=importance
        )
        
        self.session.add(memory)
        await self.session.commit()
        await self.session.refresh(memory)
        
        logger.info(f"Created memory {memory.id} with type {memory_type}")
        return memory
    
    async def get_memory(self, memory_id: UUID) -> Optional[Memory]:
        """Get a memory by ID."""
        result = await self.session.execute(
            select(Memory).where(Memory.id == memory_id)
        )
        return result.scalar_one_or_none()
    
    async def update_memory(
        self, 
        memory_id: UUID,
        updates: Dict[str, Any]
    ) -> Memory:
        """Update an existing memory."""
        memory = await self.get_memory(memory_id)
        if not memory:
            raise NotFoundError(f"Memory {memory_id} not found")
        
        for key, value in updates.items():
            if hasattr(memory, key):
                setattr(memory, key, value)
        
        memory.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(memory)
        
        logger.info(f"Updated memory {memory_id}")
        return memory
    
    async def delete_memory(self, memory_id: UUID) -> bool:
        """Delete a memory."""
        memory = await self.get_memory(memory_id)
        if not memory:
            raise NotFoundError(f"Memory {memory_id} not found")
        
        await self.session.delete(memory)
        await self.session.commit()
        
        logger.info(f"Deleted memory {memory_id}")
        return True
    
    async def search_memories(
        self,
        query: str = None,
        memory_type: str = None,
        persona_id: UUID = None,
        tags: List[str] = None,
        limit: int = 10,
        offset: int = 0
    ) -> List[Memory]:
        """Search memories with filters."""
        stmt = select(Memory)
        
        conditions = []
        if query:
            conditions.append(Memory.content.ilike(f"%{query}%"))
        if memory_type:
            conditions.append(Memory.memory_type == memory_type)
        if persona_id:
            conditions.append(Memory.persona_id == persona_id)
        if tags:
            # Check if any of the provided tags are in the memory's tags
            tag_conditions = []
            for tag in tags:
                tag_conditions.append(Memory.tags.contains([tag]))
            conditions.append(or_(*tag_conditions))
        
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        stmt = stmt.order_by(Memory.importance.desc(), Memory.created_at.desc())
        stmt = stmt.limit(limit).offset(offset)
        
        result = await self.session.execute(stmt)
        memories = result.scalars().all()
        
        logger.info(f"Found {len(memories)} memories matching search criteria")
        return memories
    
    async def search_similar_memories(
        self,
        embedding: List[float],
        memory_type: str = None,
        persona_id: UUID = None,
        limit: int = 10,
        min_similarity: float = 0.7
    ) -> List[Memory]:
        """Search for similar memories using vector similarity."""
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
        
        result = await self.session.execute(stmt)
        results = result.all()
        
        # Filter by minimum similarity and add similarity score
        memories = []
        for memory, distance in results:
            similarity = 1 - distance  # Convert distance to similarity
            if similarity >= min_similarity:
                memory.similarity = similarity
                memories.append(memory)
        
        logger.info(f"Found {len(memories)} similar memories")
        return memories
    
    async def count_memories(
        self,
        memory_type: str = None,
        persona_id: UUID = None
    ) -> int:
        """Count memories with optional filters."""
        stmt = select(func.count(Memory.id))
        
        conditions = []
        if memory_type:
            conditions.append(Memory.memory_type == memory_type)
        if persona_id:
            conditions.append(Memory.persona_id == persona_id)
        
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        result = await self.session.execute(stmt)
        count = result.scalar()
        
        return count or 0
    
    async def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        total_count = await self.count_memories()
        
        # Count by type
        type_counts_stmt = select(
            Memory.memory_type,
            func.count(Memory.id).label('count')
        ).group_by(Memory.memory_type)
        
        type_counts_result = await self.session.execute(type_counts_stmt)
        type_counts = {row.memory_type: row.count for row in type_counts_result}
        
        # Average importance
        avg_importance_stmt = select(func.avg(Memory.importance))
        avg_importance_result = await self.session.execute(avg_importance_stmt)
        avg_importance = avg_importance_result.scalar() or 0.0
        
        return {
            "total_memories": total_count,
            "memories_by_type": type_counts,
            "average_importance": float(avg_importance)
        }
    
    async def cleanup_old_memories(
        self,
        days_old: int = 90,
        min_importance: float = 0.3
    ) -> int:
        """Clean up old, low-importance memories."""
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        stmt = select(Memory).where(
            and_(
                Memory.created_at < cutoff_date,
                Memory.importance < min_importance
            )
        )
        
        result = await self.session.execute(stmt)
        memories_to_delete = result.scalars().all()
        
        for memory in memories_to_delete:
            await self.session.delete(memory)
        
        await self.session.commit()
        
        deleted_count = len(memories_to_delete)
        logger.info(f"Cleaned up {deleted_count} old memories")
        
        return deleted_count