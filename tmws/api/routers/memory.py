"""
Memory management endpoints for TMWS.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_

from ...core.database import get_db_session_dependency
from ...models.memory import Memory, MemoryVector
from ...services.vectorization_service import VectorizationService
from ..security import get_current_user, sanitize_input

logger = logging.getLogger(__name__)
router = APIRouter()


# Request/Response Models
class MemoryCreate(BaseModel):
    """Memory creation request."""
    content: str = Field(..., min_length=1, max_length=10000)
    persona: Optional[str] = Field(None, max_length=50)
    category: Optional[str] = Field(None, max_length=100)
    importance: float = Field(0.5, ge=0.0, le=1.0)
    is_shared: bool = Field(False)
    is_learned: bool = Field(False)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @validator('content', 'persona', 'category', pre=True)
    def sanitize_strings(cls, v):
        if isinstance(v, str):
            return sanitize_input(v)
        return v


class MemoryUpdate(BaseModel):
    """Memory update request."""
    content: Optional[str] = Field(None, min_length=1, max_length=10000)
    persona: Optional[str] = Field(None, max_length=50)
    category: Optional[str] = Field(None, max_length=100)
    importance: Optional[float] = Field(None, ge=0.0, le=1.0)
    is_shared: Optional[bool] = None
    is_learned: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None
    
    @validator('content', 'persona', 'category', pre=True)
    def sanitize_strings(cls, v):
        if isinstance(v, str):
            return sanitize_input(v)
        return v


class MemorySearch(BaseModel):
    """Memory search request."""
    query: Optional[str] = Field(None, max_length=1000)
    persona: Optional[str] = Field(None, max_length=50)
    category: Optional[str] = Field(None, max_length=100)
    is_shared: Optional[bool] = None
    is_learned: Optional[bool] = None
    min_importance: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_importance: Optional[float] = Field(None, ge=0.0, le=1.0)
    limit: int = Field(10, ge=1, le=100)
    offset: int = Field(0, ge=0)
    semantic_search: bool = Field(False, description="Enable semantic search")
    min_similarity: float = Field(0.7, ge=0.0, le=1.0, description="Minimum similarity for semantic search")
    
    @validator('query', 'persona', 'category', pre=True)
    def sanitize_strings(cls, v):
        if isinstance(v, str):
            return sanitize_input(v)
        return v


class MemoryResponse(BaseModel):
    """Memory response model."""
    id: str
    content: str
    persona: Optional[str]
    category: Optional[str]
    importance: float
    is_shared: bool
    is_learned: bool
    metadata: Dict[str, Any]
    access_count: int
    created_at: datetime
    updated_at: datetime
    accessed_at: datetime
    
    class Config:
        from_attributes = True

class SemanticMemoryResponse(MemoryResponse):
    """Memory response model for semantic search."""
    similarity: float

class MemoryListResponse(BaseModel):
    """Memory list response."""
    memories: List[Union[MemoryResponse, SemanticMemoryResponse]]
    total: int
    offset: int
    limit: int
    has_more: bool


# Endpoints
@router.post("/", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
async def create_memory(
    memory_data: MemoryCreate,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> MemoryResponse:
    """
    Create a new memory.
    
    Args:
        memory_data: Memory creation data
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Created memory
    """
    try:
        # Vectorize content
        vectorization_service = VectorizationService()
        embedding = await vectorization_service.vectorize_text(memory_data.content)

        # Build metadata including all extra fields
        metadata = memory_data.metadata or {}
        if memory_data.persona:
            metadata['persona'] = memory_data.persona
        if memory_data.category:
            metadata['category'] = memory_data.category
        metadata['importance'] = memory_data.importance
        metadata['is_shared'] = memory_data.is_shared
        metadata['is_learned'] = memory_data.is_learned
        
        # Create memory
        memory = Memory(
            content=memory_data.content,
            embedding=embedding.tolist(),
            metadata=metadata,
        )
        
        db.add(memory)
        await db.commit()
        await db.refresh(memory)
        
        logger.info(f"Memory created: {memory.id} by user {current_user.get('username')}")
        
        return MemoryResponse(
            id=str(memory.id),
            content=memory.content,
            persona=memory.metadata.get('persona') if memory.metadata else None,
            category=memory.metadata.get('category') if memory.metadata else None,
            importance=memory.metadata.get('importance', 0.5) if memory.metadata else 0.5,
            is_shared=memory.metadata.get('is_shared', False) if memory.metadata else False,
            is_learned=memory.metadata.get('is_learned', False) if memory.metadata else False,
            metadata=memory.metadata or {},
            access_count=memory.access_count,
            created_at=memory.created_at,
            updated_at=memory.updated_at,
            accessed_at=memory.accessed_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create memory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create memory"
        )


@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: UUID,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> MemoryResponse:
    """
    Get a specific memory by ID.
    
    Args:
        memory_id: Memory ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Memory data
    """
    try:
        memory = await db.get(Memory, memory_id)
        
        if not memory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Memory not found"
            )
        
        # Update access tracking
        memory.update_access()
        await db.commit()
        
        return MemoryResponse(
            id=str(memory.id),
            content=memory.content,
            persona=memory.metadata.get('persona') if memory.metadata else None,
            category=memory.metadata.get('category') if memory.metadata else None,
            importance=memory.metadata.get('importance', 0.5) if memory.metadata else 0.5,
            is_shared=memory.metadata.get('is_shared', False) if memory.metadata else False,
            is_learned=memory.metadata.get('is_learned', False) if memory.metadata else False,
            metadata=memory.metadata or {},
            access_count=memory.access_count,
            created_at=memory.created_at,
            updated_at=memory.updated_at,
            accessed_at=memory.accessed_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get memory {memory_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve memory"
        )


@router.put("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: UUID,
    memory_data: MemoryUpdate,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> MemoryResponse:
    """
    Update a specific memory.
    
    Args:
        memory_id: Memory ID
        memory_data: Memory update data
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Updated memory
    """
    try:
        memory = await db.get(Memory, memory_id)
        
        if not memory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Memory not found"
            )
        
        # Update fields
        update_data = memory_data.dict(exclude_unset=True)
        if 'content' in update_data:
            # Vectorize content
            vectorization_service = VectorizationService()
            embedding = await vectorization_service.vectorize_text(update_data['content'])
            memory.embedding = embedding.tolist()

        for field, value in update_data.items():
            setattr(memory, field, value)
        
        memory.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(memory)
        
        logger.info(f"Memory updated: {memory.key} by user {current_user.get('id')}")
        
        return MemoryResponse(
            id=str(memory.id),
            content=memory.content,
            persona=memory.metadata.get('persona') if memory.metadata else None,
            category=memory.metadata.get('category') if memory.metadata else None,
            importance=memory.metadata.get('importance', 0.5) if memory.metadata else 0.5,
            is_shared=memory.metadata.get('is_shared', False) if memory.metadata else False,
            is_learned=memory.metadata.get('is_learned', False) if memory.metadata else False,
            metadata=memory.metadata or {},
            access_count=memory.access_count,
            created_at=memory.created_at,
            updated_at=memory.updated_at,
            accessed_at=memory.accessed_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update memory {memory_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update memory"
        )


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: UUID,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Delete a specific memory.
    
    Args:
        memory_id: Memory ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Deletion confirmation
    """
    try:
        memory = await db.get(Memory, memory_id)
        
        if not memory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Memory not found"
            )
        
        memory_key = memory.key
        await db.delete(memory)
        await db.commit()
        
        logger.info(f"Memory deleted: {memory_key} by user {current_user.get('id')}")
        
        return {"message": f"Memory '{memory_key}' deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete memory {memory_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete memory"
        )


@router.post("/search", response_model=MemoryListResponse)
async def search_memories(
    search_data: MemorySearch,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> MemoryListResponse:
    """
    Search memories with various filters.
    
    Args:
        search_data: Search criteria
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List of matching memories
    """
    try:
        # Build query
        query = select(Memory)
        conditions = []
        
        # Semantic search
        if search_data.semantic_search and search_data.query:
            vectorization_service = VectorizationService()
            query_embedding = await vectorization_service.vectorize_text(search_data.query)
            
            query = query.add_columns(Memory.embedding.l2_distance(query_embedding).label("similarity"))
            conditions.append(Memory.embedding.l2_distance(query_embedding) < (1 - search_data.min_similarity))
            order_by = "similarity"
        # Text search
        elif search_data.query:
            conditions.append(
                or_(
                    Memory.key.ilike(f"%{search_data.query}%"),
                    Memory.content.ilike(f"%{search_data.query}%")
                )
            )
            order_by = None
        else:
            order_by = None

        # Filter by persona
        if search_data.persona:
            conditions.append(Memory.persona == search_data.persona)
        
        # Filter by category
        if search_data.category:
            conditions.append(Memory.category == search_data.category)
        
        # Filter by shared status
        if search_data.is_shared is not None:
            conditions.append(Memory.is_shared == search_data.is_shared)
        
        # Filter by learned status
        if search_data.is_learned is not None:
            conditions.append(Memory.is_learned == search_data.is_learned)
        
        # Filter by importance range
        if search_data.min_importance is not None:
            conditions.append(Memory.importance >= search_data.min_importance)
        
        if search_data.max_importance is not None:
            conditions.append(Memory.importance <= search_data.max_importance)
        
        # Apply conditions
        if conditions:
            query = query.where(and_(*conditions))
        
        # Count total results
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Apply ordering, offset, and limit
        if order_by == "similarity":
            query = query.order_by("similarity")
        else:
            query = query.order_by(Memory.importance.desc(), Memory.updated_at.desc())

        query = query.offset(search_data.offset).limit(search_data.limit)
        
        # Execute query
        result = await db.execute(query)
        
        memories = []
        if search_data.semantic_search and search_data.query:
            for row in result.all():
                memory = row[0]
                similarity = row[1]
                mem_resp = SemanticMemoryResponse.from_orm(memory)
                mem_resp.similarity = 1 - similarity
                memories.append(mem_resp)
        else:
            memories = [MemoryResponse.from_orm(memory) for memory in result.scalars().all()]

        return MemoryListResponse(
            memories=memories,
            total=total,
            offset=search_data.offset,
            limit=search_data.limit,
            has_more=search_data.offset + len(memories) < total
        )
        
    except Exception as e:
        logger.error(f"Failed to search memories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search memories"
        )


@router.get("/", response_model=MemoryListResponse)
async def list_memories(
    persona: Optional[str] = Query(None, max_length=50),
    category: Optional[str] = Query(None, max_length=100),
    is_shared: Optional[bool] = Query(None),
    is_learned: Optional[bool] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> MemoryListResponse:
    """
    List memories with optional filters.
    
    Args:
        persona: Filter by persona
        category: Filter by category
        is_shared: Filter by shared status
        is_learned: Filter by learned status
        limit: Maximum number of results
        offset: Number of results to skip
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List of memories
    """
    search_data = MemorySearch(
        persona=persona,
        category=category,
        is_shared=is_shared,
        is_learned=is_learned,
        limit=limit,
        offset=offset
    )
    
    return await search_memories(search_data, db, current_user)


@router.get("/stats/summary")
async def get_memory_stats(
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get memory statistics summary.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Memory statistics
    """
    try:
        # Total memories
        total_result = await db.execute(select(func.count(Memory.id)))
        total_memories = total_result.scalar()
        
        # Memories by persona
        persona_stats = await db.execute(
            select(Memory.persona, func.count(Memory.id))
            .group_by(Memory.persona)
        )
        persona_counts = {persona: count for persona, count in persona_stats.all()}
        
        # Memories by category
        category_stats = await db.execute(
            select(Memory.category, func.count(Memory.id))
            .group_by(Memory.category)
        )
        category_counts = {category: count for category, count in category_stats.all()}
        
        # Shared vs private
        shared_stats = await db.execute(
            select(Memory.is_shared, func.count(Memory.id))
            .group_by(Memory.is_shared)
        )
        shared_counts = {shared: count for shared, count in shared_stats.all()}
        
        # Learned memories
        learned_result = await db.execute(
            select(func.count(Memory.id)).where(Memory.is_learned == True)
        )
        learned_memories = learned_result.scalar()
        
        # Average importance
        avg_importance_result = await db.execute(
            select(func.avg(Memory.importance))
        )
        avg_importance = avg_importance_result.scalar() or 0.0
        
        return {
            "total_memories": total_memories,
            "learned_memories": learned_memories,
            "average_importance": round(float(avg_importance), 3),
            "by_persona": persona_counts,
            "by_category": category_counts,
            "shared_distribution": {
                "shared": shared_counts.get(True, 0),
                "private": shared_counts.get(False, 0)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get memory stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get memory statistics"
        )