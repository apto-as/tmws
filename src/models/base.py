"""
Base model classes for TMWS database models.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all database models."""
    
    @declared_attr
    def __tablename__(cls):
        """Generate table name from class name."""
        name = cls.__name__.lower()
        # Convert CamelCase to snake_case
        import re
        return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


class UUIDMixin:
    """Mixin for UUID primary key."""
    
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False,
        comment="Primary key UUID"
    )


class TimestampMixin:
    """Mixin for timestamp fields."""
    
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        comment="Record creation timestamp"
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        comment="Record last update timestamp"
    )


class MetadataMixin:
    """Mixin for JSONB metadata fields."""
    
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(
        "metadata",  # Actual column name in database
        JSONB,
        nullable=False,
        default=dict,
        server_default=sa.text("'{}'::jsonb"),
        comment="JSON metadata"
    )


class TMWSBase(Base, UUIDMixin, TimestampMixin):
    """Base class for all TMWS models with common fields."""
    
    __abstract__ = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            elif isinstance(value, UUID):
                value = str(value)
            result[column.name] = value
        return result
    
    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update model from dictionary."""
        for key, value in data.items():
            if hasattr(self, key) and key not in ('id', 'created_at'):
                setattr(self, key, value)
    
    def __repr__(self) -> str:
        """String representation of the model."""
        return f"<{self.__class__.__name__}(id={self.id})>"