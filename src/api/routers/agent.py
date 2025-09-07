"""
Agent API router for TMWS v2.0 - Universal Multi-Agent Platform.
Replaces the persona-specific API with universal agent management.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.exceptions import NotFoundError, ValidationError
from ...services.agent_service import AgentService
from ..dependencies import get_db_session_dependency, get_current_user
from ..security import require_permissions

router = APIRouter(prefix="/agents", tags=["agents"])


# Request/Response Models

class AgentCreateRequest(BaseModel):
    """Agent creation request."""
    agent_id: str = Field(..., description="Unique agent identifier")
    display_name: str = Field(..., description="Human-readable agent name")
    agent_type: str = Field(..., description="Agent type classification")
    agent_subtype: Optional[str] = Field(None, description="Agent subtype for fine-grained classification")
    capabilities: Dict[str, Any] = Field(default_factory=dict, description="Agent capabilities")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Agent configuration")
    namespace: str = Field(default="default", description="Agent namespace")
    access_level: str = Field(default="standard", description="Access level")
    parent_agent_id: Optional[str] = Field(None, description="Parent agent ID for hierarchical relationships")
    team_memberships: List[str] = Field(default_factory=list, description="Team memberships")
    learning_enabled: bool = Field(default=True, description="Enable learning capabilities")
    adaptation_rate: float = Field(default=0.1, description="Learning adaptation rate")
    
    @validator('agent_id')
    def validate_agent_id(cls, v):
        if not v or len(v) < 3 or len(v) > 100:
            raise ValueError('agent_id must be 3-100 characters long')
        if not v.replace('-', '').replace('_', '').replace('.', '').isalnum():
            raise ValueError('agent_id must contain only alphanumeric characters, hyphens, underscores, and dots')
        return v
    
    @validator('access_level')
    def validate_access_level(cls, v):
        valid_levels = ['admin', 'standard', 'restricted', 'readonly']
        if v not in valid_levels:
            raise ValueError(f'access_level must be one of: {valid_levels}')
        return v
    
    @validator('adaptation_rate')
    def validate_adaptation_rate(cls, v):
        if v < 0.0 or v > 1.0:
            raise ValueError('adaptation_rate must be between 0.0 and 1.0')
        return v


class AgentUpdateRequest(BaseModel):
    """Agent update request."""
    display_name: Optional[str] = Field(None, description="Updated display name")
    agent_type: Optional[str] = Field(None, description="Updated agent type")
    agent_subtype: Optional[str] = Field(None, description="Updated agent subtype")
    capabilities: Optional[Dict[str, Any]] = Field(None, description="Updated capabilities")
    configuration: Optional[Dict[str, Any]] = Field(None, description="Updated configuration")
    access_level: Optional[str] = Field(None, description="Updated access level")
    team_memberships: Optional[List[str]] = Field(None, description="Updated team memberships")
    learning_enabled: Optional[bool] = Field(None, description="Updated learning setting")
    adaptation_rate: Optional[float] = Field(None, description="Updated adaptation rate")
    is_active: Optional[bool] = Field(None, description="Updated active status")
    
    @validator('access_level')
    def validate_access_level(cls, v):
        if v is not None:
            valid_levels = ['admin', 'standard', 'restricted', 'readonly']
            if v not in valid_levels:
                raise ValueError(f'access_level must be one of: {valid_levels}')
        return v
    
    @validator('adaptation_rate')
    def validate_adaptation_rate(cls, v):
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError('adaptation_rate must be between 0.0 and 1.0')
        return v


class AgentResponse(BaseModel):
    """Agent response model."""
    id: str
    agent_id: str
    display_name: str
    agent_type: str
    agent_subtype: Optional[str]
    capabilities: Dict[str, Any]
    configuration: Dict[str, Any]
    namespace: str
    access_level: str
    is_active: bool
    last_activity: Optional[datetime]
    total_memories: int
    total_tasks: int
    performance_score: float
    parent_agent_id: Optional[str]
    team_memberships: List[str]
    learning_enabled: bool
    adaptation_rate: float
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AgentStatsResponse(BaseModel):
    """Agent statistics response."""
    agent_id: str
    display_name: str
    agent_type: str
    namespace: str
    is_active: bool
    performance_score: float
    capability_score: float
    total_memories: int
    total_tasks: int
    completed_tasks: int
    success_rate: float
    average_quality_score: float
    last_activity: Optional[str]
    created_at: str
    updated_at: str


class NamespaceCreateRequest(BaseModel):
    """Namespace creation request."""
    namespace: str = Field(..., description="Namespace identifier")
    display_name: str = Field(..., description="Human-readable namespace name")
    description: Optional[str] = Field(None, description="Namespace description")
    parent_namespace: Optional[str] = Field(None, description="Parent namespace")
    access_policy: str = Field(default="private", description="Access policy")
    max_agents: Optional[int] = Field(None, description="Maximum number of agents")
    
    @validator('access_policy')
    def validate_access_policy(cls, v):
        valid_policies = ['public', 'private', 'invite_only', 'restricted']
        if v not in valid_policies:
            raise ValueError(f'access_policy must be one of: {valid_policies}')
        return v


class TeamCreateRequest(BaseModel):
    """Team creation request."""
    team_id: str = Field(..., description="Team identifier")
    display_name: str = Field(..., description="Human-readable team name")
    description: Optional[str] = Field(None, description="Team description")
    namespace: str = Field(default="default", description="Team namespace")
    team_type: str = Field(default="collaborative", description="Team type")
    team_lead: Optional[str] = Field(None, description="Team lead agent ID")
    max_members: Optional[int] = Field(None, description="Maximum team members")
    
    @validator('team_type')
    def validate_team_type(cls, v):
        valid_types = ['collaborative', 'hierarchical', 'specialized']
        if v not in valid_types:
            raise ValueError(f'team_type must be one of: {valid_types}')
        return v


# Agent Management Endpoints

@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent_data: AgentCreateRequest,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> AgentResponse:
    """
    Create a new agent.
    
    Requires admin privileges or appropriate namespace permissions.
    """
    # Check permissions
    if current_user.get("access_level") != "admin" and agent_data.access_level == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient privileges to create admin agent"
        )
    
    agent_service = AgentService(db)
    
    try:
        agent = await agent_service.create_agent(
            agent_id=agent_data.agent_id,
            display_name=agent_data.display_name,
            agent_type=agent_data.agent_type,
            agent_subtype=agent_data.agent_subtype,
            capabilities=agent_data.capabilities,
            configuration=agent_data.configuration,
            namespace=agent_data.namespace,
            access_level=agent_data.access_level,
            parent_agent_id=agent_data.parent_agent_id,
            team_memberships=agent_data.team_memberships,
            learning_enabled=agent_data.learning_enabled,
            adaptation_rate=agent_data.adaptation_rate
        )
        
        return AgentResponse.from_orm(agent)
        
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> AgentResponse:
    """Get agent details by ID."""
    agent_service = AgentService(db)
    
    agent = await agent_service.get_agent_by_id(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found"
        )
    
    # Check access permissions
    if (current_user.get("access_level") != "admin" and 
        agent.namespace != current_user.get("namespace", "default") and
        agent.access_level == "restricted"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient privileges to access this agent"
        )
    
    return AgentResponse.from_orm(agent)


@router.get("/", response_model=List[AgentResponse])
async def list_agents(
    namespace: Optional[str] = Query(None, description="Filter by namespace"),
    agent_type: Optional[str] = Query(None, description="Filter by agent type"),
    access_level: Optional[str] = Query(None, description="Filter by access level"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[AgentResponse]:
    """List agents with optional filtering."""
    agent_service = AgentService(db)
    
    # Apply namespace filtering based on user permissions
    if current_user.get("access_level") != "admin":
        # Non-admin users can only see agents in their namespace or public ones
        if not namespace:
            namespace = current_user.get("namespace", "default")
    
    agents = await agent_service.list_agents(
        namespace=namespace,
        agent_type=agent_type,
        access_level=access_level,
        is_active=is_active,
        limit=limit,
        offset=offset
    )
    
    return [AgentResponse.from_orm(agent) for agent in agents]


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    update_data: AgentUpdateRequest,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> AgentResponse:
    """Update an existing agent."""
    agent_service = AgentService(db)
    
    # Check if agent exists
    existing_agent = await agent_service.get_agent_by_id(agent_id)
    if not existing_agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found"
        )
    
    # Check permissions
    if (current_user.get("access_level") != "admin" and 
        existing_agent.namespace != current_user.get("namespace", "default")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient privileges to update this agent"
        )
    
    # Prevent non-admin from elevating access level
    if (current_user.get("access_level") != "admin" and 
        update_data.access_level == "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient privileges to set admin access level"
        )
    
    try:
        # Convert to dict and filter None values
        updates = {k: v for k, v in update_data.dict().items() if v is not None}
        
        agent = await agent_service.update_agent(agent_id, updates)
        return AgentResponse.from_orm(agent)
        
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    force: bool = Query(False, description="Force hard delete"),
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Delete an agent (soft delete by default, hard delete if force=True)."""
    if current_user.get("access_level") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient privileges to delete agents"
        )
    
    agent_service = AgentService(db)
    
    success = await agent_service.delete_agent(agent_id, force=force)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found"
        )


@router.post("/{agent_id}/activate", response_model=AgentResponse)
async def activate_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> AgentResponse:
    """Activate a deactivated agent."""
    agent_service = AgentService(db)
    
    try:
        agent = await agent_service.activate_agent(agent_id)
        return AgentResponse.from_orm(agent)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")


@router.post("/{agent_id}/deactivate", response_model=AgentResponse)
async def deactivate_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> AgentResponse:
    """Deactivate an agent."""
    if current_user.get("access_level") not in ["admin", "standard"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient privileges to deactivate agents"
        )
    
    agent_service = AgentService(db)
    
    try:
        agent = await agent_service.deactivate_agent(agent_id)
        return AgentResponse.from_orm(agent)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")


# Agent Analytics and Statistics

@router.get("/{agent_id}/stats", response_model=AgentStatsResponse)
async def get_agent_stats(
    agent_id: str,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> AgentStatsResponse:
    """Get comprehensive statistics for an agent."""
    agent_service = AgentService(db)
    
    try:
        stats = await agent_service.get_agent_stats(agent_id)
        return AgentStatsResponse(**stats)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{agent_id}/update-metrics", status_code=status.HTTP_200_OK)
async def update_performance_metrics(
    agent_id: str,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update agent performance metrics based on recent activity."""
    agent_service = AgentService(db)
    
    await agent_service.update_performance_metrics(agent_id)
    return {"message": "Performance metrics updated successfully"}


# Agent Memory and Task Management

@router.get("/{agent_id}/memories")
async def get_agent_memories(
    agent_id: str,
    memory_type: Optional[str] = Query(None, description="Filter by memory type"),
    access_level: Optional[str] = Query(None, description="Filter by access level"),
    is_archived: Optional[bool] = Query(None, description="Filter by archived status"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get memories associated with an agent."""
    agent_service = AgentService(db)
    
    memories = await agent_service.get_agent_memories(
        agent_id=agent_id,
        memory_type=memory_type,
        access_level=access_level,
        is_archived=is_archived,
        limit=limit,
        offset=offset
    )
    
    # Convert to dict representation
    return [
        {
            "id": str(memory.id),
            "content": memory.content[:200] + "..." if len(memory.content) > 200 else memory.content,
            "memory_type": memory.memory_type,
            "access_level": memory.access_level,
            "importance": memory.importance,
            "created_at": memory.created_at.isoformat(),
            "accessed_at": memory.accessed_at.isoformat() if memory.accessed_at else None
        }
        for memory in memories
    ]


@router.get("/{agent_id}/tasks")
async def get_agent_tasks(
    agent_id: str,
    status: Optional[str] = Query(None, description="Filter by task status"),
    task_type: Optional[str] = Query(None, description="Filter by task type"),
    include_collaborating: bool = Query(False, description="Include tasks where agent is collaborating"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get tasks associated with an agent."""
    agent_service = AgentService(db)
    
    tasks = await agent_service.get_agent_tasks(
        agent_id=agent_id,
        status=status,
        task_type=task_type,
        include_collaborating=include_collaborating,
        limit=limit,
        offset=offset
    )
    
    # Convert to dict representation
    return [
        {
            "id": str(task.id),
            "title": task.title,
            "status": task.status,
            "priority": task.priority,
            "progress_percentage": task.progress_percentage,
            "created_at": task.created_at.isoformat(),
            "due_date": task.due_date.isoformat() if task.due_date else None
        }
        for task in tasks
    ]


# Search and Discovery

@router.get("/search/", response_model=List[AgentResponse])
async def search_agents(
    query: str = Query(..., description="Search query"),
    namespace: Optional[str] = Query(None, description="Filter by namespace"),
    agent_type: Optional[str] = Query(None, description="Filter by agent type"),
    limit: int = Query(20, ge=1, le=50, description="Maximum number of results"),
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[AgentResponse]:
    """Search agents by name, capabilities, or other attributes."""
    agent_service = AgentService(db)
    
    agents = await agent_service.search_agents(
        query=query,
        namespace=namespace,
        agent_type=agent_type,
        limit=limit
    )
    
    return [AgentResponse.from_orm(agent) for agent in agents]


@router.get("/recommend/", response_model=List[AgentResponse])
async def get_recommended_agents(
    task_type: Optional[str] = Query(None, description="Task type for recommendations"),
    capabilities: Optional[List[str]] = Query(None, description="Required capabilities"),
    namespace: Optional[str] = Query(None, description="Filter by namespace"),
    limit: int = Query(10, ge=1, le=20, description="Maximum number of results"),
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[AgentResponse]:
    """Get recommended agents based on requirements."""
    agent_service = AgentService(db)
    
    agents = await agent_service.get_recommended_agents(
        task_type=task_type,
        capabilities=capabilities or [],
        namespace=namespace,
        limit=limit
    )
    
    return [AgentResponse.from_orm(agent) for agent in agents]


# Namespace Management

@router.post("/namespaces/", status_code=status.HTTP_201_CREATED)
async def create_namespace(
    namespace_data: NamespaceCreateRequest,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new namespace."""
    if current_user.get("access_level") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient privileges to create namespaces"
        )
    
    agent_service = AgentService(db)
    
    try:
        namespace = await agent_service.create_namespace(
            namespace=namespace_data.namespace,
            display_name=namespace_data.display_name,
            description=namespace_data.description,
            parent_namespace=namespace_data.parent_namespace,
            access_policy=namespace_data.access_policy,
            max_agents=namespace_data.max_agents
        )
        
        return {
            "namespace": namespace.namespace,
            "display_name": namespace.display_name,
            "access_policy": namespace.access_policy,
            "created_at": namespace.created_at.isoformat()
        }
        
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/namespaces/")
async def list_namespaces(
    access_policy: Optional[str] = Query(None, description="Filter by access policy"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List namespaces."""
    agent_service = AgentService(db)
    
    namespaces = await agent_service.list_namespaces(
        access_policy=access_policy,
        is_active=is_active,
        limit=limit,
        offset=offset
    )
    
    return [
        {
            "namespace": ns.namespace,
            "display_name": ns.display_name,
            "description": ns.description,
            "access_policy": ns.access_policy,
            "agent_count": ns.agent_count,
            "is_active": ns.is_active,
            "created_at": ns.created_at.isoformat()
        }
        for ns in namespaces
    ]


# Team Management

@router.post("/teams/", status_code=status.HTTP_201_CREATED)
async def create_team(
    team_data: TeamCreateRequest,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new team."""
    agent_service = AgentService(db)
    
    try:
        team = await agent_service.create_team(
            team_id=team_data.team_id,
            display_name=team_data.display_name,
            description=team_data.description,
            namespace=team_data.namespace,
            team_type=team_data.team_type,
            team_lead=team_data.team_lead,
            max_members=team_data.max_members
        )
        
        return {
            "team_id": team.team_id,
            "display_name": team.display_name,
            "team_type": team.team_type,
            "namespace": team.namespace,
            "created_at": team.created_at.isoformat()
        }
        
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/teams/{team_id}/members/{agent_id}", status_code=status.HTTP_200_OK)
async def add_agent_to_team(
    team_id: str,
    agent_id: str,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Add an agent to a team."""
    agent_service = AgentService(db)
    
    try:
        success = await agent_service.add_agent_to_team(team_id, agent_id)
        if success:
            return {"message": f"Agent {agent_id} added to team {team_id}"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to add agent to team (possibly at capacity or already member)"
            )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/teams/{team_id}/members/{agent_id}", status_code=status.HTTP_200_OK)
async def remove_agent_from_team(
    team_id: str,
    agent_id: str,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Remove an agent from a team."""
    agent_service = AgentService(db)
    
    success = await agent_service.remove_agent_from_team(team_id, agent_id)
    if success:
        return {"message": f"Agent {agent_id} removed from team {team_id}"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team or agent not found, or agent not in team"
        )


# Migration and Compatibility

@router.post("/migrate-from-personas", status_code=status.HTTP_200_OK)
async def migrate_from_personas(
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Migrate existing persona data to agent format."""
    if current_user.get("access_level") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient privileges to run migration"
        )
    
    agent_service = AgentService(db)
    
    try:
        results = await agent_service.migrate_from_personas()
        return {
            "message": "Migration completed successfully",
            "results": results
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Migration failed: {str(e)}"
        )