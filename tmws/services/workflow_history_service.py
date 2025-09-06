"""
Workflow History Service for TMWS
Handles workflow execution history persistence and querying
"""

import logging
import json
import time
import traceback
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
from datetime import datetime, timedelta

from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.workflow_history import (
    WorkflowExecution,
    WorkflowStepExecution,
    WorkflowExecutionLog,
    WorkflowSchedule
)
from ..models import Workflow
from ..core.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


class WorkflowHistoryService:
    """Service for managing workflow execution history."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def start_execution(
        self,
        workflow_id: UUID,
        triggered_by: str = "system",
        trigger_type: str = "manual",
        input_data: Dict[str, Any] = None
    ) -> WorkflowExecution:
        """Start tracking a new workflow execution."""
        
        # Verify workflow exists
        workflow = await self.session.get(Workflow, workflow_id)
        if not workflow:
            raise NotFoundError(f"Workflow {workflow_id} not found")
        
        execution = WorkflowExecution(
            workflow_id=workflow_id,
            started_at=datetime.utcnow(),
            status="running",
            triggered_by=triggered_by,
            trigger_type=trigger_type,
            input_data=input_data or {},
            metadata_json={
                "workflow_name": workflow.name,
                "workflow_version": workflow.metadata_json.get("version", "1.0.0")
            }
        )
        
        self.session.add(execution)
        await self.session.commit()
        await self.session.refresh(execution)
        
        # Log execution start
        await self.add_log(
            execution.id,
            level="info",
            message=f"Workflow execution started: {workflow.name}",
            component="workflow_engine"
        )
        
        logger.info(f"Started workflow execution {execution.id} for workflow {workflow_id}")
        return execution
    
    async def complete_execution(
        self,
        execution_id: UUID,
        status: str = "completed",
        output_data: Dict[str, Any] = None,
        error_message: str = None,
        error_details: Dict[str, Any] = None,
        performance_metrics: Dict[str, float] = None
    ) -> WorkflowExecution:
        """Complete a workflow execution."""
        
        execution = await self.session.get(WorkflowExecution, execution_id)
        if not execution:
            raise NotFoundError(f"Workflow execution {execution_id} not found")
        
        execution.completed_at = datetime.utcnow()
        execution.status = status
        execution.output_data = output_data or {}
        
        # Calculate execution time
        if execution.started_at:
            execution.execution_time_seconds = (
                execution.completed_at - execution.started_at
            ).total_seconds()
        
        # Add error information if failed
        if status == "failed":
            execution.error_message = error_message
            execution.error_details = error_details or {}
        
        # Add performance metrics if provided
        if performance_metrics:
            execution.cpu_time_seconds = performance_metrics.get("cpu_time")
            execution.memory_peak_mb = performance_metrics.get("memory_peak")
        
        await self.session.commit()
        await self.session.refresh(execution)
        
        # Log execution completion
        await self.add_log(
            execution.id,
            level="info" if status == "completed" else "error",
            message=f"Workflow execution {status}: {error_message or 'Success'}",
            component="workflow_engine"
        )
        
        logger.info(f"Completed workflow execution {execution_id} with status {status}")
        return execution
    
    async def start_step_execution(
        self,
        workflow_execution_id: UUID,
        step_name: str,
        step_index: int,
        step_type: str = "action",
        input_data: Dict[str, Any] = None
    ) -> WorkflowStepExecution:
        """Start tracking a workflow step execution."""
        
        step_execution = WorkflowStepExecution(
            workflow_execution_id=workflow_execution_id,
            step_name=step_name,
            step_index=step_index,
            step_type=step_type,
            started_at=datetime.utcnow(),
            status="running",
            input_data=input_data or {}
        )
        
        self.session.add(step_execution)
        await self.session.commit()
        await self.session.refresh(step_execution)
        
        # Log step start
        await self.add_log(
            workflow_execution_id,
            step_execution_id=step_execution.id,
            level="debug",
            message=f"Step started: {step_name}",
            component="step_executor"
        )
        
        return step_execution
    
    async def complete_step_execution(
        self,
        step_execution_id: UUID,
        status: str = "completed",
        output_data: Dict[str, Any] = None,
        error_message: str = None,
        error_details: Dict[str, Any] = None
    ) -> WorkflowStepExecution:
        """Complete a workflow step execution."""
        
        step_execution = await self.session.get(WorkflowStepExecution, step_execution_id)
        if not step_execution:
            raise NotFoundError(f"Step execution {step_execution_id} not found")
        
        step_execution.completed_at = datetime.utcnow()
        step_execution.status = status
        step_execution.output_data = output_data or {}
        
        # Calculate execution time
        if step_execution.started_at:
            step_execution.execution_time_seconds = (
                step_execution.completed_at - step_execution.started_at
            ).total_seconds()
        
        # Add error information if failed
        if status == "failed":
            step_execution.error_message = error_message
            step_execution.error_details = error_details or {}
        
        await self.session.commit()
        await self.session.refresh(step_execution)
        
        # Log step completion
        await self.add_log(
            step_execution.workflow_execution_id,
            step_execution_id=step_execution.id,
            level="debug" if status == "completed" else "error",
            message=f"Step {status}: {step_execution.step_name} - {error_message or 'Success'}",
            component="step_executor"
        )
        
        return step_execution
    
    async def add_log(
        self,
        workflow_execution_id: UUID,
        level: str,
        message: str,
        component: str = None,
        function: str = None,
        step_execution_id: UUID = None,
        context_data: Dict[str, Any] = None
    ) -> WorkflowExecutionLog:
        """Add a log entry for workflow execution."""
        
        log_entry = WorkflowExecutionLog(
            workflow_execution_id=workflow_execution_id,
            step_execution_id=step_execution_id,
            timestamp=datetime.utcnow(),
            level=level,
            message=message,
            component=component,
            function=function,
            context_data=context_data or {}
        )
        
        self.session.add(log_entry)
        await self.session.commit()
        
        return log_entry
    
    async def get_execution_history(
        self,
        workflow_id: Optional[UUID] = None,
        status: Optional[str] = None,
        triggered_by: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[WorkflowExecution]:
        """Get workflow execution history with filters."""
        
        query = select(WorkflowExecution)
        
        # Apply filters
        filters = []
        if workflow_id:
            filters.append(WorkflowExecution.workflow_id == workflow_id)
        if status:
            filters.append(WorkflowExecution.status == status)
        if triggered_by:
            filters.append(WorkflowExecution.triggered_by == triggered_by)
        if start_date:
            filters.append(WorkflowExecution.started_at >= start_date)
        if end_date:
            filters.append(WorkflowExecution.started_at <= end_date)
        
        if filters:
            query = query.where(and_(*filters))
        
        # Order by most recent first
        query = query.order_by(desc(WorkflowExecution.started_at)).limit(limit)
        
        # Include related data
        query = query.options(
            selectinload(WorkflowExecution.workflow),
            selectinload(WorkflowExecution.step_executions)
        )
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_execution_details(
        self,
        execution_id: UUID,
        include_logs: bool = False
    ) -> Dict[str, Any]:
        """Get detailed information about a workflow execution."""
        
        # Get execution with related data
        query = select(WorkflowExecution).where(
            WorkflowExecution.id == execution_id
        ).options(
            selectinload(WorkflowExecution.workflow),
            selectinload(WorkflowExecution.step_executions)
        )
        
        if include_logs:
            query = query.options(selectinload(WorkflowExecution.logs))
        
        result = await self.session.execute(query)
        execution = result.scalar_one_or_none()
        
        if not execution:
            raise NotFoundError(f"Workflow execution {execution_id} not found")
        
        # Build response
        details = {
            "id": str(execution.id),
            "workflow": {
                "id": str(execution.workflow.id),
                "name": execution.workflow.name,
                "type": execution.workflow.workflow_type
            },
            "status": execution.status,
            "started_at": execution.started_at.isoformat(),
            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
            "execution_time_seconds": execution.execution_time_seconds,
            "triggered_by": execution.triggered_by,
            "trigger_type": execution.trigger_type,
            "input_data": execution.input_data,
            "output_data": execution.output_data,
            "error_message": execution.error_message,
            "steps": []
        }
        
        # Add step information
        for step in sorted(execution.step_executions, key=lambda s: s.step_index):
            step_data = {
                "name": step.step_name,
                "index": step.step_index,
                "type": step.step_type,
                "status": step.status,
                "started_at": step.started_at.isoformat(),
                "completed_at": step.completed_at.isoformat() if step.completed_at else None,
                "execution_time_seconds": step.execution_time_seconds,
                "error_message": step.error_message
            }
            details["steps"].append(step_data)
        
        # Add logs if requested
        if include_logs:
            details["logs"] = [
                {
                    "timestamp": log.timestamp.isoformat(),
                    "level": log.level,
                    "message": log.message,
                    "component": log.component
                }
                for log in sorted(execution.logs, key=lambda l: l.timestamp)
            ]
        
        return details
    
    async def get_execution_statistics(
        self,
        workflow_id: Optional[UUID] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get execution statistics for workflows."""
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Base query
        base_query = select(WorkflowExecution).where(
            WorkflowExecution.started_at >= start_date
        )
        
        if workflow_id:
            base_query = base_query.where(WorkflowExecution.workflow_id == workflow_id)
        
        # Total executions
        total_query = select(func.count(WorkflowExecution.id)).select_from(
            base_query.subquery()
        )
        total_result = await self.session.execute(total_query)
        total_executions = total_result.scalar()
        
        # Status breakdown
        status_query = select(
            WorkflowExecution.status,
            func.count(WorkflowExecution.id)
        ).where(
            WorkflowExecution.started_at >= start_date
        )
        
        if workflow_id:
            status_query = status_query.where(WorkflowExecution.workflow_id == workflow_id)
        
        status_query = status_query.group_by(WorkflowExecution.status)
        status_result = await self.session.execute(status_query)
        status_breakdown = dict(status_result.all())
        
        # Average execution time
        time_query = select(
            func.avg(WorkflowExecution.execution_time_seconds)
        ).where(
            and_(
                WorkflowExecution.started_at >= start_date,
                WorkflowExecution.execution_time_seconds.isnot(None)
            )
        )
        
        if workflow_id:
            time_query = time_query.where(WorkflowExecution.workflow_id == workflow_id)
        
        time_result = await self.session.execute(time_query)
        avg_execution_time = time_result.scalar() or 0
        
        # Success rate
        success_rate = 0
        if total_executions > 0:
            success_count = status_breakdown.get("completed", 0)
            success_rate = (success_count / total_executions) * 100
        
        return {
            "period_days": days,
            "total_executions": total_executions,
            "status_breakdown": status_breakdown,
            "average_execution_time_seconds": round(avg_execution_time, 2),
            "success_rate_percent": round(success_rate, 2),
            "workflow_id": str(workflow_id) if workflow_id else None
        }
    
    async def cleanup_old_executions(
        self,
        days_to_keep: int = 90,
        keep_failed: bool = True
    ) -> int:
        """Clean up old execution records."""
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        # Build deletion query
        delete_query = select(WorkflowExecution).where(
            WorkflowExecution.started_at < cutoff_date
        )
        
        # Optionally keep failed executions
        if keep_failed:
            delete_query = delete_query.where(
                WorkflowExecution.status != "failed"
            )
        
        # Get executions to delete
        result = await self.session.execute(delete_query)
        executions_to_delete = result.scalars().all()
        
        # Delete executions (cascades to steps and logs)
        for execution in executions_to_delete:
            await self.session.delete(execution)
        
        await self.session.commit()
        
        deleted_count = len(executions_to_delete)
        logger.info(f"Cleaned up {deleted_count} old workflow executions")
        
        return deleted_count