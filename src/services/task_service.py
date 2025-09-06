"""
Task Service for TMWS
Handles task management and execution tracking
"""

import logging
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import Task, Persona
from ..core.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


class TaskService:
    """Service for managing tasks."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_task(
        self,
        title: str,
        description: str,
        task_type: str = "general",
        priority: str = "medium",
        assigned_persona_id: Optional[UUID] = None,
        dependencies: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> Task:
        """Create a new task."""
        # Validate priority
        valid_priorities = ["low", "medium", "high", "critical"]
        if priority not in valid_priorities:
            raise ValidationError(f"Invalid priority: {priority}. Must be one of {valid_priorities}")
        
        # Validate persona if assigned
        if assigned_persona_id:
            persona_result = await self.session.execute(
                select(Persona).where(Persona.id == assigned_persona_id)
            )
            if not persona_result.scalar_one_or_none():
                raise NotFoundError(f"Persona {assigned_persona_id} not found")
        
        task = Task(
            title=title,
            description=description,
            task_type=task_type,
            priority=priority,
            status="pending",
            progress=0.0,
            assigned_persona_id=assigned_persona_id,
            dependencies=dependencies or [],
            metadata_json=metadata or {}
        )
        
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        
        logger.info(f"Created task {task.id}: {title}")
        return task
    
    async def get_task(self, task_id: UUID) -> Optional[Task]:
        """Get a task by ID."""
        result = await self.session.execute(
            select(Task)
            .where(Task.id == task_id)
            .options(selectinload(Task.assigned_persona))
        )
        return result.scalar_one_or_none()
    
    async def update_task(
        self,
        task_id: UUID,
        updates: Dict[str, Any]
    ) -> Task:
        """Update an existing task."""
        task = await self.get_task(task_id)
        if not task:
            raise NotFoundError(f"Task {task_id} not found")
        
        # Update allowed fields
        allowed_fields = [
            'title', 'description', 'task_type', 'priority', 'status',
            'progress', 'assigned_persona_id', 'dependencies', 'result',
            'metadata_json', 'started_at', 'completed_at'
        ]
        
        for key, value in updates.items():
            if key in allowed_fields:
                # Special handling for status changes
                if key == 'status':
                    await self._handle_status_change(task, value)
                else:
                    setattr(task, key, value)
        
        task.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(task)
        
        logger.info(f"Updated task {task_id}")
        return task
    
    async def _handle_status_change(self, task: Task, new_status: str):
        """Handle special logic for status changes."""
        valid_statuses = ["pending", "in_progress", "completed", "failed", "cancelled"]
        if new_status not in valid_statuses:
            raise ValidationError(f"Invalid status: {new_status}")
        
        old_status = task.status
        task.status = new_status
        
        # Set timestamps based on status
        if new_status == "in_progress" and not task.started_at:
            task.started_at = datetime.utcnow()
        elif new_status in ["completed", "failed", "cancelled"] and not task.completed_at:
            task.completed_at = datetime.utcnow()
            if new_status == "completed":
                task.progress = 1.0
        
        logger.info(f"Task {task.id} status changed from {old_status} to {new_status}")
    
    async def delete_task(self, task_id: UUID) -> bool:
        """Delete a task."""
        task = await self.get_task(task_id)
        if not task:
            raise NotFoundError(f"Task {task_id} not found")
        
        await self.session.delete(task)
        await self.session.commit()
        
        logger.info(f"Deleted task {task_id}")
        return True
    
    async def list_tasks(
        self,
        status: str = None,
        priority: str = None,
        task_type: str = None,
        assigned_persona_id: UUID = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Task]:
        """List tasks with filters."""
        stmt = select(Task).options(selectinload(Task.assigned_persona))
        
        conditions = []
        if status:
            conditions.append(Task.status == status)
        if priority:
            conditions.append(Task.priority == priority)
        if task_type:
            conditions.append(Task.task_type == task_type)
        if assigned_persona_id:
            conditions.append(Task.assigned_persona_id == assigned_persona_id)
        
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        # Order by priority and creation date
        priority_order = func.case(
            (Task.priority == "critical", 1),
            (Task.priority == "high", 2),
            (Task.priority == "medium", 3),
            (Task.priority == "low", 4),
            else_=5
        )
        
        stmt = stmt.order_by(priority_order, Task.created_at.desc())
        stmt = stmt.limit(limit).offset(offset)
        
        result = await self.session.execute(stmt)
        tasks = result.scalars().all()
        
        return tasks
    
    async def get_pending_tasks(
        self,
        assigned_persona_id: UUID = None,
        limit: int = 10
    ) -> List[Task]:
        """Get pending tasks, optionally filtered by persona."""
        conditions = [Task.status == "pending"]
        if assigned_persona_id:
            conditions.append(Task.assigned_persona_id == assigned_persona_id)
        
        stmt = select(Task).where(and_(*conditions))
        stmt = stmt.order_by(Task.created_at)
        stmt = stmt.limit(limit)
        
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def get_task_dependencies(self, task_id: UUID) -> List[Task]:
        """Get all tasks that this task depends on."""
        task = await self.get_task(task_id)
        if not task or not task.dependencies:
            return []
        
        # Dependencies are stored as task IDs
        dependency_ids = [UUID(dep) for dep in task.dependencies]
        
        stmt = select(Task).where(Task.id.in_(dependency_ids))
        result = await self.session.execute(stmt)
        
        return result.scalars().all()
    
    async def check_dependencies_met(self, task_id: UUID) -> bool:
        """Check if all dependencies for a task are completed."""
        dependencies = await self.get_task_dependencies(task_id)
        
        for dep in dependencies:
            if dep.status != "completed":
                return False
        
        return True
    
    async def count_active_tasks(self) -> int:
        """Count tasks that are pending or in progress."""
        stmt = select(func.count(Task.id)).where(
            or_(Task.status == "pending", Task.status == "in_progress")
        )
        
        result = await self.session.execute(stmt)
        count = result.scalar()
        
        return count or 0
    
    async def get_task_stats(self) -> Dict[str, Any]:
        """Get task statistics."""
        # Count by status
        status_counts_stmt = select(
            Task.status,
            func.count(Task.id).label('count')
        ).group_by(Task.status)
        
        status_counts_result = await self.session.execute(status_counts_stmt)
        status_counts = {row.status: row.count for row in status_counts_result}
        
        # Count by priority
        priority_counts_stmt = select(
            Task.priority,
            func.count(Task.id).label('count')
        ).group_by(Task.priority)
        
        priority_counts_result = await self.session.execute(priority_counts_stmt)
        priority_counts = {row.priority: row.count for row in priority_counts_result}
        
        # Average completion time for completed tasks
        completion_time_stmt = select(
            func.avg(
                func.extract('epoch', Task.completed_at - Task.started_at)
            )
        ).where(
            and_(
                Task.status == "completed",
                Task.started_at.isnot(None),
                Task.completed_at.isnot(None)
            )
        )
        
        completion_time_result = await self.session.execute(completion_time_stmt)
        avg_completion_seconds = completion_time_result.scalar()
        
        return {
            "tasks_by_status": status_counts,
            "tasks_by_priority": priority_counts,
            "active_tasks": status_counts.get("pending", 0) + status_counts.get("in_progress", 0),
            "completed_tasks": status_counts.get("completed", 0),
            "failed_tasks": status_counts.get("failed", 0),
            "avg_completion_time_seconds": float(avg_completion_seconds) if avg_completion_seconds else None
        }