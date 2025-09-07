"""
Learning patterns management models for TMWS - 404 Perfect Implementation.
Implements the exact database schema specification for learning_patterns table.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import String, Integer, Numeric, CheckConstraint, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import TMWSBase, MetadataMixin


class LearningPattern(TMWSBase, MetadataMixin):
    """
    Learning pattern model implementing the exact TMWS database schema.
    
    Follows the specification:
    - UUID primary key with auto-generation
    - Unique pattern name with category classification
    - JSONB pattern data for flexible storage
    - Usage tracking with count and success rate
    - Complete timestamp tracking including last used
    - JSONB metadata for extensibility
    """
    
    __tablename__ = "learning_patterns"
    
    # Core pattern fields - matches spec exactly
    pattern_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        comment="Unique pattern name identifier"
    )
    
    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Pattern category classification"
    )
    
    pattern_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Pattern data structure in JSON format"
    )
    
    # Usage tracking - exact spec implementation
    usage_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=sa.text("0"),
        comment="Number of times pattern was used"
    )
    
    success_rate: Mapped[float] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=0.00,
        server_default=sa.text("0.00"),
        comment="Pattern success rate percentage"
    )
    
    # Timestamp tracking - exact spec
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
        comment="Last time pattern was used"
    )
    
    # Table constraints - exact spec
    __table_args__ = (
        # Indexes for performance - matching spec exactly
        Index("idx_learning_patterns_category", "category"),
        Index("idx_learning_patterns_usage_count", "usage_count", postgresql_ops={"usage_count": "DESC"}),
        Index("idx_learning_patterns_success_rate", "success_rate", postgresql_ops={"success_rate": "DESC"}),
        Index("idx_learning_patterns_metadata", "metadata", postgresql_using="gin"),
    )
    
    def increment_usage(self) -> None:
        """Increment usage count and update last used timestamp."""
        self.usage_count += 1
        self.last_used_at = datetime.now()
    
    def update_success_rate(self, success: bool) -> None:
        """Update success rate based on outcome."""
        if self.usage_count == 0:
            # First usage
            self.success_rate = 100.0 if success else 0.0
        else:
            # Calculate new success rate
            current_successes = (self.success_rate / 100.0) * (self.usage_count - 1)
            if success:
                current_successes += 1
            new_rate = (current_successes / self.usage_count) * 100.0
            self.success_rate = round(new_rate, 2)
    
    def record_usage(self, success: bool) -> None:
        """Record a pattern usage with success outcome."""
        self.increment_usage()
        self.update_success_rate(success)
    
    def set_pattern_data(self, data: Dict[str, Any]) -> None:
        """Set pattern data with validation."""
        if not isinstance(data, dict):
            raise ValueError("Pattern data must be a dictionary")
        self.pattern_data = data
    
    def get_pattern_data(self) -> Dict[str, Any]:
        """Get pattern data safely."""
        return self.pattern_data or {}
    
    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata key-value pair."""
        if not self.metadata:
            self.metadata = {}
        self.metadata[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value safely."""
        if not self.metadata:
            return default
        return self.metadata.get(key, default)
    
    @property
    def is_successful(self) -> bool:
        """Check if pattern has good success rate (>= 70%)."""
        return self.success_rate >= 70.0
    
    @property
    def is_frequently_used(self) -> bool:
        """Check if pattern is frequently used (>= 10 times)."""
        return self.usage_count >= 10
    
    @property
    def effectiveness_score(self) -> float:
        """Calculate effectiveness score based on usage and success."""
        if self.usage_count == 0:
            return 0.0
        # Weight success rate by usage frequency (logarithmic scale)
        import math
        usage_weight = min(math.log(self.usage_count + 1) / math.log(10), 2.0)
        return (self.success_rate / 100.0) * usage_weight
    
    @property
    def days_since_last_use(self) -> Optional[int]:
        """Calculate days since last use."""
        if not self.last_used_at:
            return None
        delta = datetime.now() - self.last_used_at
        return delta.days
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with enhanced pattern information."""
        result = super().to_dict()
        result.update({
            "is_successful": self.is_successful,
            "is_frequently_used": self.is_frequently_used,
            "effectiveness_score": self.effectiveness_score,
            "days_since_last_use": self.days_since_last_use,
        })
        return result
    
    def __repr__(self) -> str:
        """Enhanced string representation."""
        return (f"<LearningPattern(id={self.id}, name='{self.pattern_name}', "
                f"category='{self.category}', usage={self.usage_count}, "
                f"success_rate={self.success_rate:.1f}%)>")
    
    @classmethod
    def get_by_name(cls, session, pattern_name: str) -> Optional["LearningPattern"]:
        """Get learning pattern by name."""
        return session.query(cls).filter(cls.pattern_name == pattern_name).first()
    
    @classmethod
    def get_by_category(cls, session, category: str) -> list["LearningPattern"]:
        """Get all learning patterns in a category."""
        return session.query(cls).filter(cls.category == category).all()
    
    @classmethod
    def get_most_successful(cls, session, limit: int = 10) -> list["LearningPattern"]:
        """Get most successful patterns."""
        return (session.query(cls)
                .order_by(cls.success_rate.desc(), cls.usage_count.desc())
                .limit(limit)
                .all())
    
    @classmethod
    def get_most_used(cls, session, limit: int = 10) -> list["LearningPattern"]:
        """Get most frequently used patterns."""
        return (session.query(cls)
                .order_by(cls.usage_count.desc())
                .limit(limit)
                .all())
    
    @classmethod
    def get_recent_patterns(cls, session, days: int = 7, limit: int = 10) -> list["LearningPattern"]:
        """Get recently used patterns."""
        cutoff_date = datetime.now() - timedelta(days=days)
        return (session.query(cls)
                .filter(cls.last_used_at >= cutoff_date)
                .order_by(cls.last_used_at.desc())
                .limit(limit)
                .all())