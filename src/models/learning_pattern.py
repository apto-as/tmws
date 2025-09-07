"""
Learning patterns management models for TMWS v2.0 - Universal Multi-Agent Platform.
Enhanced with agent-centric design and namespace isolation.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional, List
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import String, Integer, Float, Text, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import TMWSBase, MetadataMixin


class LearningPattern(TMWSBase, MetadataMixin):
    """
    Enhanced Learning pattern model with agent-centric design.
    
    Key improvements:
    - agent_id support for multi-agent environments
    - namespace-based pattern organization
    - hierarchical access levels (private, shared, public)
    - pattern versioning and evolution tracking
    - collaborative learning capabilities
    - performance optimization with selective indexing
    """
    
    __tablename__ = "learning_patterns_v2"
    
    # Pattern identification
    pattern_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Pattern name identifier"
    )
    
    # Agent-centric design
    agent_id: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        index=True,
        comment="Owner agent identifier (null for system patterns)"
    )
    
    # Namespace organization
    namespace: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="default",
        server_default=sa.text("'default'"),
        index=True,
        comment="Pattern namespace for organization and isolation"
    )
    
    # Pattern classification
    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Pattern category classification"
    )
    
    subcategory: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Pattern subcategory for fine-grained classification"
    )
    
    # Access control
    access_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="private",
        server_default=sa.text("'private'"),
        comment="Access level: private, shared, public, system"
    )
    
    # Pattern data
    pattern_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Pattern data structure with enhanced schema"
    )
    
    # Pattern versioning
    version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="1.0.0",
        server_default=sa.text("'1.0.0'"),
        comment="Pattern version for evolution tracking"
    )
    
    parent_pattern_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        sa.ForeignKey("learning_patterns_v2.id", ondelete="SET NULL"),
        nullable=True,
        comment="Parent pattern for versioning hierarchy"
    )
    
    # Usage analytics
    usage_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=sa.text("0"),
        comment="Total usage count across all agents"
    )
    
    agent_usage_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=sa.text("0"),
        comment="Usage count by the owner agent"
    )
    
    success_rate: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default=sa.text("0.0"),
        comment="Overall success rate (0.0-1.0)"
    )
    
    agent_success_rate: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default=sa.text("0.0"),
        comment="Success rate for the owner agent (0.0-1.0)"
    )
    
    # Performance tracking
    avg_execution_time: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Average execution time in seconds"
    )
    
    complexity_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Pattern complexity score for optimization"
    )
    
    # Timestamp tracking
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
        comment="Last usage timestamp"
    )
    
    last_agent_used_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
        comment="Last usage by owner agent"
    )
    
    # Collaborative features
    shared_with_agents: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="List of agent IDs with shared access"
    )
    
    # Learning metrics
    learning_weight: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        server_default=sa.text("1.0"),
        comment="Weight for learning algorithms"
    )
    
    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.5,
        server_default=sa.text("0.5"),
        comment="Confidence in pattern effectiveness"
    )
    
    # Relationships
    parent_pattern = relationship(
        "LearningPattern",
        remote_side="LearningPattern.id",
        back_populates="child_patterns"
    )
    
    child_patterns = relationship(
        "LearningPattern",
        back_populates="parent_pattern",
        cascade="all, delete-orphan"
    )
    
    # Table constraints and indexes
    __table_args__ = (
        # Unique constraints
        sa.UniqueConstraint(
            "pattern_name", "namespace", "agent_id",
            name="uq_learning_patterns_name_namespace_agent"
        ),
        
        # Check constraints
        CheckConstraint(
            "access_level IN ('private', 'shared', 'public', 'system')",
            name="ck_learning_patterns_access_level"
        ),
        CheckConstraint(
            "success_rate >= 0.0 AND success_rate <= 1.0",
            name="ck_learning_patterns_success_rate"
        ),
        CheckConstraint(
            "agent_success_rate >= 0.0 AND agent_success_rate <= 1.0",
            name="ck_learning_patterns_agent_success_rate"
        ),
        CheckConstraint(
            "confidence_score >= 0.0 AND confidence_score <= 1.0",
            name="ck_learning_patterns_confidence_score"
        ),
        CheckConstraint(
            "usage_count >= 0",
            name="ck_learning_patterns_usage_count"
        ),
        CheckConstraint(
            "agent_usage_count >= 0",
            name="ck_learning_patterns_agent_usage_count"
        ),
        
        # Performance indexes
        Index(
            "idx_learning_patterns_v2_agent_namespace",
            "agent_id", "namespace"
        ),
        Index(
            "idx_learning_patterns_v2_category_access",
            "category", "access_level"
        ),
        Index(
            "idx_learning_patterns_v2_usage_performance",
            "usage_count", "success_rate",
            postgresql_ops={"usage_count": "DESC", "success_rate": "DESC"}
        ),
        Index(
            "idx_learning_patterns_v2_agent_performance",
            "agent_id", "agent_usage_count", "agent_success_rate",
            postgresql_ops={"agent_usage_count": "DESC", "agent_success_rate": "DESC"}
        ),
        Index(
            "idx_learning_patterns_v2_shared_access",
            "shared_with_agents",
            postgresql_using="gin"
        ),
        Index(
            "idx_learning_patterns_v2_pattern_data",
            "pattern_data",
            postgresql_using="gin"
        ),
        Index(
            "idx_learning_patterns_v2_metadata",
            "metadata",
            postgresql_using="gin"
        ),
        Index(
            "idx_learning_patterns_v2_last_used",
            "last_used_at",
            postgresql_ops={"last_used_at": "DESC"}
        ),
    )
    
    def increment_usage(self, by_owner: bool = False, execution_time: Optional[float] = None) -> None:
        """Increment usage count and update timestamps."""
        self.usage_count += 1
        self.last_used_at = func.now()
        
        if by_owner:
            self.agent_usage_count += 1
            self.last_agent_used_at = func.now()
        
        # Update average execution time
        if execution_time is not None:
            if self.avg_execution_time is None:
                self.avg_execution_time = execution_time
            else:
                # Exponential moving average
                alpha = 0.1
                self.avg_execution_time = (1 - alpha) * self.avg_execution_time + alpha * execution_time
    
    def update_success_rate(self, success: bool, by_owner: bool = False) -> None:
        """Update success rate based on outcome."""
        # Update overall success rate
        if self.usage_count <= 1:
            self.success_rate = 1.0 if success else 0.0
        else:
            current_successes = self.success_rate * (self.usage_count - 1)
            if success:
                current_successes += 1
            self.success_rate = current_successes / self.usage_count
        
        # Update agent-specific success rate
        if by_owner:
            if self.agent_usage_count <= 1:
                self.agent_success_rate = 1.0 if success else 0.0
            else:
                current_agent_successes = self.agent_success_rate * (self.agent_usage_count - 1)
                if success:
                    current_agent_successes += 1
                self.agent_success_rate = current_agent_successes / self.agent_usage_count
        
        # Update confidence score based on success rate and usage count
        self._update_confidence_score()
    
    def _update_confidence_score(self) -> None:
        """Update confidence score based on usage patterns."""
        if self.usage_count == 0:
            self.confidence_score = 0.5
        else:
            # Confidence increases with usage and success rate
            usage_factor = min(1.0, self.usage_count / 10.0)  # Max confidence at 10+ uses
            success_factor = self.success_rate
            self.confidence_score = 0.3 + 0.7 * (usage_factor * success_factor)
    
    def grant_access(self, agent_id: str) -> None:
        """Grant access to another agent."""
        if self.shared_with_agents is None:
            self.shared_with_agents = []
        if agent_id not in self.shared_with_agents:
            self.shared_with_agents.append(agent_id)
    
    def revoke_access(self, agent_id: str) -> None:
        """Revoke access from an agent."""
        if self.shared_with_agents and agent_id in self.shared_with_agents:
            self.shared_with_agents.remove(agent_id)
    
    def can_access(self, agent_id: Optional[str]) -> bool:
        """Check if an agent can access this pattern."""
        if self.access_level == "public" or self.access_level == "system":
            return True
        if self.access_level == "private" and self.agent_id == agent_id:
            return True
        if self.access_level == "shared":
            return (self.agent_id == agent_id or 
                   (self.shared_with_agents and agent_id in self.shared_with_agents))
        return False
    
    def create_version(self, new_version: str, pattern_data: Dict[str, Any]) -> "LearningPattern":
        """Create a new version of this pattern."""
        new_pattern = LearningPattern(
            pattern_name=self.pattern_name,
            agent_id=self.agent_id,
            namespace=self.namespace,
            category=self.category,
            subcategory=self.subcategory,
            access_level=self.access_level,
            pattern_data=pattern_data,
            version=new_version,
            parent_pattern_id=self.id,
            learning_weight=self.learning_weight,
            confidence_score=0.5,  # Reset confidence for new version
            shared_with_agents=self.shared_with_agents.copy() if self.shared_with_agents else None
        )
        return new_pattern
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "id": str(self.id),
            "pattern_name": self.pattern_name,
            "namespace": self.namespace,
            "category": self.category,
            "subcategory": self.subcategory,
            "access_level": self.access_level,
            "pattern_data": self.pattern_data,
            "version": self.version,
            "usage_count": self.usage_count,
            "success_rate": self.success_rate,
            "avg_execution_time": self.avg_execution_time,
            "complexity_score": self.complexity_score,
            "confidence_score": self.confidence_score,
            "learning_weight": self.learning_weight,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
        
        if include_sensitive:
            result.update({
                "agent_id": self.agent_id,
                "agent_usage_count": self.agent_usage_count,
                "agent_success_rate": self.agent_success_rate,
                "last_agent_used_at": self.last_agent_used_at.isoformat() if self.last_agent_used_at else None,
                "shared_with_agents": self.shared_with_agents,
                "parent_pattern_id": str(self.parent_pattern_id) if self.parent_pattern_id else None,
                "metadata": self.metadata
            })
        
        return result


class PatternUsageHistory(TMWSBase):
    """
    Track pattern usage history for analytics and optimization.
    """
    
    __tablename__ = "pattern_usage_history"
    
    pattern_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        sa.ForeignKey("learning_patterns_v2.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    agent_id: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        index=True
    )
    
    used_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now()
    )
    
    execution_time: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Execution time in seconds"
    )
    
    success: Mapped[Optional[bool]] = mapped_column(
        sa.Boolean,
        nullable=True,
        comment="Whether the pattern usage was successful"
    )
    
    context_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Context information about the usage"
    )
    
    # Relationships
    pattern = relationship("LearningPattern", backref="usage_history")
    
    __table_args__ = (
        Index("idx_pattern_usage_history_pattern_time", "pattern_id", "used_at"),
        Index("idx_pattern_usage_history_agent_time", "agent_id", "used_at"),
        Index("idx_pattern_usage_history_context", "context_data", postgresql_using="gin"),
    )