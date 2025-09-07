"""
Persona models for TMWS.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import JSON, Text, DateTime, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import TMWSBase, MetadataMixin


class PersonaType(str, Enum):
    """Types of Trinitas personas."""
    ATHENA = "athena"
    ARTEMIS = "artemis"
    HESTIA = "hestia"
    BELLONA = "bellona"
    SESHAT = "seshat"


class PersonaRole(str, Enum):
    """Roles of Trinitas personas."""
    STRATEGIST = "strategist"
    OPTIMIZER = "optimizer"  
    AUDITOR = "auditor"
    COORDINATOR = "coordinator"
    DOCUMENTER = "documenter"


class Persona(TMWSBase, MetadataMixin):
    """Persona configuration and state."""
    
    __tablename__ = "personas"
    
    # Persona identification
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    type: Mapped[PersonaType] = mapped_column(
        sa.Enum(PersonaType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True
    )
    role: Mapped[PersonaRole] = mapped_column(
        sa.Enum(PersonaRole, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True
    )
    
    # Persona configuration
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    specialties: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    
    # Persona behavior configuration
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    preferences: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    
    # Status and capabilities
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    capabilities: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    
    # Performance metrics
    total_tasks: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    successful_tasks: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    average_response_time: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)
    
    # Additional timestamps (created_at and updated_at come from TMWSBase)
    last_active_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )
    
    # Indexes for performance
    __table_args__ = (
        Index('ix_persona_type_active', 'type', 'is_active'),
        Index('ix_persona_role_active', 'role', 'is_active'),
        Index('ix_persona_active_last_active', 'is_active', 'last_active_at'),
    )
    
    def __repr__(self) -> str:
        return f"<Persona(name='{self.name}', type='{self.type}', role='{self.role}')>"
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_tasks == 0:
            return 0.0
        return self.successful_tasks / self.total_tasks
    
    def update_task_metrics(self, success: bool, response_time: float) -> None:
        """Update task performance metrics."""
        self.total_tasks += 1
        if success:
            self.successful_tasks += 1
        
        # Update average response time
        if self.average_response_time is None:
            self.average_response_time = response_time
        else:
            # Exponential moving average
            self.average_response_time = (
                0.9 * self.average_response_time + 0.1 * response_time
            )
        
        self.last_active_at = datetime.utcnow()
    
    def to_dict(self) -> dict[str, Any]:
        """Convert persona to dictionary."""
        return {
            "id": str(self.id),
            "name": self.name,
            "type": self.type.value,
            "role": self.role.value,
            "display_name": self.display_name,
            "description": self.description,
            "specialties": self.specialties,
            "config": self.config,
            "preferences": self.preferences,
            "is_active": self.is_active,
            "capabilities": self.capabilities,
            "total_tasks": self.total_tasks,
            "successful_tasks": self.successful_tasks,
            "success_rate": self.success_rate,
            "average_response_time": self.average_response_time,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_active_at": self.last_active_at.isoformat() if self.last_active_at else None,
        }
    
    @classmethod
    def get_default_personas(cls) -> list[dict]:
        """Get default Trinitas persona configurations."""
        return [
            {
                "name": "athena",
                "type": PersonaType.ATHENA,
                "role": PersonaRole.STRATEGIST,
                "display_name": "Athena - Strategic Architect",
                "description": "Strategic planning and architecture design specialist",
                "specialties": [
                    "strategic_planning",
                    "architecture_design", 
                    "team_coordination",
                    "stakeholder_management",
                    "long_term_vision"
                ],
                "capabilities": [
                    "system_architecture",
                    "project_planning",
                    "risk_assessment",
                    "resource_optimization",
                    "stakeholder_communication"
                ],
            },
            {
                "name": "artemis",
                "type": PersonaType.ARTEMIS,
                "role": PersonaRole.OPTIMIZER,
                "display_name": "Artemis - Technical Perfectionist",
                "description": "Performance optimization and code quality specialist",
                "specialties": [
                    "performance_optimization",
                    "code_quality",
                    "technical_excellence",
                    "algorithm_design",
                    "efficiency_improvement"
                ],
                "capabilities": [
                    "code_optimization",
                    "performance_tuning",
                    "quality_assurance",
                    "refactoring",
                    "best_practices"
                ],
            },
            {
                "name": "hestia",
                "type": PersonaType.HESTIA,
                "role": PersonaRole.AUDITOR,
                "display_name": "Hestia - Security Guardian",
                "description": "Security analysis and vulnerability assessment specialist",
                "specialties": [
                    "security_analysis",
                    "vulnerability_assessment",
                    "risk_management",
                    "threat_modeling",
                    "quality_assurance"
                ],
                "capabilities": [
                    "security_audit",
                    "vulnerability_scanning",
                    "risk_analysis",
                    "compliance_checking",
                    "threat_assessment"
                ],
            },
            {
                "name": "bellona",
                "type": PersonaType.BELLONA,
                "role": PersonaRole.COORDINATOR,
                "display_name": "Bellona - Tactical Coordinator",
                "description": "Parallel task management and resource optimization specialist",
                "specialties": [
                    "task_coordination",
                    "resource_optimization",
                    "parallel_execution",
                    "workflow_orchestration",
                    "real_time_coordination"
                ],
                "capabilities": [
                    "task_management",
                    "resource_allocation",
                    "parallel_processing",
                    "workflow_automation",
                    "coordination"
                ],
            },
            {
                "name": "seshat",
                "type": PersonaType.SESHAT,
                "role": PersonaRole.DOCUMENTER,
                "display_name": "Seshat - Knowledge Architect",
                "description": "Documentation creation and knowledge management specialist",
                "specialties": [
                    "documentation_creation",
                    "knowledge_management",
                    "information_architecture",
                    "content_organization",
                    "system_documentation"
                ],
                "capabilities": [
                    "documentation_generation",
                    "knowledge_archival",
                    "content_creation",
                    "information_structuring",
                    "API_documentation"
                ],
            },
        ]