"""
Agent service for TMWS v2.0 - Universal Multi-Agent Platform.
Replaces PersonaService with universal agent management capabilities.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.exceptions import NotFoundError, ValidationError, DatabaseError
from ..models.agent import Agent, AgentTeam, AgentNamespace
from ..models.memory import Memory
from ..models.task import Task

logger = logging.getLogger(__name__)


class AgentService:
    """
    Universal agent management service.
    
    Provides comprehensive agent lifecycle management, namespace organization,
    and performance tracking for any AI agent type.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # Agent CRUD Operations
    
    async def create_agent(
        self,
        agent_id: str,
        display_name: str,
        agent_type: str,
        agent_subtype: Optional[str] = None,
        capabilities: Dict[str, Any] = None,
        configuration: Dict[str, Any] = None,
        namespace: str = "default",
        access_level: str = "standard",
        parent_agent_id: Optional[str] = None,
        team_memberships: List[str] = None,
        learning_enabled: bool = True,
        adaptation_rate: float = 0.1
    ) -> Agent:
        """Create a new agent with comprehensive configuration."""
        
        # Validate agent_id uniqueness
        existing = await self.get_agent_by_id(agent_id)
        if existing:
            raise ValidationError(f"Agent with ID '{agent_id}' already exists")
        
        # Validate parent agent exists if specified
        if parent_agent_id:
            parent = await self.get_agent_by_id(parent_agent_id)
            if not parent:
                raise ValidationError(f"Parent agent '{parent_agent_id}' not found")
        
        # Validate namespace exists
        namespace_exists = await self.namespace_exists(namespace)
        if not namespace_exists:
            # Auto-create namespace if it doesn't exist
            await self.create_namespace(
                namespace=namespace,
                display_name=f"Auto-created namespace: {namespace}",
                access_policy="private"
            )
        
        agent = Agent(
            agent_id=agent_id,
            display_name=display_name,
            agent_type=agent_type,
            agent_subtype=agent_subtype,
            capabilities=capabilities or {},
            configuration=configuration or {},
            namespace=namespace,
            access_level=access_level,
            parent_agent_id=parent_agent_id,
            team_memberships=team_memberships or [],
            learning_enabled=learning_enabled,
            adaptation_rate=adaptation_rate
        )
        
        try:
            self.session.add(agent)
            await self.session.commit()
            await self.session.refresh(agent)
            
            logger.info(f"Created agent {agent_id}: {display_name} ({agent_type})")
            return agent
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to create agent {agent_id}: {e}")
            raise DatabaseError(f"Failed to create agent: {e}") from e
    
    async def get_agent_by_id(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by their ID."""
        try:
            result = await self.session.execute(
                select(Agent)
                .where(Agent.agent_id == agent_id)
                .options(
                    selectinload(Agent.memories),
                    selectinload(Agent.tasks)
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get agent {agent_id}: {e}")
            return None
    
    async def get_agent_by_display_name(self, display_name: str, namespace: str = None) -> Optional[Agent]:
        """Get an agent by their display name, optionally within a namespace."""
        try:
            query = select(Agent).where(Agent.display_name == display_name)
            if namespace:
                query = query.where(Agent.namespace == namespace)
            
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get agent by name {display_name}: {e}")
            return None
    
    async def list_agents(
        self,
        namespace: str = None,
        agent_type: str = None,
        access_level: str = None,
        is_active: bool = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Agent]:
        """List agents with optional filtering."""
        try:
            query = select(Agent)
            
            # Apply filters
            conditions = []
            if namespace:
                conditions.append(Agent.namespace == namespace)
            if agent_type:
                conditions.append(Agent.agent_type == agent_type)
            if access_level:
                conditions.append(Agent.access_level == access_level)
            if is_active is not None:
                conditions.append(Agent.is_active == is_active)
            
            if conditions:
                query = query.where(and_(*conditions))
            
            query = query.order_by(Agent.last_activity.desc()).limit(limit).offset(offset)
            
            result = await self.session.execute(query)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"Failed to list agents: {e}")
            return []
    
    async def update_agent(
        self,
        agent_id: str,
        updates: Dict[str, Any]
    ) -> Agent:
        """Update an existing agent."""
        agent = await self.get_agent_by_id(agent_id)
        if not agent:
            raise NotFoundError(f"Agent {agent_id} not found")
        
        try:
            # Apply updates
            for field, value in updates.items():
                if hasattr(agent, field):
                    setattr(agent, field, value)
            
            # Update activity timestamp
            agent.update_activity()
            
            await self.session.commit()
            await self.session.refresh(agent)
            
            logger.info(f"Updated agent {agent_id}")
            return agent
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to update agent {agent_id}: {e}")
            raise DatabaseError(f"Failed to update agent: {e}") from e
    
    async def deactivate_agent(self, agent_id: str) -> Agent:
        """Deactivate an agent (soft delete)."""
        return await self.update_agent(agent_id, {"is_active": False})
    
    async def activate_agent(self, agent_id: str) -> Agent:
        """Reactivate a deactivated agent."""
        return await self.update_agent(agent_id, {"is_active": True})
    
    async def delete_agent(self, agent_id: str, force: bool = False) -> bool:
        """Delete an agent (hard delete if force=True, otherwise soft delete)."""
        if not force:
            await self.deactivate_agent(agent_id)
            return True
        
        agent = await self.get_agent_by_id(agent_id)
        if not agent:
            return False
        
        try:
            await self.session.delete(agent)
            await self.session.commit()
            
            logger.info(f"Hard deleted agent {agent_id}")
            return True
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to delete agent {agent_id}: {e}")
            raise DatabaseError(f"Failed to delete agent: {e}") from e
    
    # Agent Performance and Analytics
    
    async def get_agent_stats(self, agent_id: str) -> Dict[str, Any]:
        """Get comprehensive statistics for an agent."""
        agent = await self.get_agent_by_id(agent_id)
        if not agent:
            raise NotFoundError(f"Agent {agent_id} not found")
        
        try:
            # Count memories
            memory_count = await self.session.scalar(
                select(func.count(Memory.id)).where(Memory.agent_id == agent_id)
            )
            
            # Count tasks
            task_count = await self.session.scalar(
                select(func.count(Task.id)).where(Task.assigned_agent_id == agent_id)
            )
            
            # Count completed tasks
            completed_tasks = await self.session.scalar(
                select(func.count(Task.id)).where(
                    and_(Task.assigned_agent_id == agent_id, Task.status == "completed")
                )
            )
            
            # Average quality score
            avg_quality = await self.session.scalar(
                select(func.avg(Task.quality_score)).where(
                    and_(Task.assigned_agent_id == agent_id, Task.quality_score.isnot(None))
                )
            ) or 0.0
            
            # Calculate success rate
            success_rate = (completed_tasks / task_count) if task_count > 0 else 0.0
            
            return {
                "agent_id": agent_id,
                "display_name": agent.display_name,
                "agent_type": agent.agent_type,
                "namespace": agent.namespace,
                "is_active": agent.is_active,
                "performance_score": agent.performance_score,
                "capability_score": agent.capability_score,
                "total_memories": memory_count,
                "total_tasks": task_count,
                "completed_tasks": completed_tasks,
                "success_rate": success_rate,
                "average_quality_score": float(avg_quality),
                "last_activity": agent.last_activity.isoformat() if agent.last_activity else None,
                "created_at": agent.created_at.isoformat(),
                "updated_at": agent.updated_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get agent stats for {agent_id}: {e}")
            raise DatabaseError(f"Failed to get agent stats: {e}") from e
    
    async def update_performance_metrics(self, agent_id: str) -> None:
        """Update agent performance metrics based on recent activity."""
        agent = await self.get_agent_by_id(agent_id)
        if not agent:
            return
        
        try:
            # Get recent task performance (last 30 days)
            from datetime import datetime, timedelta
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            
            # Calculate performance score based on recent tasks
            recent_tasks = await self.session.execute(
                select(Task).where(
                    and_(
                        Task.assigned_agent_id == agent_id,
                        Task.completed_at >= thirty_days_ago,
                        Task.status == "completed"
                    )
                )
            )
            
            tasks = list(recent_tasks.scalars().all())
            if tasks:
                # Performance factors: quality, efficiency, success rate
                quality_scores = [t.quality_score for t in tasks if t.quality_score is not None]
                efficiency_scores = [t.efficiency_score for t in tasks if t.efficiency_score is not None]
                
                avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 5.0
                avg_efficiency = sum(efficiency_scores) / len(efficiency_scores) if efficiency_scores else 1.0
                
                # Calculate composite performance score (0-10 scale)
                performance_score = min(10.0, (avg_quality + avg_efficiency * 5.0) / 2.0)
                agent.update_performance_score(performance_score)
            
            # Update counters
            memory_count = await self.session.scalar(
                select(func.count(Memory.id)).where(Memory.agent_id == agent_id)
            )
            task_count = await self.session.scalar(
                select(func.count(Task.id)).where(Task.assigned_agent_id == agent_id)
            )
            
            agent.total_memories = memory_count or 0
            agent.total_tasks = task_count or 0
            agent.update_activity()
            
            await self.session.commit()
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to update performance metrics for {agent_id}: {e}")
    
    # Agent Memory Management
    
    async def get_agent_memories(
        self,
        agent_id: str,
        memory_type: str = None,
        access_level: str = None,
        is_archived: bool = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Memory]:
        """Get memories associated with an agent."""
        try:
            query = select(Memory).where(Memory.agent_id == agent_id)
            
            if memory_type:
                query = query.where(Memory.memory_type == memory_type)
            if access_level:
                query = query.where(Memory.access_level == access_level)
            if is_archived is not None:
                query = query.where(Memory.is_archived == is_archived)
            
            query = query.order_by(Memory.accessed_at.desc()).limit(limit).offset(offset)
            
            result = await self.session.execute(query)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"Failed to get memories for agent {agent_id}: {e}")
            return []
    
    async def get_agent_tasks(
        self,
        agent_id: str,
        status: str = None,
        task_type: str = None,
        include_collaborating: bool = False,
        limit: int = 100,
        offset: int = 0
    ) -> List[Task]:
        """Get tasks associated with an agent."""
        try:
            if include_collaborating:
                # Include tasks where agent is assigned or collaborating
                query = select(Task).where(
                    (Task.assigned_agent_id == agent_id) |
                    (Task.collaborating_agents.contains([agent_id]))
                )
            else:
                query = select(Task).where(Task.assigned_agent_id == agent_id)
            
            if status:
                query = query.where(Task.status == status)
            if task_type:
                query = query.where(Task.task_type == task_type)
            
            query = query.order_by(Task.created_at.desc()).limit(limit).offset(offset)
            
            result = await self.session.execute(query)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"Failed to get tasks for agent {agent_id}: {e}")
            return []
    
    # Namespace Management
    
    async def create_namespace(
        self,
        namespace: str,
        display_name: str,
        description: str = None,
        parent_namespace: str = None,
        access_policy: str = "private",
        max_agents: int = None
    ) -> AgentNamespace:
        """Create a new agent namespace."""
        existing = await self.get_namespace(namespace)
        if existing:
            raise ValidationError(f"Namespace '{namespace}' already exists")
        
        namespace_obj = AgentNamespace(
            namespace=namespace,
            display_name=display_name,
            description=description,
            parent_namespace=parent_namespace,
            access_policy=access_policy,
            max_agents=max_agents
        )
        
        try:
            self.session.add(namespace_obj)
            await self.session.commit()
            await self.session.refresh(namespace_obj)
            
            logger.info(f"Created namespace: {namespace}")
            return namespace_obj
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to create namespace {namespace}: {e}")
            raise DatabaseError(f"Failed to create namespace: {e}") from e
    
    async def get_namespace(self, namespace: str) -> Optional[AgentNamespace]:
        """Get a namespace by name."""
        try:
            result = await self.session.execute(
                select(AgentNamespace).where(AgentNamespace.namespace == namespace)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get namespace {namespace}: {e}")
            return None
    
    async def namespace_exists(self, namespace: str) -> bool:
        """Check if a namespace exists."""
        result = await self.get_namespace(namespace)
        return result is not None
    
    async def list_namespaces(
        self,
        access_policy: str = None,
        is_active: bool = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[AgentNamespace]:
        """List namespaces with optional filtering."""
        try:
            query = select(AgentNamespace)
            
            conditions = []
            if access_policy:
                conditions.append(AgentNamespace.access_policy == access_policy)
            if is_active is not None:
                conditions.append(AgentNamespace.is_active == is_active)
            
            if conditions:
                query = query.where(and_(*conditions))
            
            query = query.order_by(AgentNamespace.namespace).limit(limit).offset(offset)
            
            result = await self.session.execute(query)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"Failed to list namespaces: {e}")
            return []
    
    # Team Management
    
    async def create_team(
        self,
        team_id: str,
        display_name: str,
        description: str = None,
        namespace: str = "default",
        team_type: str = "collaborative",
        team_lead: str = None,
        max_members: int = None
    ) -> AgentTeam:
        """Create a new agent team."""
        existing = await self.get_team(team_id)
        if existing:
            raise ValidationError(f"Team '{team_id}' already exists")
        
        team = AgentTeam(
            team_id=team_id,
            display_name=display_name,
            description=description,
            namespace=namespace,
            team_type=team_type,
            team_lead=team_lead,
            max_members=max_members
        )
        
        try:
            self.session.add(team)
            await self.session.commit()
            await self.session.refresh(team)
            
            logger.info(f"Created team: {team_id}")
            return team
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to create team {team_id}: {e}")
            raise DatabaseError(f"Failed to create team: {e}") from e
    
    async def get_team(self, team_id: str) -> Optional[AgentTeam]:
        """Get a team by ID."""
        try:
            result = await self.session.execute(
                select(AgentTeam).where(AgentTeam.team_id == team_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get team {team_id}: {e}")
            return None
    
    async def add_agent_to_team(self, team_id: str, agent_id: str) -> bool:
        """Add an agent to a team."""
        team = await self.get_team(team_id)
        if not team:
            raise NotFoundError(f"Team {team_id} not found")
        
        agent = await self.get_agent_by_id(agent_id)
        if not agent:
            raise NotFoundError(f"Agent {agent_id} not found")
        
        try:
            success = team.add_member(agent_id)
            if success:
                # Update agent's team memberships
                if team_id not in agent.team_memberships:
                    agent.team_memberships.append(team_id)
                
                await self.session.commit()
                logger.info(f"Added agent {agent_id} to team {team_id}")
                return True
            return False
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to add agent {agent_id} to team {team_id}: {e}")
            return False
    
    async def remove_agent_from_team(self, team_id: str, agent_id: str) -> bool:
        """Remove an agent from a team."""
        team = await self.get_team(team_id)
        if not team:
            return False
        
        agent = await self.get_agent_by_id(agent_id)
        if not agent:
            return False
        
        try:
            success = team.remove_member(agent_id)
            if success:
                # Update agent's team memberships
                if team_id in agent.team_memberships:
                    agent.team_memberships.remove(team_id)
                
                await self.session.commit()
                logger.info(f"Removed agent {agent_id} from team {team_id}")
                return True
            return False
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to remove agent {agent_id} from team {team_id}: {e}")
            return False
    
    # Migration and Compatibility
    
    async def migrate_from_personas(self) -> Dict[str, Any]:
        """Migrate existing Persona data to Agent format."""
        try:
            # This would be implemented to migrate data from the old persona table
            # For now, create default Trinitas agents
            default_agents = Agent.create_default_agents()
            created_agents = []
            
            for agent_data in default_agents:
                try:
                    agent = await self.create_agent(**agent_data)
                    created_agents.append(agent.agent_id)
                except ValidationError:
                    # Agent already exists, skip
                    logger.info(f"Agent {agent_data['agent_id']} already exists, skipping")
                    continue
            
            logger.info(f"Migration complete: created {len(created_agents)} agents")
            return {
                "created_agents": created_agents,
                "total_created": len(created_agents)
            }
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise DatabaseError(f"Migration failed: {e}") from e
    
    # Search and Discovery
    
    async def search_agents(
        self,
        query: str,
        namespace: str = None,
        agent_type: str = None,
        limit: int = 20
    ) -> List[Agent]:
        """Search agents by name, capabilities, or other attributes."""
        try:
            # Simple text search - could be enhanced with full-text search
            search_query = select(Agent).where(
                (Agent.display_name.ilike(f"%{query}%")) |
                (Agent.agent_id.ilike(f"%{query}%")) |
                (Agent.agent_type.ilike(f"%{query}%"))
            )
            
            if namespace:
                search_query = search_query.where(Agent.namespace == namespace)
            if agent_type:
                search_query = search_query.where(Agent.agent_type == agent_type)
            
            search_query = search_query.where(Agent.is_active == True).limit(limit)
            
            result = await self.session.execute(search_query)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"Failed to search agents with query '{query}': {e}")
            return []
    
    async def get_recommended_agents(
        self,
        task_type: str = None,
        capabilities: List[str] = None,
        namespace: str = None,
        limit: int = 10
    ) -> List[Agent]:
        """Get recommended agents based on task requirements."""
        try:
            query = select(Agent).where(Agent.is_active == True)
            
            if namespace:
                query = query.where(Agent.namespace == namespace)
            
            # Order by performance score and capability match
            query = query.order_by(Agent.performance_score.desc()).limit(limit)
            
            result = await self.session.execute(query)
            agents = list(result.scalars().all())
            
            # TODO: Implement more sophisticated matching based on capabilities
            # This could use ML models or rule-based matching
            
            return agents
            
        except Exception as e:
            logger.error(f"Failed to get recommended agents: {e}")
            return []