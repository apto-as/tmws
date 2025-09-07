"""
Workflow models for TMWS.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import JSON, Text, DateTime, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import TMWSBase, MetadataMixin


class WorkflowStatus(str, Enum):
    """Workflow status enumeration."""
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowType(str, Enum):
    """Workflow type enumeration."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    HYBRID = "hybrid"


class Workflow(TMWSBase, MetadataMixin):
    """Workflow model for complex task orchestration."""
    
    __tablename__ = "workflows"
    
    # Workflow identification
    name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Workflow configuration
    workflow_type: Mapped[WorkflowType] = mapped_column(
        sa.Enum(WorkflowType),
        nullable=False,
        default=WorkflowType.SEQUENTIAL,
        index=True
    )
    
    # Workflow status
    status: Mapped[WorkflowStatus] = mapped_column(
        sa.Enum(WorkflowStatus),
        nullable=False,
        default=WorkflowStatus.DRAFT,
        index=True
    )
    
    # Workflow definition
    steps: Mapped[list[dict]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        server_default=sa.text("'[]'::jsonb")
    )
    
    # Execution tracking
    current_step_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=sa.text("0")
    )
    
    execution_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=sa.text("0")
    )
    
    # Execution timestamps
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
    last_executed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )
    
    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failed_step_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Creator information
    created_by: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        index=True
    )
    
    # Tags for categorization
    tags: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        server_default=sa.text("'[]'::jsonb")
    )
    
    # Execution configuration
    config: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default=sa.text("'{}'::jsonb")
    )
    
    # Indexes for performance
    __table_args__ = (
        Index('ix_workflow_status_type', 'status', 'workflow_type'),
        Index('ix_workflow_created_by_status', 'created_by', 'status'),
        Index('ix_workflow_last_executed', 'last_executed_at'),
    )
    
    def __repr__(self) -> str:
        return f"<Workflow(name='{self.name}', type='{self.workflow_type}', status='{self.status}')>"
    
    @property
    def is_active(self) -> bool:
        """Check if workflow is active."""
        return self.status == WorkflowStatus.ACTIVE
    
    @property
    def is_running(self) -> bool:
        """Check if workflow is currently running."""
        return self.status == WorkflowStatus.RUNNING
    
    @property
    def is_completed(self) -> bool:
        """Check if workflow is completed."""
        return self.status == WorkflowStatus.COMPLETED
    
    @property
    def is_failed(self) -> bool:
        """Check if workflow has failed."""
        return self.status == WorkflowStatus.FAILED
    
    @property
    def can_execute(self) -> bool:
        """Check if workflow can be executed."""
        return self.status in [WorkflowStatus.ACTIVE, WorkflowStatus.PAUSED]
    
    @property
    def total_steps(self) -> int:
        """Get total number of steps."""
        return len(self.steps)
    
    @property
    def progress(self) -> float:
        """Calculate workflow progress."""
        if self.total_steps == 0:
            return 0.0
        return self.current_step_index / self.total_steps
    
    @property
    def duration(self) -> Optional[float]:
        """Calculate workflow duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    def start(self) -> None:
        """Start workflow execution."""
        self.status = WorkflowStatus.RUNNING
        self.started_at = datetime.utcnow()
        self.last_executed_at = datetime.utcnow()
        self.execution_count += 1
        self.current_step_index = 0
        self.error_message = None
        self.failed_step_index = None
    
    def pause(self) -> None:
        """Pause workflow execution."""
        self.status = WorkflowStatus.PAUSED
    
    def resume(self) -> None:
        """Resume workflow execution."""
        self.status = WorkflowStatus.RUNNING
    
    def complete(self) -> None:
        """Mark workflow as completed."""
        self.status = WorkflowStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.current_step_index = self.total_steps
    
    def fail(self, error_message: str, step_index: Optional[int] = None) -> None:
        """Mark workflow as failed."""
        self.status = WorkflowStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_message = error_message
        self.failed_step_index = step_index or self.current_step_index
    
    def cancel(self) -> None:
        """Cancel workflow execution."""
        self.status = WorkflowStatus.CANCELLED
        self.completed_at = datetime.utcnow()
    
    def activate(self) -> None:
        """Activate workflow for execution."""
        self.status = WorkflowStatus.ACTIVE
    
    def deactivate(self) -> None:
        """Deactivate workflow."""
        self.status = WorkflowStatus.INACTIVE
    
    def advance_step(self) -> None:
        """Advance to next step."""
        self.current_step_index = min(self.current_step_index + 1, self.total_steps)
    
    def reset(self) -> None:
        """Reset workflow execution state."""
        self.current_step_index = 0
        self.started_at = None
        self.completed_at = None
        self.error_message = None
        self.failed_step_index = None
        if self.status in [WorkflowStatus.RUNNING, WorkflowStatus.PAUSED, 
                           WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]:
            self.status = WorkflowStatus.ACTIVE
    
    def add_step(self, step: dict) -> None:
        """Add a step to the workflow."""
        if not self.steps:
            self.steps = []
        self.steps.append(step)
    
    def remove_step(self, index: int) -> None:
        """Remove a step from the workflow."""
        if 0 <= index < len(self.steps):
            self.steps.pop(index)
    
    def update_step(self, index: int, step: dict) -> None:
        """Update a specific step."""
        if 0 <= index < len(self.steps):
            self.steps[index] = step
    
    def to_dict(self) -> dict[str, Any]:
        """Convert workflow to dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "workflow_type": self.workflow_type.value,
            "status": self.status.value,
            "steps": self.steps,
            "current_step_index": self.current_step_index,
            "total_steps": self.total_steps,
            "progress": self.progress,
            "execution_count": self.execution_count,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "last_executed_at": self.last_executed_at.isoformat() if self.last_executed_at else None,
            "duration": self.duration,
            "error_message": self.error_message,
            "failed_step_index": self.failed_step_index,
            "created_by": self.created_by,
            "tags": self.tags,
            "config": self.config,
            "metadata": self.metadata_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }