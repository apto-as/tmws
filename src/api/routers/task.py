"""
Task management API endpoints for TMWS.
Complete implementation with full CRUD operations.
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_
from sqlalchemy.exc import IntegrityError

from ...core.config import get_settings
from ...core.database import get_db_session_dependency
from ...models.task import Task, TaskStatus, TaskPriority
from ...services.task_service import TaskService
from ..dependencies import get_current_user, get_task_service
from ...security.validators import InputValidator

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()
input_validator = InputValidator()


@router.get("/")
async def list_tasks(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of items to return"),
    status: Optional[TaskStatus] = Query(None, description="Filter by status"),
    priority: Optional[TaskPriority] = Query(None, description="Filter by priority"),
    assigned_persona: Optional[str] = Query(None, description="Filter by assigned persona"),
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: dict = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service)
) -> Dict[str, Any]:
    """
    Get list of tasks with optional filtering.
    """
    try:
        # Build query
        query = select(Task)
        
        # Apply filters
        conditions = []
        if status:
            conditions.append(Task.status == status)
        if priority:
            conditions.append(Task.priority == priority)
        if assigned_persona:
            conditions.append(Task.assigned_persona == assigned_persona)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # Apply pagination
        query = query.offset(skip).limit(limit)
        
        # Execute query
        result = await db.execute(query)
        tasks = result.scalars().all()
        
        # Get total count
        count_query = select(Task)
        if conditions:
            count_query = count_query.where(and_(*conditions))
        total_result = await db.execute(count_query)
        total = len(total_result.scalars().all())
        
        return {
            "tasks": [task.to_dict() for task in tasks],
            "total": total,
            "skip": skip,
            "limit": limit,
            "filters": {
                "status": status,
                "priority": priority,
                "assigned_persona": assigned_persona
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tasks"
        )


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_task(
    title: str,
    description: Optional[str] = None,
    priority: TaskPriority = TaskPriority.MEDIUM,
    assigned_persona: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: dict = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service)
) -> Dict[str, Any]:
    """
    Create a new task.
    """
    try:
        # Validate input
        if not input_validator.validate_task_title(title):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid task title"
            )
        
        # Create task
        task = await task_service.create_task(
            title=title,
            description=description,
            priority=priority,
            assigned_persona=assigned_persona,
            metadata=metadata or {},
            db_session=db
        )
        
        logger.info(f"Task created: {task.id}")
        
        return {
            "message": "Task created successfully",
            "task": task.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Failed to create task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create task"
        )


@router.get("/{task_id}")
async def get_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get a specific task by ID.
    """
    try:
        result = await db.execute(
            select(Task).where(Task.id == task_id)
        )
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found"
            )
        
        return {
            "task": task.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve task"
        )


@router.put("/{task_id}")
async def update_task(
    task_id: UUID,
    title: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[TaskStatus] = None,
    priority: Optional[TaskPriority] = None,
    assigned_persona: Optional[str] = None,
    progress: Optional[int] = Query(None, ge=0, le=100),
    metadata: Optional[Dict[str, Any]] = None,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: dict = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service)
) -> Dict[str, Any]:
    """
    Update an existing task.
    """
    try:
        # Get existing task
        result = await db.execute(
            select(Task).where(Task.id == task_id)
        )
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found"
            )
        
        # Update fields
        if title is not None:
            if not input_validator.validate_task_title(title):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid task title"
                )
            task.title = title
        
        if description is not None:
            task.description = description
        if status is not None:
            task.status = status
        if priority is not None:
            task.priority = priority
        if assigned_persona is not None:
            task.assigned_persona = assigned_persona
        if progress is not None:
            task.progress = progress
        if metadata is not None:
            task.metadata = metadata
        
        task.updated_at = datetime.utcnow()
        
        # Save changes
        await db.commit()
        await db.refresh(task)
        
        logger.info(f"Task updated: {task_id}")
        
        return {
            "message": "Task updated successfully",
            "task": task.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update task {task_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update task"
        )


@router.delete("/{task_id}")
async def delete_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Delete a task.
    """
    try:
        # Check if task exists
        result = await db.execute(
            select(Task).where(Task.id == task_id)
        )
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found"
            )
        
        # Delete task
        await db.execute(
            delete(Task).where(Task.id == task_id)
        )
        await db.commit()
        
        logger.info(f"Task deleted: {task_id}")
        
        return {
            "message": "Task deleted successfully",
            "task_id": str(task_id)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete task {task_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete task"
        )


@router.post("/{task_id}/complete")
async def complete_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: dict = Depends(get_current_user),
    task_service: TaskService = Depends(get_task_service)
) -> Dict[str, Any]:
    """
    Mark a task as completed.
    """
    try:
        task = await task_service.complete_task(task_id, db)
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found"
            )
        
        return {
            "message": "Task completed successfully",
            "task": task.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to complete task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete task"
        )


@router.get("/stats/summary")
async def get_task_statistics(
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get task statistics summary.
    """
    try:
        # Get counts by status
        status_counts = {}
        for status in TaskStatus:
            result = await db.execute(
                select(Task).where(Task.status == status)
            )
            status_counts[status.value] = len(result.scalars().all())
        
        # Get counts by priority
        priority_counts = {}
        for priority in TaskPriority:
            result = await db.execute(
                select(Task).where(Task.priority == priority)
            )
            priority_counts[priority.value] = len(result.scalars().all())
        
        # Get total count
        total_result = await db.execute(select(Task))
        total = len(total_result.scalars().all())
        
        return {
            "total_tasks": total,
            "by_status": status_counts,
            "by_priority": priority_counts,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get task statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        )