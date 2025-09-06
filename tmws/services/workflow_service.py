"""
Workflow Service for TMWS
Handles workflow management and execution
"""

import logging
import json
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
from datetime import datetime

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import Workflow, Task
from ..core.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


class WorkflowService:
    """Service for managing workflows."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_workflow(
        self,
        name: str,
        description: str,
        steps: List[Dict[str, Any]],
        workflow_type: str = "sequential",
        metadata: Dict[str, Any] = None
    ) -> Workflow:
        """Create a new workflow."""
        # Validate workflow type
        valid_types = ["sequential", "parallel", "conditional", "hybrid"]
        if workflow_type not in valid_types:
            raise ValidationError(f"Invalid workflow type: {workflow_type}")
        
        # Validate steps structure
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                raise ValidationError(f"Step {i} must be a dictionary")
            if "name" not in step:
                raise ValidationError(f"Step {i} missing required field 'name'")
            if "action" not in step:
                raise ValidationError(f"Step {i} missing required field 'action'")
        
        workflow = Workflow(
            name=name,
            description=description,
            workflow_type=workflow_type,
            steps=steps,
            status="draft",
            metadata_json=metadata or {}
        )
        
        self.session.add(workflow)
        await self.session.commit()
        await self.session.refresh(workflow)
        
        logger.info(f"Created workflow {workflow.id}: {name}")
        return workflow
    
    async def get_workflow(self, workflow_id: UUID) -> Optional[Workflow]:
        """Get a workflow by ID."""
        result = await self.session.execute(
            select(Workflow).where(Workflow.id == workflow_id)
        )
        return result.scalar_one_or_none()
    
    async def update_workflow(
        self,
        workflow_id: UUID,
        updates: Dict[str, Any]
    ) -> Workflow:
        """Update an existing workflow."""
        workflow = await self.get_workflow(workflow_id)
        if not workflow:
            raise NotFoundError(f"Workflow {workflow_id} not found")
        
        # Prevent updates to active workflows
        if workflow.status == "active" and "status" not in updates:
            raise ValidationError("Cannot update an active workflow")
        
        # Update allowed fields
        allowed_fields = [
            'name', 'description', 'workflow_type', 'steps',
            'status', 'metadata_json'
        ]
        
        for key, value in updates.items():
            if key in allowed_fields:
                setattr(workflow, key, value)
        
        workflow.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(workflow)
        
        logger.info(f"Updated workflow {workflow_id}")
        return workflow
    
    async def delete_workflow(self, workflow_id: UUID) -> bool:
        """Delete a workflow."""
        workflow = await self.get_workflow(workflow_id)
        if not workflow:
            raise NotFoundError(f"Workflow {workflow_id} not found")
        
        # Prevent deletion of active workflows
        if workflow.status == "active":
            raise ValidationError("Cannot delete an active workflow")
        
        await self.session.delete(workflow)
        await self.session.commit()
        
        logger.info(f"Deleted workflow {workflow_id}")
        return True
    
    async def list_workflows(
        self,
        status: str = None,
        workflow_type: str = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Workflow]:
        """List workflows with filters."""
        stmt = select(Workflow)
        
        conditions = []
        if status:
            conditions.append(Workflow.status == status)
        if workflow_type:
            conditions.append(Workflow.workflow_type == workflow_type)
        
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        stmt = stmt.order_by(Workflow.created_at.desc())
        stmt = stmt.limit(limit).offset(offset)
        
        result = await self.session.execute(stmt)
        workflows = result.scalars().all()
        
        return workflows
    
    async def activate_workflow(self, workflow_id: UUID) -> Workflow:
        """Activate a workflow for execution."""
        workflow = await self.get_workflow(workflow_id)
        if not workflow:
            raise NotFoundError(f"Workflow {workflow_id} not found")
        
        if workflow.status == "active":
            raise ValidationError("Workflow is already active")
        
        workflow.status = "active"
        workflow.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(workflow)
        
        logger.info(f"Activated workflow {workflow_id}")
        return workflow
    
    async def deactivate_workflow(self, workflow_id: UUID) -> Workflow:
        """Deactivate a workflow."""
        workflow = await self.get_workflow(workflow_id)
        if not workflow:
            raise NotFoundError(f"Workflow {workflow_id} not found")
        
        workflow.status = "inactive"
        workflow.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(workflow)
        
        logger.info(f"Deactivated workflow {workflow_id}")
        return workflow
    
    async def execute_workflow(
        self,
        workflow_id: UUID,
        input_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute a workflow synchronously."""
        workflow = await self.get_workflow(workflow_id)
        if not workflow:
            raise NotFoundError(f"Workflow {workflow_id} not found")
        
        if workflow.status != "active":
            raise ValidationError("Workflow must be active to execute")
        
        execution_id = str(uuid4())
        execution_context = {
            "workflow_id": str(workflow_id),
            "execution_id": execution_id,
            "input": input_data or {},
            "started_at": datetime.utcnow().isoformat(),
            "steps_completed": [],
            "current_step": 0,
            "status": "running"
        }
        
        try:
            # Execute steps based on workflow type
            if workflow.workflow_type == "sequential":
                result = await self._execute_sequential_steps(
                    workflow.steps,
                    execution_context
                )
            elif workflow.workflow_type == "parallel":
                result = await self._execute_parallel_steps(
                    workflow.steps,
                    execution_context
                )
            elif workflow.workflow_type == "conditional":
                result = await self._execute_conditional_steps(
                    workflow.steps,
                    execution_context
                )
            else:
                raise ValidationError(f"Unsupported workflow type: {workflow.workflow_type}")
            
            execution_context["status"] = "completed"
            execution_context["completed_at"] = datetime.utcnow().isoformat()
            execution_context["result"] = result
            
            logger.info(f"Workflow {workflow_id} execution {execution_id} completed")
            
        except Exception as e:
            execution_context["status"] = "failed"
            execution_context["error"] = str(e)
            execution_context["failed_at"] = datetime.utcnow().isoformat()
            logger.error(f"Workflow {workflow_id} execution {execution_id} failed: {e}")
            raise
        
        return execution_context
    
    async def _execute_sequential_steps(
        self,
        steps: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute workflow steps sequentially."""
        results = {}
        
        for i, step in enumerate(steps):
            step_name = step.get("name", f"step_{i}")
            context["current_step"] = i
            
            logger.info(f"Executing step {i}: {step_name}")
            
            # Execute step action
            step_result = await self._execute_step_action(step, context, results)
            
            results[step_name] = step_result
            context["steps_completed"].append(step_name)
            
            # Check for early exit conditions
            if step.get("exit_on_failure") and step_result.get("status") == "failed":
                logger.warning(f"Step {step_name} failed, exiting workflow")
                break
        
        return results
    
    async def _execute_parallel_steps(
        self,
        steps: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute workflow steps in parallel."""
        import asyncio
        
        tasks = []
        for i, step in enumerate(steps):
            step_name = step.get("name", f"step_{i}")
            task = self._execute_step_action(step, context, {})
            tasks.append((step_name, task))
        
        # Execute all steps concurrently
        results = {}
        step_tasks = [task for _, task in tasks]
        step_names = [name for name, _ in tasks]
        
        completed_results = await asyncio.gather(*step_tasks, return_exceptions=True)
        
        for name, result in zip(step_names, completed_results):
            if isinstance(result, Exception):
                results[name] = {"status": "failed", "error": str(result)}
            else:
                results[name] = result
            context["steps_completed"].append(name)
        
        return results
    
    async def _execute_conditional_steps(
        self,
        steps: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute workflow steps with conditional logic."""
        results = {}
        
        for i, step in enumerate(steps):
            step_name = step.get("name", f"step_{i}")
            context["current_step"] = i
            
            # Check condition if present
            condition = step.get("condition")
            if condition:
                if not await self._evaluate_condition(condition, context, results):
                    logger.info(f"Skipping step {step_name} due to condition")
                    results[step_name] = {"status": "skipped"}
                    continue
            
            # Execute step
            step_result = await self._execute_step_action(step, context, results)
            results[step_name] = step_result
            context["steps_completed"].append(step_name)
        
        return results
    
    async def _execute_step_action(
        self,
        step: Dict[str, Any],
        context: Dict[str, Any],
        previous_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a single step action."""
        action = step.get("action", {})
        action_type = action.get("type", "task")
        
        if action_type == "task":
            # Create and execute a task
            from .task_service import TaskService
            task_service = TaskService(self.session)
            
            task = await task_service.create_task(
                title=step.get("name", "Workflow step"),
                description=action.get("description", ""),
                task_type=action.get("task_type", "workflow"),
                priority=action.get("priority", "medium"),
                metadata={
                    "workflow_execution_id": context["execution_id"],
                    "step_index": context["current_step"]
                }
            )
            
            # Mark task as in progress
            await task_service.update_task(
                task.id,
                {"status": "in_progress", "started_at": datetime.utcnow()}
            )
            
            # Simulate task execution (in real implementation, this would be async)
            await task_service.update_task(
                task.id,
                {
                    "status": "completed",
                    "progress": 1.0,
                    "completed_at": datetime.utcnow(),
                    "result": {"message": "Step completed successfully"}
                }
            )
            
            return {
                "status": "completed",
                "task_id": str(task.id),
                "result": task.result
            }
        
        elif action_type == "wait":
            # Wait for a specified duration
            import asyncio
            duration = action.get("duration", 1)
            await asyncio.sleep(duration)
            return {"status": "completed", "waited": duration}
        
        elif action_type == "decision":
            # Make a decision based on previous results
            decision_logic = action.get("logic", {})
            decision = await self._evaluate_decision(decision_logic, previous_results)
            return {"status": "completed", "decision": decision}
        
        else:
            return {"status": "completed", "message": f"Unknown action type: {action_type}"}
    
    async def _evaluate_condition(
        self,
        condition: Dict[str, Any],
        context: Dict[str, Any],
        results: Dict[str, Any]
    ) -> bool:
        """Evaluate a condition for conditional execution."""
        # Simple condition evaluation
        # In a real implementation, this would be more sophisticated
        condition_type = condition.get("type", "always")
        
        if condition_type == "always":
            return True
        elif condition_type == "never":
            return False
        elif condition_type == "step_completed":
            required_step = condition.get("step")
            return required_step in context.get("steps_completed", [])
        elif condition_type == "step_result":
            step_name = condition.get("step")
            expected_status = condition.get("status", "completed")
            step_result = results.get(step_name, {})
            return step_result.get("status") == expected_status
        else:
            return True
    
    async def _evaluate_decision(
        self,
        logic: Dict[str, Any],
        results: Dict[str, Any]
    ) -> str:
        """Evaluate decision logic based on previous results."""
        # Simple decision evaluation
        decision_type = logic.get("type", "default")
        
        if decision_type == "default":
            return logic.get("default_choice", "continue")
        elif decision_type == "based_on_results":
            # Check results and make decision
            for step_name, step_result in results.items():
                if step_result.get("status") == "failed":
                    return "abort"
            return "continue"
        else:
            return "continue"
    
    async def queue_workflow_execution(
        self,
        workflow_id: UUID,
        input_data: Dict[str, Any] = None
    ) -> str:
        """Queue a workflow for asynchronous execution."""
        workflow = await self.get_workflow(workflow_id)
        if not workflow:
            raise NotFoundError(f"Workflow {workflow_id} not found")
        
        execution_id = str(uuid4())
        
        # In a real implementation, this would queue to Celery or similar
        # For now, we just create a placeholder
        logger.info(f"Queued workflow {workflow_id} for execution: {execution_id}")
        
        return execution_id
    
    async def get_workflow_executions(
        self,
        workflow_id: UUID,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent workflow executions."""
        # In a real implementation, this would query an executions table
        # For now, return empty list
        return []
    
    async def count_workflows(self, status: str = None) -> int:
        """Count workflows."""
        stmt = select(func.count(Workflow.id))
        
        if status:
            stmt = stmt.where(Workflow.status == status)
        
        result = await self.session.execute(stmt)
        count = result.scalar()
        
        return count or 0
    
    async def get_workflow_stats(self) -> Dict[str, Any]:
        """Get workflow statistics."""
        # Count by status
        status_counts_stmt = select(
            Workflow.status,
            func.count(Workflow.id).label('count')
        ).group_by(Workflow.status)
        
        status_counts_result = await self.session.execute(status_counts_stmt)
        status_counts = {row.status: row.count for row in status_counts_result}
        
        # Count by type
        type_counts_stmt = select(
            Workflow.workflow_type,
            func.count(Workflow.id).label('count')
        ).group_by(Workflow.workflow_type)
        
        type_counts_result = await self.session.execute(type_counts_stmt)
        type_counts = {row.workflow_type: row.count for row in type_counts_result}
        
        return {
            "workflows_by_status": status_counts,
            "workflows_by_type": type_counts,
            "total_workflows": sum(status_counts.values()),
            "active_workflows": status_counts.get("active", 0)
        }