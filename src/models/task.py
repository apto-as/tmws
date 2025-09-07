"""
Task models for TMWS v2.0 - Universal Multi-Agent Platform.
Enhanced task management with agent-centric design and workflow integration.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import JSON, Text, DateTime, Boolean, Float, Integer, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import TMWSBase, MetadataMixin


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class TaskPriority(str, Enum):
    """Task priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class Task(TMWSBase, MetadataMixin):
    """
    Enhanced Task model with agent-centric design.
    
    Key improvements:
    - assigned_agent_id instead of assigned_persona_id
    - namespace-based organization and isolation
    - collaborative task support with multiple agents
    - enhanced workflow integration
    - performance tracking and optimization
    """
    
    __tablename__ = "tasks"
    
    # Task identification and content
    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Task title"
    )
    
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Detailed task description"
    )
    
    task_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="general",
        index=True,
        comment="Task type for categorization"
    )
    
    # Agent assignment (replaces persona assignment)
    assigned_agent_id: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        index=True,
        comment="Primary agent assigned to this task"
    )
    
    # Collaborative assignment support
    collaborating_agents: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        comment="Additional agents collaborating on this task"
    )
    
    # Namespace and access control
    namespace: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
        default="default",
        comment="Namespace for task isolation and organization"
    )
    
    access_level: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="private",
        index=True,
        comment="Access level: 'private', 'shared', 'public', 'system'"
    )
    
    # Task state and priority
    status: Mapped[TaskStatus] = mapped_column(
        sa.Enum(TaskStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=TaskStatus.PENDING,
        index=True,
        comment="Current task status"
    )
    
    priority: Mapped[TaskPriority] = mapped_column(
        sa.Enum(TaskPriority, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=TaskPriority.MEDIUM,
        index=True,
        comment="Task priority level"
    )
    
    # Scheduling and timing
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Scheduled execution time"
    )
    
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Task start time"
    )
    
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Task completion time"
    )
    
    due_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Task due date"
    )
    
    # Task dependencies and relationships
    dependencies: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        comment="List of task IDs that must complete before this task"
    )
    
    parent_task_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        comment="Parent task for hierarchical task structures"
    )
    
    workflow_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Associated workflow ID"
    )
    
    # Task configuration and parameters
    task_config: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        comment="Task-specific configuration parameters"
    )
    
    input_data: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        comment="Input data for task execution"
    )
    
    output_data: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        comment="Output data from task execution"
    )
    
    # Progress and performance tracking
    progress_percentage: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        comment="Task completion percentage (0.0 to 100.0)"
    )
    
    estimated_duration: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Estimated duration in seconds"
    )
    
    actual_duration: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Actual duration in seconds"
    )
    
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Number of retry attempts"
    )
    
    max_retries: Mapped[int] = mapped_column(
        Integer,
        default=3,
        comment="Maximum number of retry attempts"
    )
    
    # Error handling and logging
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if task failed"
    )
    
    error_details: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        comment="Detailed error information"
    )
    
    execution_log: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        comment="Execution log entries"
    )
    
    # Tags and categorization
    tags: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        comment="User-defined tags for categorization"
    )
    
    context_tags: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        comment="Contextual tags for enhanced organization"
    )
    
    # Resource management
    resource_requirements: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        comment="Required resources (CPU, memory, etc.)"
    )
    
    resource_usage: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        comment="Actual resource usage during execution"
    )
    
    # Quality and success metrics
    quality_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Task execution quality score (0.0 to 10.0)"
    )
    
    success_criteria: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        comment="Criteria for determining task success"
    )
    
    # Relationships
    assigned_agent = relationship(
        "Agent",
        back_populates="tasks",
        foreign_keys="[Task.assigned_agent_id]",
        primaryjoin="Task.assigned_agent_id == Agent.agent_id"
    )
    
    # Self-referential relationship for hierarchical tasks
    children = relationship(
        "Task",
        backref="parent",
        remote_side="Task.id",
        foreign_keys="[Task.parent_task_id]"
    )
    
    # Table constraints and indexes
    __table_args__ = (
        # Basic validation
        CheckConstraint(
            "LENGTH(title) >= 1",
            name="title_not_empty"
        ),
        CheckConstraint(
            "LENGTH(description) >= 1",
            name="description_not_empty"
        ),
        
        # Access level validation
        CheckConstraint(
            "access_level IN ('private', 'shared', 'public', 'system')",
            name="access_level_check"
        ),
        
        # Progress validation
        CheckConstraint(
            "progress_percentage >= 0.0 AND progress_percentage <= 100.0",
            name="progress_bounds"
        ),
        
        # Duration validation
        CheckConstraint(
            "estimated_duration IS NULL OR estimated_duration > 0",
            name="estimated_duration_positive"
        ),
        CheckConstraint(
            "actual_duration IS NULL OR actual_duration >= 0",
            name="actual_duration_non_negative"
        ),
        
        # Retry validation
        CheckConstraint(
            "retry_count >= 0",
            name="retry_count_non_negative"
        ),
        CheckConstraint(
            "max_retries >= 0",
            name="max_retries_non_negative"
        ),
        
        # Quality score validation
        CheckConstraint(
            "quality_score IS NULL OR (quality_score >= 0.0 AND quality_score <= 10.0)",
            name="quality_score_bounds"
        ),
        
        # Timing logic validation
        CheckConstraint(
            "completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at",
            name="completion_after_start"
        ),
        
        # Composite indexes for common queries
        Index("idx_tasks_agent_status", "assigned_agent_id", "status"),
        Index("idx_tasks_namespace_status", "namespace", "status"),
        Index("idx_tasks_priority_status", "priority", "status"),
        Index("idx_tasks_type_status", "task_type", "status"),
        Index("idx_tasks_workflow", "workflow_id", "status"),
        Index("idx_tasks_scheduled", "scheduled_at", postgresql_using="btree"),
        Index("idx_tasks_due_date", "due_date", postgresql_using="btree"),
        Index("idx_tasks_progress", "progress_percentage", postgresql_using="btree"),
        Index("idx_tasks_hierarchy", "parent_task_id", "status"),
        
        # Performance indexes
        Index("idx_tasks_performance", "quality_score", "actual_duration"),
        Index("idx_tasks_retry", "retry_count", "max_retries"),
        
        # Full-text search indexes
        Index(
            "idx_tasks_content_search",
            func.to_tsvector('english', sa.text("title || ' ' || description")),
            postgresql_using="gin"
        ),
        Index("idx_tasks_tags", "tags", postgresql_using="gin"),
        Index("idx_tasks_context_tags", "context_tags", postgresql_using="gin")
    )
    
    # Properties and methods
    @property
    def is_overdue(self) -> bool:
        """Check if task is overdue."""
        if not self.due_date:
            return False
        return datetime.utcnow() > self.due_date and self.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]
    
    @property
    def is_running_late(self) -> bool:
        """Check if task is running behind schedule."""
        if not self.estimated_duration or not self.started_at:
            return False
        
        elapsed = (datetime.utcnow() - self.started_at).total_seconds()
        return elapsed > self.estimated_duration and self.status == TaskStatus.RUNNING
    
    @property
    def efficiency_score(self) -> Optional[float]:
        """Calculate efficiency score based on estimated vs actual duration."""
        if not self.estimated_duration or not self.actual_duration or self.actual_duration == 0:
            return None
        
        # Higher score for completing faster than estimated
        ratio = self.estimated_duration / self.actual_duration
        return min(2.0, max(0.1, ratio))  # Clamped between 0.1 and 2.0
    
    @property
    def all_agents(self) -> List[str]:
        """Get all agents involved in this task (assigned + collaborating)."""
        agents = []
        if self.assigned_agent_id:
            agents.append(self.assigned_agent_id)
        agents.extend(self.collaborating_agents or [])
        return list(set(agents))  # Remove duplicates
    
    def start_execution(self, agent_id: str = None) -> None:
        """Mark task as started."""
        if self.status != TaskStatus.PENDING:
            raise ValueError(f"Cannot start task in status: {self.status}")
        
        self.status = TaskStatus.RUNNING
        self.started_at = func.now()
        self.progress_percentage = 0.0
        
        # Update assigned agent if provided
        if agent_id:
            self.assigned_agent_id = agent_id
        
        self.add_log_entry("task_started", {"agent_id": agent_id or self.assigned_agent_id})
    
    def complete_execution(self, output_data: Dict[str, Any] = None, quality_score: float = None) -> None:
        """Mark task as completed."""
        if self.status != TaskStatus.RUNNING:
            raise ValueError(f"Cannot complete task in status: {self.status}")
        
        self.status = TaskStatus.COMPLETED
        self.completed_at = func.now()
        self.progress_percentage = 100.0
        
        if output_data:
            self.output_data.update(output_data)
        
        if quality_score is not None:
            self.quality_score = max(0.0, min(10.0, quality_score))
        
        # Calculate actual duration
        if self.started_at:
            self.actual_duration = int((datetime.utcnow() - self.started_at).total_seconds())
        
        self.add_log_entry("task_completed", {
            "output_data_keys": list(output_data.keys()) if output_data else [],
            "quality_score": quality_score,
            "actual_duration": self.actual_duration
        })
    
    def fail_execution(self, error_message: str, error_details: Dict[str, Any] = None) -> None:
        """Mark task as failed."""
        self.status = TaskStatus.FAILED
        self.error_message = error_message
        self.error_details = error_details or {}
        
        # Calculate actual duration if started
        if self.started_at:
            self.actual_duration = int((datetime.utcnow() - self.started_at).total_seconds())
        
        self.add_log_entry("task_failed", {
            "error_message": error_message,
            "error_details": error_details,
            "retry_count": self.retry_count
        })
    
    def retry_execution(self) -> bool:
        """Attempt to retry failed task."""
        if self.status != TaskStatus.FAILED:
            raise ValueError(f"Cannot retry task in status: {self.status}")
        
        if self.retry_count >= self.max_retries:
            return False
        
        self.retry_count += 1
        self.status = TaskStatus.PENDING
        self.error_message = None
        self.error_details = {}
        self.started_at = None
        self.completed_at = None
        self.progress_percentage = 0.0
        
        self.add_log_entry("task_retrying", {"retry_attempt": self.retry_count})
        return True
    
    def cancel_execution(self, reason: str = None) -> None:
        """Cancel task execution."""
        if self.status in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
            raise ValueError(f"Cannot cancel task in status: {self.status}")
        
        self.status = TaskStatus.CANCELLED
        
        # Calculate actual duration if started
        if self.started_at:
            self.actual_duration = int((datetime.utcnow() - self.started_at).total_seconds())
        
        self.add_log_entry("task_cancelled", {"reason": reason})
    
    def pause_execution(self) -> None:
        """Pause running task."""
        if self.status != TaskStatus.RUNNING:
            raise ValueError(f"Cannot pause task in status: {self.status}")
        
        self.status = TaskStatus.PAUSED
        self.add_log_entry("task_paused", {})
    
    def resume_execution(self) -> None:
        """Resume paused task."""
        if self.status != TaskStatus.PAUSED:
            raise ValueError(f"Cannot resume task in status: {self.status}")
        
        self.status = TaskStatus.RUNNING
        self.add_log_entry("task_resumed", {})
    
    def update_progress(self, percentage: float, message: str = None) -> None:
        """Update task progress."""
        self.progress_percentage = max(0.0, min(100.0, percentage))
        
        if message:
            self.add_log_entry("progress_updated", {
                "percentage": percentage,
                "message": message
            })
    
    def add_collaborator(self, agent_id: str) -> bool:
        """Add a collaborating agent to the task."""
        if agent_id not in self.collaborating_agents:
            self.collaborating_agents.append(agent_id)
            self.add_log_entry("collaborator_added", {"agent_id": agent_id})
            return True
        return False
    
    def remove_collaborator(self, agent_id: str) -> bool:
        """Remove a collaborating agent from the task."""
        if agent_id in self.collaborating_agents:
            self.collaborating_agents.remove(agent_id)
            self.add_log_entry("collaborator_removed", {"agent_id": agent_id})
            return True
        return False
    
    def add_log_entry(self, event_type: str, details: Dict[str, Any] = None) -> None:
        """Add an entry to the execution log."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "details": details or {}
        }
        self.execution_log.append(log_entry)
    
    def add_tag(self, tag: str) -> None:
        """Add a tag if not already present."""
        if tag and tag not in self.tags:
            self.tags.append(tag)
    
    def remove_tag(self, tag: str) -> None:
        """Remove a tag if present."""
        if tag in self.tags:
            self.tags.remove(tag)
    
    def add_context_tag(self, tag: str) -> None:
        """Add a context tag if not already present."""
        if tag and tag not in self.context_tags:
            self.context_tags.append(tag)
    
    def can_access(self, agent_id: str, agent_namespace: str, agent_access_level: str = "standard") -> bool:
        """Check if an agent can access this task."""
        # System level access
        if agent_access_level == "admin":
            return True
        
        # System tasks require admin access
        if self.access_level == "system":
            return agent_access_level == "admin"
        
        # Public tasks are accessible to all
        if self.access_level == "public":
            return True
        
        # Task assigned to agent or agent is collaborating
        if agent_id in self.all_agents:
            return True
        
        # Private tasks only accessible within same namespace
        if self.access_level == "private":
            return self.namespace == agent_namespace
        
        # Shared tasks accessible within same namespace
        if self.access_level == "shared":
            return self.namespace == agent_namespace
        
        return False
    
    def __repr__(self) -> str:
        return f"<Task(id={self.id}, title='{self.title}', status='{self.status}', assigned_to='{self.assigned_agent_id}')>"


class TaskTemplate(TMWSBase):
    """
    Task templates for creating standardized tasks.
    Allows agents to create tasks following predefined patterns.
    """
    
    __tablename__ = "task_templates"
    
    # Template identification
    template_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
        index=True,
        comment="Unique template identifier"
    )
    
    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Human-readable template name"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Template description and usage guidelines"
    )
    
    # Template structure
    title_template: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Template title with placeholders"
    )
    
    description_template: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Template description with placeholders"
    )
    
    required_fields: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        comment="Required fields for template instantiation"
    )
    
    optional_fields: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        comment="Optional fields for template instantiation"
    )
    
    # Template defaults
    default_task_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="templated",
        comment="Default task type for instances"
    )
    
    default_priority: Mapped[TaskPriority] = mapped_column(
        sa.Enum(TaskPriority, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=TaskPriority.MEDIUM,
        comment="Default priority for instances"
    )
    
    default_access_level: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="private",
        comment="Default access level for instances"
    )
    
    default_config: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        comment="Default task configuration"
    )
    
    estimated_duration: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Estimated duration in seconds for template instances"
    )
    
    # Template metadata
    namespace: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
        default="default",
        comment="Template namespace"
    )
    
    created_by: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Agent ID of template creator"
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
        comment="Whether template is active and available"
    )
    
    usage_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Number of times template has been used"
    )
    
    success_rate: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        comment="Success rate of tasks created from this template"
    )
    
    __table_args__ = (
        CheckConstraint(
            "default_access_level IN ('private', 'shared', 'public', 'system')",
            name="default_access_level_check"
        ),
        CheckConstraint(
            "estimated_duration IS NULL OR estimated_duration > 0",
            name="estimated_duration_positive"
        ),
        CheckConstraint(
            "success_rate >= 0.0 AND success_rate <= 1.0",
            name="success_rate_bounds"
        ),
        Index("idx_task_templates_namespace", "namespace", "is_active"),
        Index("idx_task_templates_usage", "usage_count", postgresql_using="btree"),
        Index("idx_task_templates_success", "success_rate", postgresql_using="btree")
    )
    
    def instantiate(self, agent_id: str, field_values: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Create a task instance from this template."""
        # Validate required fields
        missing_fields = [field for field in self.required_fields if field not in field_values]
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")
        
        # Replace placeholders in templates
        title = self.title_template
        description = self.description_template
        
        for field, value in field_values.items():
            placeholder = f"{{{field}}}"
            title = title.replace(placeholder, str(value))
            description = description.replace(placeholder, str(value))
        
        # Increment usage count
        self.usage_count += 1
        
        # Merge default config with provided config
        task_config = self.default_config.copy()
        task_config.update(kwargs.get('task_config', {}))
        
        # Return task creation parameters
        return {
            "title": title,
            "description": description,
            "task_type": kwargs.get('task_type', self.default_task_type),
            "assigned_agent_id": agent_id,
            "priority": kwargs.get('priority', self.default_priority),
            "access_level": kwargs.get('access_level', self.default_access_level),
            "task_config": task_config,
            "estimated_duration": kwargs.get('estimated_duration', self.estimated_duration),
            "context_tags": ["templated", self.template_id],
            "metadata": {
                "template_id": self.template_id,
                "template_version": "1.0",
                "field_values": field_values
            }
        }
    
    def update_success_rate(self, completed_tasks: int, successful_tasks: int) -> None:
        """Update template success rate based on task outcomes."""
        if completed_tasks > 0:
            self.success_rate = successful_tasks / completed_tasks
    
    def __repr__(self) -> str:
        return f"<TaskTemplate(template_id='{self.template_id}', name='{self.name}', usage={self.usage_count})>"