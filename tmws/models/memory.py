"""
Memory storage models for TMWS - 404 Perfect Implementation.
Implements the exact database schema specification for memories table.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Float, Integer, Text, CheckConstraint, Index
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql import func

from .base import TMWSBase, MetadataMixin


class Memory(TMWSBase, MetadataMixin):
    """
    Memory storage model implementing the exact TMWS database schema.
    
    Follows the specification:
    - UUID primary key with auto-generation
    - Content with check constraint for non-empty
    - Vector embedding for OpenAI ada-002 (1536 dimensions)
    - JSONB metadata with generated columns for performance
    - Complete timestamp tracking including access patterns
    """
    
    __tablename__ = "memories"
    
    # Core content - matches spec exactly
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Memory content text"
    )
    
    # Vector embedding for semantic search - all-MiniLM-L6-v2 dimension  
    embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(384),
        nullable=True,
        comment="Vector embedding for semantic search (all-MiniLM-L6-v2 dimension)"
    )
    
    # Access tracking - exact spec implementation
    accessed_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        comment="Last access timestamp"
    )
    
    access_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=sa.text("0"),
        comment="Number of times this memory was accessed"
    )
    
    # Virtual columns - accessed via metadata
    # These are not actual database columns but are extracted from metadata
    
    # Table constraints - exact spec
    __table_args__ = (
        CheckConstraint(
            "char_length(content) > 0",
            name="chk_memory_content_not_empty"
        ),
        # Indexes for performance - matching spec exactly
        Index("idx_memories_created_at", "created_at", postgresql_using="btree", postgresql_ops={"created_at": "DESC"}),
        Index("idx_memories_accessed_at", "accessed_at", postgresql_using="btree", postgresql_ops={"accessed_at": "DESC"}),
        Index("idx_memories_metadata", "metadata", postgresql_using="gin"),
        Index("idx_memories_content_trgm", "content", postgresql_using="gin", postgresql_ops={"content": "gin_trgm_ops"}),
        Index("idx_memories_embedding", "embedding", postgresql_using="ivfflat", postgresql_ops={"embedding": "vector_cosine_ops"}, postgresql_with={"lists": 100}),
    )
    
    @hybrid_property
    def persona_direct(self) -> Optional[str]:
        """Direct access to persona from metadata."""
        if self.metadata and 'persona' in self.metadata:
            return self.metadata['persona']
        return None
    
    @hybrid_property
    def importance_direct(self) -> Optional[float]:
        """Direct access to importance from metadata."""
        if self.metadata and 'importance' in self.metadata:
            try:
                return float(self.metadata['importance'])
            except (ValueError, TypeError):
                return None
        return None
    
    @hybrid_property
    def memory_type_direct(self) -> Optional[str]:
        """Direct access to memory type from metadata."""
        if self.metadata and 'type' in self.metadata:
            return self.metadata['type']
        return None
    
    def update_access(self) -> None:
        """Update access tracking when memory is accessed."""
        self.accessed_at = datetime.now()
        self.access_count += 1
    
    def set_persona(self, persona: str) -> None:
        """Set persona in metadata with proper typing."""
        if not self.metadata:
            self.metadata = {}
        self.metadata['persona'] = persona
    
    def set_importance(self, importance: float) -> None:
        """Set importance in metadata with validation."""
        if not 0.0 <= importance <= 1.0:
            raise ValueError("Importance must be between 0.0 and 1.0")
        if not self.metadata:
            self.metadata = {}
        self.metadata['importance'] = importance
    
    def set_memory_type(self, memory_type: str) -> None:
        """Set memory type in metadata."""
        if not self.metadata:
            self.metadata = {}
        self.metadata['type'] = memory_type
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with special handling for vector data."""
        result = super().to_dict()
        # Convert vector to list for JSON serialization
        if self.embedding:
            result['embedding'] = list(self.embedding)
        return result
    
    def __repr__(self) -> str:
        """Enhanced string representation."""
        persona_str = f", persona={self.persona}" if self.persona else ""
        importance_str = f", importance={self.importance}" if self.importance else ""
        return f"<Memory(id={self.id}{persona_str}{importance_str}, content='{self.content[:50]}...')>"


# Compatibility alias for existing code
MemoryVector = Memory