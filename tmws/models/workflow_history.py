"""
Workflow History Models for TMWS
Tracks workflow execution history and logs for auditing and debugging
"""

from sqlalchemy import Column, String, DateTime, JSON, Float, Integer, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from . import Base


class WorkflowExecution(Base):
    """Model for workflow execution history."""
    __tablename__ = "workflow_executions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    
    # Execution metadata
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime)
    status = Column(String(50), nullable=False, default="running")  # running, completed, failed, cancelled
    
    # Execution context
    triggered_by = Column(String(100))  # user_id, system, api, scheduler
    trigger_type = Column(String(50))  # manual, scheduled, event, api
    
    # Input/Output
    input_data = Column(JSON)
    output_data = Column(JSON)
    
    # Performance metrics
    execution_time_seconds = Column(Float)
    cpu_time_seconds = Column(Float)
    memory_peak_mb = Column(Float)
    
    # Error handling
    error_message = Column(Text)
    error_details = Column(JSON)
    retry_count = Column(Integer, default=0)
    
    # Additional metadata
    metadata_json = Column(JSON, default=dict)
    
    # Relationships
    workflow = relationship("Workflow", back_populates="executions")
    step_executions = relationship("WorkflowStepExecution", back_populates="workflow_execution", cascade="all, delete-orphan")
    logs = relationship("WorkflowExecutionLog", back_populates="workflow_execution", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index("idx_workflow_executions_workflow_id", "workflow_id"),
        Index("idx_workflow_executions_status", "status"),
        Index("idx_workflow_executions_started_at", "started_at"),
        Index("idx_workflow_executions_triggered_by", "triggered_by"),
    )


class WorkflowStepExecution(Base):
    """Model for individual step execution within a workflow."""
    __tablename__ = "workflow_step_executions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_execution_id = Column(UUID(as_uuid=True), ForeignKey("workflow_executions.id"), nullable=False)
    
    # Step identification
    step_name = Column(String(200), nullable=False)
    step_index = Column(Integer, nullable=False)
    step_type = Column(String(50))  # action, condition, parallel, loop
    
    # Execution timing
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime)
    status = Column(String(50), nullable=False, default="running")  # running, completed, failed, skipped
    
    # Input/Output
    input_data = Column(JSON)
    output_data = Column(JSON)
    
    # Performance
    execution_time_seconds = Column(Float)
    
    # Error handling
    error_message = Column(Text)
    error_details = Column(JSON)
    retry_count = Column(Integer, default=0)
    
    # Additional metadata
    metadata_json = Column(JSON, default=dict)
    
    # Relationships
    workflow_execution = relationship("WorkflowExecution", back_populates="step_executions")
    
    # Indexes
    __table_args__ = (
        Index("idx_step_executions_workflow_execution_id", "workflow_execution_id"),
        Index("idx_step_executions_status", "status"),
        Index("idx_step_executions_step_name", "step_name"),
    )


class WorkflowExecutionLog(Base):
    """Model for detailed workflow execution logs."""
    __tablename__ = "workflow_execution_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_execution_id = Column(UUID(as_uuid=True), ForeignKey("workflow_executions.id"), nullable=False)
    step_execution_id = Column(UUID(as_uuid=True), ForeignKey("workflow_step_executions.id"))
    
    # Log details
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    level = Column(String(20), nullable=False)  # debug, info, warning, error, critical
    message = Column(Text, nullable=False)
    
    # Context
    component = Column(String(100))  # workflow_engine, step_executor, validator, etc.
    function = Column(String(100))
    line_number = Column(Integer)
    
    # Additional data
    context_data = Column(JSON)
    
    # Relationships
    workflow_execution = relationship("WorkflowExecution", back_populates="logs")
    
    # Indexes
    __table_args__ = (
        Index("idx_execution_logs_workflow_execution_id", "workflow_execution_id"),
        Index("idx_execution_logs_timestamp", "timestamp"),
        Index("idx_execution_logs_level", "level"),
    )


class WorkflowSchedule(Base):
    """Model for scheduled workflow executions."""
    __tablename__ = "workflow_schedules"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    
    # Schedule configuration
    schedule_type = Column(String(50), nullable=False)  # cron, interval, once
    schedule_expression = Column(String(200))  # cron expression or interval specification
    
    # Schedule window
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    
    # Status
    is_active = Column(Integer, default=1)  # Boolean as integer for compatibility
    last_run_at = Column(DateTime)
    next_run_at = Column(DateTime)
    
    # Execution configuration
    input_data = Column(JSON)
    metadata_json = Column(JSON, default=dict)
    
    # Statistics
    total_runs = Column(Integer, default=0)
    successful_runs = Column(Integer, default=0)
    failed_runs = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    workflow = relationship("Workflow", back_populates="schedules")
    
    # Indexes
    __table_args__ = (
        Index("idx_workflow_schedules_workflow_id", "workflow_id"),
        Index("idx_workflow_schedules_is_active", "is_active"),
        Index("idx_workflow_schedules_next_run_at", "next_run_at"),
    )