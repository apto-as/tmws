"""
Task models for TMWS.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import JSON, Text, DateTime, Integer, Float, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import TMWSBase, MetadataMixin


class TaskStatus(str, Enum):
    """Task status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class TaskPriority(str, Enum):
    """Task priority enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Task(TMWSBase, MetadataMixin):
    """Task model for workflow management."""
    
    __tablename__ = "tasks"
    
    # Task identification
    title: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    task_type: Mapped[str] = mapped_column(Text, nullable=False, default="general")
    
    # Task status and priority
    status: Mapped[TaskStatus] = mapped_column(
        sa.Enum(TaskStatus),
        nullable=False,
        default=TaskStatus.PENDING,
        index=True
    )
    priority: Mapped[TaskPriority] = mapped_column(
        sa.Enum(TaskPriority),
        nullable=False,
        default=TaskPriority.MEDIUM,
        index=True
    )
    
    # Progress tracking
    progress: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default=sa.text("0.0")
    )
    
    # Assignment
    assigned_persona_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("personas.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Relationships
    assigned_persona = relationship("Persona", backref="tasks", lazy="select")
    
    # Task dependencies
    dependencies: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        server_default=sa.text("'[]'::jsonb")
    )
    
    # Results and errors
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Execution tracking
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )
    
    # Retry tracking
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=sa.text("0")
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        server_default=sa.text("3")
    )
    
    # Tags for categorization
    tags: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        server_default=sa.text("'[]'::jsonb")
    )
    
    # Indexes for performance
    __table_args__ = (
        Index('ix_task_status_priority', 'status', 'priority'),
        Index('ix_task_assigned_status', 'assigned_persona_id', 'status'),
        Index('ix_task_created_status', 'created_at', 'status'),
    )
    
    def __repr__(self) -> str:
        return f"<Task(title='{self.title}', status='{self.status}', priority='{self.priority}')>"
    
    @property
    def is_completed(self) -> bool:
        """Check if task is completed."""
        return self.status == TaskStatus.COMPLETED
    
    @property
    def is_failed(self) -> bool:
        """Check if task has failed."""
        return self.status == TaskStatus.FAILED
    
    @property
    def is_active(self) -> bool:
        """Check if task is currently active."""
        return self.status == TaskStatus.IN_PROGRESS
    
    @property
    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return self.retry_count < self.max_retries and self.status == TaskStatus.FAILED
    
    @property
    def duration(self) -> Optional[float]:
        """Calculate task duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    def start(self) -> None:
        """Mark task as started."""
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = datetime.utcnow()
    
    def complete(self, result: Optional[dict] = None) -> None:
        """Mark task as completed."""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.progress = 1.0
        if result:
            self.result = result
    
    def fail(self, error_message: str) -> None:
        """Mark task as failed."""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_message = error_message
        self.retry_count += 1
    
    def cancel(self) -> None:
        """Cancel the task."""
        self.status = TaskStatus.CANCELLED
        self.completed_at = datetime.utcnow()
    
    def skip(self) -> None:
        """Skip the task."""
        self.status = TaskStatus.SKIPPED
        self.completed_at = datetime.utcnow()
    
    def update_progress(self, progress: float) -> None:
        """Update task progress."""
        self.progress = max(0.0, min(1.0, progress))
    
    def to_dict(self) -> dict[str, Any]:
        """Convert task to dictionary."""
        return {
            "id": str(self.id),
            "title": self.title,
            "description": self.description,
            "task_type": self.task_type,
            "status": self.status.value,
            "priority": self.priority.value,
            "progress": self.progress,
            "assigned_persona_id": str(self.assigned_persona_id) if self.assigned_persona_id else None,
            "dependencies": self.dependencies,
            "result": self.result,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration": self.duration,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "tags": self.tags,
            "metadata": self.metadata_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }