"""
Agent models for TMWS v2.0 - Universal Multi-Agent Memory System.
Replaces the persona-specific implementation with a generic agent architecture.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import JSON, Text, DateTime, Boolean, Index, Float, Integer
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import TMWSBase, MetadataMixin


class AccessLevel(str, Enum):
    """Access levels for memory isolation."""
    PRIVATE = "private"      # Only accessible by owner agent
    TEAM = "team"            # Accessible by team members
    SHARED = "shared"        # Accessible by explicitly shared agents
    PUBLIC = "public"        # Accessible by all agents
    SYSTEM = "system"        # System-level shared knowledge


class AgentStatus(str, Enum):
    """Agent operational status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DEPRECATED = "deprecated"


class Agent(TMWSBase, MetadataMixin):
    """Universal agent model for any AI system."""
    
    __tablename__ = "agents"
    
    # Core identification
    agent_id: Mapped[str] = mapped_column(
        Text, 
        nullable=False, 
        unique=True, 
        index=True,
        comment="Unique identifier for the agent (e.g., 'claude-3', 'gpt-4', 'athena-conductor')"
    )
    
    display_name: Mapped[str] = mapped_column(
        Text, 
        nullable=False,
        comment="Human-readable name for the agent"
    )
    
    # Organization and namespace
    organization_id: Mapped[Optional[str]] = mapped_column(
        Text, 
        nullable=True, 
        index=True,
        comment="Organization or project identifier"
    )
    
    namespace: Mapped[str] = mapped_column(
        Text, 
        nullable=False, 
        default="default",
        index=True,
        comment="Namespace for memory isolation"
    )
    
    # Agent metadata
    agent_type: Mapped[Optional[str]] = mapped_column(
        Text, 
        nullable=True,
        comment="Type of agent (e.g., 'language_model', 'task_executor', 'coordinator')"
    )
    
    capabilities: Mapped[Dict[str, Any]] = mapped_column(
        JSON, 
        nullable=False, 
        default=dict,
        comment="Dynamic capabilities and features"
    )
    
    config: Mapped[Dict[str, Any]] = mapped_column(
        JSON, 
        nullable=False, 
        default=dict,
        comment="Agent-specific configuration"
    )
    
    # Access control
    default_access_level: Mapped[AccessLevel] = mapped_column(
        sa.Enum(AccessLevel, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=AccessLevel.PRIVATE,
        comment="Default access level for agent's memories"
    )
    
    # Status and health
    status: Mapped[AgentStatus] = mapped_column(
        sa.Enum(AgentStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=AgentStatus.ACTIVE,
        index=True
    )
    
    health_score: Mapped[float] = mapped_column(
        Float, 
        nullable=False, 
        default=1.0,
        comment="Health score (0.0 - 1.0)"
    )
    
    # Performance metrics
    total_memories: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tasks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_tasks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    average_response_time_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Authentication
    api_key_hash: Mapped[Optional[str]] = mapped_column(
        Text, 
        nullable=True,
        comment="Hashed API key for agent authentication"
    )
    
    # Timestamps
    last_active_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )
    
    # Indexes for performance
    __table_args__ = (
        Index('ix_agent_org_namespace', 'organization_id', 'namespace'),
        Index('ix_agent_status_active', 'status', 'last_active_at'),
        Index('ix_agent_type_status', 'agent_type', 'status'),
    )
    
    def __repr__(self) -> str:
        return f"<Agent(agent_id='{self.agent_id}', namespace='{self.namespace}')>"
    
    @property
    def success_rate(self) -> float:
        """Calculate task success rate."""
        if self.total_tasks == 0:
            return 0.0
        return self.successful_tasks / self.total_tasks
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_active_at = datetime.utcnow()
    
    def update_metrics(
        self, 
        success: bool, 
        response_time_ms: float,
        memory_count_delta: int = 0
    ) -> None:
        """Update performance metrics."""
        self.total_tasks += 1
        if success:
            self.successful_tasks += 1
        
        # Update average response time (exponential moving average)
        if self.average_response_time_ms is None:
            self.average_response_time_ms = response_time_ms
        else:
            self.average_response_time_ms = (
                0.9 * self.average_response_time_ms + 0.1 * response_time_ms
            )
        
        # Update memory count
        self.total_memories += memory_count_delta
        
        # Update health score based on success rate
        self.health_score = min(1.0, self.success_rate + 0.1)
        
        self.update_activity()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert agent to dictionary."""
        return {
            "id": str(self.id),
            "agent_id": self.agent_id,
            "display_name": self.display_name,
            "organization_id": self.organization_id,
            "namespace": self.namespace,
            "agent_type": self.agent_type,
            "capabilities": self.capabilities,
            "config": self.config,
            "default_access_level": self.default_access_level.value,
            "status": self.status.value,
            "health_score": self.health_score,
            "total_memories": self.total_memories,
            "total_tasks": self.total_tasks,
            "success_rate": self.success_rate,
            "average_response_time_ms": self.average_response_time_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_active_at": self.last_active_at.isoformat() if self.last_active_at else None,
        }
    
    @classmethod
    def create_trinitas_agents(cls) -> List[Dict[str, Any]]:
        """Create Trinitas-compatible agents for backward compatibility."""
        return [
            {
                "agent_id": "athena-conductor",
                "display_name": "Athena - Harmonious Conductor",
                "namespace": "trinitas",
                "agent_type": "coordinator",
                "capabilities": {
                    "orchestration": "advanced",
                    "workflow": "expert",
                    "parallel_execution": True,
                    "task_delegation": True
                },
                "config": {
                    "personality": "warm",
                    "approach": "harmonious",
                    "specialties": ["orchestration", "workflow", "automation"]
                }
            },
            {
                "agent_id": "artemis-optimizer",
                "display_name": "Artemis - Technical Perfectionist",
                "namespace": "trinitas",
                "agent_type": "optimizer",
                "capabilities": {
                    "performance": "expert",
                    "optimization": "advanced",
                    "code_quality": True,
                    "best_practices": True
                },
                "config": {
                    "personality": "perfectionist",
                    "approach": "technical_excellence",
                    "specialties": ["optimization", "performance", "quality"]
                }
            },
            {
                "agent_id": "hestia-auditor",
                "display_name": "Hestia - Security Guardian",
                "namespace": "trinitas",
                "agent_type": "auditor",
                "capabilities": {
                    "security": "expert",
                    "audit": "advanced",
                    "vulnerability_scan": True,
                    "threat_modeling": True
                },
                "config": {
                    "personality": "paranoid",
                    "approach": "defensive",
                    "specialties": ["security", "audit", "risk", "vulnerability"]
                }
            },
            {
                "agent_id": "eris-coordinator",
                "display_name": "Eris - Tactical Coordinator", 
                "namespace": "trinitas",
                "agent_type": "coordinator",
                "capabilities": {
                    "coordination": "advanced",
                    "tactical_planning": True,
                    "conflict_resolution": True,
                    "team_alignment": True
                },
                "config": {
                    "personality": "strategic",
                    "approach": "tactical",
                    "specialties": ["coordinate", "tactical", "team", "collaboration"]
                }
            },
            {
                "agent_id": "hera-strategist",
                "display_name": "Hera - Strategic Commander",
                "namespace": "trinitas", 
                "agent_type": "strategist",
                "capabilities": {
                    "strategy": "expert",
                    "planning": "advanced",
                    "architecture": True,
                    "vision": True
                },
                "config": {
                    "personality": "commander",
                    "approach": "strategic",
                    "specialties": ["strategy", "planning", "architecture", "vision"]
                }
            },
            {
                "agent_id": "muses-documenter",
                "display_name": "Muses - Knowledge Architect",
                "namespace": "trinitas",
                "agent_type": "documenter",
                "capabilities": {
                    "documentation": "expert",
                    "knowledge_management": True,
                    "content_creation": True,
                    "archival": True
                },
                "config": {
                    "personality": "meticulous",
                    "approach": "structured",
                    "specialties": ["documentation", "knowledge", "record", "guide"]
                }
            }
        ]


class AgentTeam(TMWSBase, MetadataMixin):
    """Team structure for agent collaboration."""
    
    __tablename__ = "agent_teams"
    
    team_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    team_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Team members (agent_ids)
    members: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    leader_agent_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Team configuration
    config: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    shared_namespace: Mapped[str] = mapped_column(Text, nullable=False)
    
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)


class AgentNamespace(TMWSBase, MetadataMixin):
    """Namespace configuration for memory isolation."""
    
    __tablename__ = "agent_namespaces"
    
    namespace: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Access control
    owner_agent_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    admin_agents: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    member_agents: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    
    # Namespace settings
    default_access_level: Mapped[AccessLevel] = mapped_column(
        sa.Enum(AccessLevel, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=AccessLevel.PRIVATE
    )
    
    config: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)