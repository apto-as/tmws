"""
Workflow management API endpoints for TMWS.
Complete implementation with execution and monitoring.
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_
from sqlalchemy.exc import IntegrityError

from ...core.config import get_settings
from ...core.database import get_db_session_dependency
from ...models.workflow import Workflow, WorkflowStatus, WorkflowPriority
from ...services.workflow_service import WorkflowService
from ...services.workflow_history_service import WorkflowHistoryService
from ..dependencies import get_current_user, get_workflow_service
from ...security.validators import InputValidator

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()
input_validator = InputValidator()


@router.get("/")
async def list_workflows(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of items to return"),
    status: Optional[WorkflowStatus] = Query(None, description="Filter by status"),
    workflow_type: Optional[str] = Query(None, description="Filter by workflow type"),
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get list of workflows with optional filtering.
    """
    try:
        # Build query
        query = select(Workflow)
        
        # Apply filters
        conditions = []
        if status:
            conditions.append(Workflow.status == status)
        if workflow_type:
            conditions.append(Workflow.workflow_type == workflow_type)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # Apply pagination
        query = query.offset(skip).limit(limit).order_by(Workflow.created_at.desc())
        
        # Execute query
        result = await db.execute(query)
        workflows = result.scalars().all()
        
        # Get total count
        count_query = select(Workflow)
        if conditions:
            count_query = count_query.where(and_(*conditions))
        total_result = await db.execute(count_query)
        total = len(total_result.scalars().all())
        
        return {
            "workflows": [workflow.to_dict() for workflow in workflows],
            "total": total,
            "skip": skip,
            "limit": limit,
            "filters": {
                "status": status,
                "workflow_type": workflow_type
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to list workflows: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve workflows"
        )


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_workflow(
    name: str,
    workflow_type: str,
    description: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    priority: WorkflowPriority = WorkflowPriority.MEDIUM,
    metadata: Optional[Dict[str, Any]] = None,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: dict = Depends(get_current_user),
    workflow_service: WorkflowService = Depends(get_workflow_service)
) -> Dict[str, Any]:
    """
    Create a new workflow.
    """
    try:
        # Validate input
        if not input_validator.validate_workflow_name(name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid workflow name"
            )
        
        # Create workflow
        workflow = await workflow_service.create_workflow(
            name=name,
            workflow_type=workflow_type,
            description=description,
            config=config or {},
            priority=priority,
            metadata=metadata or {},
            db_session=db
        )
        
        logger.info(f"Workflow created: {workflow.id}")
        
        return {
            "message": "Workflow created successfully",
            "workflow": workflow.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Failed to create workflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create workflow"
        )


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: UUID,
    include_history: bool = Query(False, description="Include execution history"),
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: dict = Depends(get_current_user),
    history_service: WorkflowHistoryService = Depends(lambda: WorkflowHistoryService())
) -> Dict[str, Any]:
    """
    Get a specific workflow by ID.
    """
    try:
        result = await db.execute(
            select(Workflow).where(Workflow.id == workflow_id)
        )
        workflow = result.scalar_one_or_none()
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow {workflow_id} not found"
            )
        
        response = {
            "workflow": workflow.to_dict()
        }
        
        # Include execution history if requested
        if include_history:
            history = await history_service.get_workflow_history(
                workflow_id=workflow_id,
                limit=10,
                db_session=db
            )
            response["execution_history"] = [h.to_dict() for h in history]
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow {workflow_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve workflow"
        )


@router.put("/{workflow_id}")
async def update_workflow(
    workflow_id: UUID,
    name: Optional[str] = None,
    description: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    priority: Optional[WorkflowPriority] = None,
    metadata: Optional[Dict[str, Any]] = None,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Update an existing workflow.
    """
    try:
        # Get existing workflow
        result = await db.execute(
            select(Workflow).where(Workflow.id == workflow_id)
        )
        workflow = result.scalar_one_or_none()
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow {workflow_id} not found"
            )
        
        # Check if workflow is running
        if workflow.status == WorkflowStatus.RUNNING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update a running workflow"
            )
        
        # Update fields
        if name is not None:
            if not input_validator.validate_workflow_name(name):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid workflow name"
                )
            workflow.name = name
        
        if description is not None:
            workflow.description = description
        if config is not None:
            workflow.config = config
        if priority is not None:
            workflow.priority = priority
        if metadata is not None:
            workflow.metadata = metadata
        
        workflow.updated_at = datetime.utcnow()
        
        # Save changes
        await db.commit()
        await db.refresh(workflow)
        
        logger.info(f"Workflow updated: {workflow_id}")
        
        return {
            "message": "Workflow updated successfully",
            "workflow": workflow.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update workflow {workflow_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update workflow"
        )


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Delete a workflow.
    """
    try:
        # Check if workflow exists
        result = await db.execute(
            select(Workflow).where(Workflow.id == workflow_id)
        )
        workflow = result.scalar_one_or_none()
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow {workflow_id} not found"
            )
        
        # Check if workflow is running
        if workflow.status == WorkflowStatus.RUNNING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete a running workflow"
            )
        
        # Delete workflow
        await db.execute(
            delete(Workflow).where(Workflow.id == workflow_id)
        )
        await db.commit()
        
        logger.info(f"Workflow deleted: {workflow_id}")
        
        return {
            "message": "Workflow deleted successfully",
            "workflow_id": str(workflow_id)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete workflow {workflow_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete workflow"
        )


@router.post("/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: UUID,
    parameters: Optional[Dict[str, Any]] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: dict = Depends(get_current_user),
    workflow_service: WorkflowService = Depends(get_workflow_service)
) -> Dict[str, Any]:
    """
    Execute a workflow asynchronously.
    """
    try:
        # Get workflow
        result = await db.execute(
            select(Workflow).where(Workflow.id == workflow_id)
        )
        workflow = result.scalar_one_or_none()
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow {workflow_id} not found"
            )
        
        # Check if workflow is already running
        if workflow.status == WorkflowStatus.RUNNING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Workflow is already running"
            )
        
        # Update workflow status to running
        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = datetime.utcnow()
        await db.commit()
        
        # Schedule background execution
        background_tasks.add_task(
            workflow_service.execute_workflow,
            workflow_id=workflow_id,
            parameters=parameters or {},
            db_session=db
        )
        
        logger.info(f"Workflow execution started: {workflow_id}")
        
        return {
            "message": "Workflow execution started",
            "workflow_id": str(workflow_id),
            "status": WorkflowStatus.RUNNING.value,
            "started_at": workflow.started_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute workflow {workflow_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute workflow"
        )


@router.get("/{workflow_id}/status")
async def get_workflow_status(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get the current status of a workflow.
    """
    try:
        result = await db.execute(
            select(Workflow).where(Workflow.id == workflow_id)
        )
        workflow = result.scalar_one_or_none()
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow {workflow_id} not found"
            )
        
        return {
            "workflow_id": str(workflow_id),
            "status": workflow.status.value,
            "started_at": workflow.started_at.isoformat() if workflow.started_at else None,
            "completed_at": workflow.completed_at.isoformat() if workflow.completed_at else None,
            "error": workflow.error,
            "result": workflow.result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow status {workflow_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve workflow status"
        )


@router.post("/{workflow_id}/cancel")
async def cancel_workflow(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Cancel a running workflow.
    """
    try:
        # Get workflow
        result = await db.execute(
            select(Workflow).where(Workflow.id == workflow_id)
        )
        workflow = result.scalar_one_or_none()
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow {workflow_id} not found"
            )
        
        # Check if workflow is running
        if workflow.status != WorkflowStatus.RUNNING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Workflow is not running"
            )
        
        # Update status to cancelled
        workflow.status = WorkflowStatus.CANCELLED
        workflow.completed_at = datetime.utcnow()
        workflow.error = "Cancelled by user"
        
        await db.commit()
        
        logger.info(f"Workflow cancelled: {workflow_id}")
        
        return {
            "message": "Workflow cancelled successfully",
            "workflow_id": str(workflow_id),
            "status": WorkflowStatus.CANCELLED.value
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel workflow {workflow_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel workflow"
        )


@router.get("/stats/summary")
async def get_workflow_statistics(
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get workflow statistics summary.
    """
    try:
        # Get counts by status
        status_counts = {}
        for status in WorkflowStatus:
            result = await db.execute(
                select(Workflow).where(Workflow.status == status)
            )
            status_counts[status.value] = len(result.scalars().all())
        
        # Get total count
        total_result = await db.execute(select(Workflow))
        total = len(total_result.scalars().all())
        
        # Get workflow type counts
        type_counts_result = await db.execute(select(Workflow))
        workflows = type_counts_result.scalars().all()
        type_counts = {}
        for workflow in workflows:
            wf_type = workflow.workflow_type
            type_counts[wf_type] = type_counts.get(wf_type, 0) + 1
        
        return {
            "total_workflows": total,
            "by_status": status_counts,
            "by_type": type_counts,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get workflow statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        )