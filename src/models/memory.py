"""
Memory v2 models for TMWS - Multi-agent memory with access control and learning support.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Text, DateTime, Boolean, Index, Float, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import TMWSBase, MetadataMixin
from .agent import AccessLevel


class Memory(TMWSBase, MetadataMixin):
    """Enhanced memory model with multi-agent support and learning capabilities."""
    
    __tablename__ = "memories_v2"
    
    # Core content
    content: Mapped[str] = mapped_column(
        Text, 
        nullable=False,
        comment="The actual memory content"
    )
    
    summary: Mapped[Optional[str]] = mapped_column(
        Text, 
        nullable=True,
        comment="Auto-generated summary for long content"
    )
    
    # Agent ownership and namespace
    agent_id: Mapped[str] = mapped_column(
        Text, 
        nullable=False, 
        index=True,
        comment="Owner agent identifier"
    )
    
    namespace: Mapped[str] = mapped_column(
        Text, 
        nullable=False, 
        default="default",
        index=True,
        comment="Namespace for memory isolation"
    )
    
    # Vector embedding for semantic search
    embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(384),  # all-MiniLM-L6-v2 dimension
        nullable=True,
        comment="Vector embedding for semantic search"
    )
    
    # Access control
    access_level: Mapped[AccessLevel] = mapped_column(
        sa.Enum(AccessLevel, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=AccessLevel.PRIVATE,
        index=True,
        comment="Access level for this memory"
    )
    
    shared_with_agents: Mapped[List[str]] = mapped_column(
        JSON, 
        nullable=False, 
        default=list,
        comment="List of agent_ids with explicit access"
    )
    
    # Metadata and context
    context: Mapped[Dict[str, Any]] = mapped_column(
        JSON, 
        nullable=False, 
        default=dict,
        comment="Flexible context metadata"
    )
    
    tags: Mapped[List[str]] = mapped_column(
        JSON, 
        nullable=False, 
        default=list,
        comment="Tags for categorization"
    )
    
    source_url: Mapped[Optional[str]] = mapped_column(
        Text, 
        nullable=True,
        comment="Source URL if applicable"
    )
    
    # Importance and relevance
    importance_score: Mapped[float] = mapped_column(
        Float, 
        nullable=False, 
        default=0.5,
        comment="Importance score (0.0 - 1.0)"
    )
    
    relevance_score: Mapped[float] = mapped_column(
        Float, 
        nullable=False, 
        default=0.5,
        comment="Current relevance score (0.0 - 1.0)"
    )
    
    # Learning support
    access_count: Mapped[int] = mapped_column(
        Integer, 
        nullable=False, 
        default=0,
        comment="Number of times accessed"
    )
    
    learning_weight: Mapped[float] = mapped_column(
        Float, 
        nullable=False, 
        default=1.0,
        comment="Weight for learning algorithms"
    )
    
    pattern_ids: Mapped[List[str]] = mapped_column(
        JSON, 
        nullable=False, 
        default=list,
        comment="Associated learning pattern IDs"
    )
    
    # Temporal aspects
    accessed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Last access timestamp"
    )
    
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Expiration timestamp for temporary memories"
    )
    
    # Versioning for optimistic locking
    version: Mapped[int] = mapped_column(
        Integer, 
        nullable=False, 
        default=1,
        comment="Version for optimistic locking"
    )
    
    # Parent-child relationships for memory consolidation
    parent_memory_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), 
        ForeignKey("memories_v2.id"),
        nullable=True,
        comment="Parent memory for hierarchical organization"
    )
    
    # Indexes for performance
    __table_args__ = (
        Index('ix_memory_agent_namespace', 'agent_id', 'namespace'),
        Index('ix_memory_access_level', 'access_level', 'agent_id'),
        Index('ix_memory_importance', 'importance_score', 'relevance_score'),
        Index('ix_memory_accessed', 'accessed_at', 'access_count'),
        Index('ix_memory_expires', 'expires_at'),
        Index('ix_memory_embedding', 'embedding', postgresql_using='ivfflat', postgresql_ops={'embedding': 'vector_cosine_ops'}),
        Index('ix_memory_tags', 'tags', postgresql_using='gin'),
        Index('ix_memory_context', 'context', postgresql_using='gin'),
    )
    
    def __repr__(self) -> str:
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<Memory(agent='{self.agent_id}', content='{content_preview}')>"
    
    def update_access(self) -> None:
        """Update access metadata."""
        self.access_count += 1
        self.accessed_at = datetime.utcnow()
        # Decay relevance over time, boost by access
        self.relevance_score = min(1.0, self.relevance_score * 0.99 + 0.05)
    
    def update_learning_weight(self, delta: float) -> None:
        """Update learning weight based on usage patterns."""
        self.learning_weight = max(0.1, min(10.0, self.learning_weight + delta))
    
    def is_accessible_by(self, agent_id: str, agent_namespace: str = None) -> bool:
        """Check if memory is accessible by given agent."""
        # Owner always has access
        if agent_id == self.agent_id:
            return True
        
        # Check access level
        if self.access_level == AccessLevel.PUBLIC:
            return True
        elif self.access_level == AccessLevel.SYSTEM:
            return True  # System memories are accessible to all
        elif self.access_level == AccessLevel.SHARED:
            return agent_id in self.shared_with_agents
        elif self.access_level == AccessLevel.TEAM:
            # Check if in same namespace (team)
            return agent_namespace == self.namespace
        else:  # PRIVATE
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert memory to dictionary."""
        return {
            "id": str(self.id),
            "content": self.content,
            "summary": self.summary,
            "agent_id": self.agent_id,
            "namespace": self.namespace,
            "access_level": self.access_level.value,
            "shared_with_agents": self.shared_with_agents,
            "context": self.context,
            "tags": self.tags,
            "source_url": self.source_url,
            "importance_score": self.importance_score,
            "relevance_score": self.relevance_score,
            "access_count": self.access_count,
            "learning_weight": self.learning_weight,
            "pattern_ids": self.pattern_ids,
            "version": self.version,
            "parent_memory_id": str(self.parent_memory_id) if self.parent_memory_id else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "accessed_at": self.accessed_at.isoformat() if self.accessed_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


class MemorySharing(TMWSBase):
    """Explicit memory sharing between agents."""
    
    __tablename__ = "memory_sharing"
    
    memory_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), 
        ForeignKey("memories_v2.id"),
        nullable=False,
        primary_key=True
    )
    
    shared_with_agent_id: Mapped[str] = mapped_column(
        Text, 
        nullable=False,
        primary_key=True
    )
    
    permission: Mapped[str] = mapped_column(
        Text, 
        nullable=False,
        default="read",
        comment="Permission level: read, write, delete"
    )
    
    shared_by_agent_id: Mapped[str] = mapped_column(
        Text, 
        nullable=False,
        comment="Agent who shared the memory"
    )
    
    shared_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow
    )
    
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the sharing expires"
    )
    
    __table_args__ = (
        Index('ix_sharing_agent', 'shared_with_agent_id', 'shared_at'),
        Index('ix_sharing_expires', 'expires_at'),
    )


class MemoryPattern(TMWSBase, MetadataMixin):
    """Learning patterns extracted from memories."""
    
    __tablename__ = "memory_patterns"
    
    pattern_type: Mapped[str] = mapped_column(
        Text, 
        nullable=False,
        comment="Type: sequence, correlation, cluster, etc."
    )
    
    agent_id: Mapped[str] = mapped_column(
        Text, 
        nullable=False, 
        index=True,
        comment="Agent who owns this pattern"
    )
    
    namespace: Mapped[str] = mapped_column(
        Text, 
        nullable=False, 
        index=True
    )
    
    pattern_data: Mapped[Dict[str, Any]] = mapped_column(
        JSON, 
        nullable=False,
        comment="The actual pattern data"
    )
    
    confidence: Mapped[float] = mapped_column(
        Float, 
        nullable=False,
        comment="Confidence score (0.0 - 1.0)"
    )
    
    frequency: Mapped[int] = mapped_column(
        Integer, 
        nullable=False,
        default=1,
        comment="Occurrence frequency"
    )
    
    memory_ids: Mapped[List[str]] = mapped_column(
        JSON, 
        nullable=False,
        default=list,
        comment="Associated memory IDs"
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean, 
        nullable=False, 
        default=True,
        index=True
    )
    
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    __table_args__ = (
        Index('ix_pattern_agent_type', 'agent_id', 'pattern_type'),
        Index('ix_pattern_confidence', 'confidence', 'frequency'),
    )


class MemoryConsolidation(TMWSBase):
    """Track memory consolidation and summarization."""
    
    __tablename__ = "memory_consolidations"
    
    source_memory_ids: Mapped[List[str]] = mapped_column(
        JSON, 
        nullable=False,
        comment="Source memory IDs that were consolidated"
    )
    
    consolidated_memory_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), 
        ForeignKey("memories_v2.id"),
        nullable=False,
        comment="Resulting consolidated memory"
    )
    
    consolidation_type: Mapped[str] = mapped_column(
        Text, 
        nullable=False,
        comment="Type: summary, merge, compress, etc."
    )
    
    agent_id: Mapped[str] = mapped_column(
        Text, 
        nullable=False, 
        index=True
    )
    
    consolidation_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSON, 
        nullable=False,
        default=dict
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow
    )