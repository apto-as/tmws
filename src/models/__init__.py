"""
Database models for TMWS v2.0 - Universal Multi-Agent Platform.
"""

# Base classes
from .base import TMWSBase, UUIDMixin, TimestampMixin, MetadataMixin

# V1 Models (Legacy - for backward compatibility)
from .memory import Memory as MemoryV1
from .persona import Persona, PersonaType, PersonaRole
from .task import Task as TaskV1, TaskStatus as TaskStatusV1, TaskPriority as TaskPriorityV1
from .workflow import Workflow, WorkflowStatus, WorkflowType
from .learning_pattern import LearningPattern as LearningPatternV1

# V2 Models (Universal Multi-Agent Platform)
from .agent import Agent, AgentTeam, AgentNamespace
from .memory_v2 import Memory, MemoryType, RetentionPolicy
from .task_v2 import Task, TaskStatus, TaskPriority
from .learning_pattern_v2 import LearningPattern, PatternUsageHistory

# API audit logging
from .api_audit_log import APIAuditLog, RequestMethod, ResponseStatus

__all__ = [
    # Base classes
    "TMWSBase",
    "UUIDMixin", 
    "TimestampMixin",
    "MetadataMixin",
    
    # V1 Models (Legacy)
    "MemoryV1",
    "Persona", "PersonaType", "PersonaRole",
    "TaskV1", "TaskStatusV1", "TaskPriorityV1",
    "Workflow", "WorkflowStatus", "WorkflowType",
    "LearningPatternV1",
    
    # V2 Models (Universal Multi-Agent Platform)
    "Agent", "AgentTeam", "AgentNamespace",
    "Memory", "MemoryType", "RetentionPolicy",
    "Task", "TaskStatus", "TaskPriority",
    "LearningPattern", "PatternUsageHistory",
    
    # API audit logging
    "APIAuditLog", "RequestMethod", "ResponseStatus",
]