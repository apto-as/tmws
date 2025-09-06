"""
Workflow Management Tools for TMWS MCP Server
Handles workflow creation, execution, and orchestration
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from fastmcp import FastMCP

from .base_tool import BaseTool


class WorkflowCreateRequest(BaseModel):
    """Workflow creation parameters."""
    name: str = Field(..., description="Workflow name")
    description: str = Field(..., description="Workflow description")
    steps: List[Dict[str, Any]] = Field(..., description="Workflow steps")
    workflow_type: str = Field(default="sequential", description="Workflow execution type")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    timeout_minutes: Optional[int] = Field(None, description="Workflow timeout in minutes")


class WorkflowExecutionRequest(BaseModel):
    """Workflow execution parameters."""
    workflow_id: str = Field(..., description="Workflow ID to execute")
    input_data: Dict[str, Any] = Field(default_factory=dict, description="Input data")
    async_execution: bool = Field(default=False, description="Execute asynchronously")
    execution_context: Optional[Dict[str, Any]] = Field(None, description="Execution context")


class WorkflowTools(BaseTool):
    """Workflow management tools for TMWS MCP server."""

    async def register_tools(self, mcp: FastMCP) -> None:
        """Register workflow tools with FastMCP instance."""

        @mcp.tool()
        async def create_workflow(
            name: str,
            description: str,
            steps: List[Dict[str, Any]],
            workflow_type: str = "sequential",
            metadata: Dict[str, Any] = None,
            timeout_minutes: Optional[int] = None
        ) -> Dict[str, Any]:
            """
            Create a new workflow with multiple steps.
            
            Workflows define sequences of operations that can be executed
            automatically with dependency management and error handling.
            
            Args:
                name: Workflow name
                description: Detailed workflow description
                steps: List of workflow steps with configurations
                workflow_type: Execution type (sequential, parallel, conditional)
                metadata: Additional workflow metadata
                timeout_minutes: Maximum execution time
                
            Returns:
                Dict containing workflow details and creation info
            """
            request = WorkflowCreateRequest(
                name=name,
                description=description,
                steps=steps,
                workflow_type=workflow_type,
                metadata=metadata or {},
                timeout_minutes=timeout_minutes
            )
            
            async def _create_workflow(session, services):
                workflow_service = services['workflow_service']
                
                # Validate workflow steps
                validated_steps = []
                for i, step in enumerate(request.steps):
                    if not isinstance(step, dict):
                        raise ValueError(f"Step {i} must be a dictionary")
                    if "action" not in step:
                        raise ValueError(f"Step {i} missing required 'action' field")
                    
                    validated_step = {
                        "step_id": step.get("step_id", f"step_{i}"),
                        "action": step["action"],
                        "parameters": step.get("parameters", {}),
                        "condition": step.get("condition"),
                        "on_error": step.get("on_error", "halt"),
                        "timeout_seconds": step.get("timeout_seconds", 300),
                        "retry_attempts": step.get("retry_attempts", 0)
                    }
                    validated_steps.append(validated_step)
                
                workflow = await workflow_service.create_workflow(
                    name=request.name,
                    description=request.description,
                    steps=validated_steps,
                    workflow_type=request.workflow_type,
                    metadata=request.metadata,
                    timeout_minutes=request.timeout_minutes
                )
                
                return {
                    "id": str(workflow.id),
                    "name": workflow.name,
                    "description": workflow.description,
                    "workflow_type": workflow.workflow_type,
                    "status": workflow.status,
                    "step_count": len(validated_steps),
                    "timeout_minutes": workflow.timeout_minutes,
                    "created_at": workflow.created_at.isoformat()
                }
            
            result = await self.execute_with_session(_create_workflow)
            return self.format_success(result, f"Workflow '{name}' created successfully")

        @mcp.tool()
        async def execute_workflow(
            workflow_id: str,
            input_data: Dict[str, Any] = None,
            async_execution: bool = False,
            execution_context: Dict[str, Any] = None
        ) -> Dict[str, Any]:
            """
            Execute a workflow with optional input data.
            
            Runs workflow steps according to the defined execution type.
            Supports both synchronous and asynchronous execution modes.
            
            Args:
                workflow_id: ID of workflow to execute
                input_data: Input data for workflow execution
                async_execution: Run workflow asynchronously
                execution_context: Additional execution context
                
            Returns:
                Dict containing execution results or queue information
            """
            request = WorkflowExecutionRequest(
                workflow_id=workflow_id,
                input_data=input_data or {},
                async_execution=async_execution,
                execution_context=execution_context
            )
            
            async def _execute_workflow(session, services):
                workflow_service = services['workflow_service']
                
                if request.async_execution:
                    # Queue for background execution
                    execution_id = await workflow_service.queue_workflow_execution(
                        workflow_id=request.workflow_id,
                        input_data=request.input_data,
                        execution_context=request.execution_context or {}
                    )
                    
                    return {
                        "workflow_id": request.workflow_id,
                        "execution_id": execution_id,
                        "status": "queued",
                        "execution_mode": "asynchronous",
                        "queued_at": datetime.utcnow().isoformat()
                    }
                else:
                    # Execute synchronously
                    execution_start = datetime.utcnow()
                    result = await workflow_service.execute_workflow(
                        workflow_id=request.workflow_id,
                        input_data=request.input_data,
                        execution_context=request.execution_context or {}
                    )
                    execution_end = datetime.utcnow()
                    
                    duration = (execution_end - execution_start).total_seconds()
                    
                    return {
                        "workflow_id": request.workflow_id,
                        "execution_mode": "synchronous",
                        "status": result.get("status", "completed"),
                        "result": result,
                        "execution_time_seconds": duration,
                        "started_at": execution_start.isoformat(),
                        "completed_at": execution_end.isoformat()
                    }
            
            result = await self.execute_with_session(_execute_workflow)
            return self.format_success(result, "Workflow execution initiated")

        @mcp.tool()
        async def get_workflow_status(workflow_id: str) -> Dict[str, Any]:
            """
            Get workflow status and execution history.
            
            Provides detailed workflow information including step definitions,
            execution history, and current status.
            
            Args:
                workflow_id: Workflow ID to retrieve
                
            Returns:
                Dict containing comprehensive workflow information
            """
            async def _get_workflow_status(session, services):
                workflow_service = services['workflow_service']
                workflow = await workflow_service.get_workflow(workflow_id)
                
                if not workflow:
                    raise ValueError(f"Workflow {workflow_id} not found")
                
                # Get execution history
                executions = await workflow_service.get_workflow_executions(workflow_id, limit=10)
                
                execution_history = []
                for execution in executions:
                    exec_data = {
                        "execution_id": str(execution.id),
                        "status": execution.status,
                        "started_at": execution.started_at.isoformat() if execution.started_at else None,
                        "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                        "duration_seconds": None
                    }
                    
                    if execution.started_at and execution.completed_at:
                        duration = execution.completed_at - execution.started_at
                        exec_data["duration_seconds"] = duration.total_seconds()
                    
                    if hasattr(execution, 'result') and execution.result:
                        exec_data["result_summary"] = {
                            "steps_executed": execution.result.get("steps_executed", 0),
                            "steps_failed": execution.result.get("steps_failed", 0),
                            "success": execution.result.get("success", False)
                        }
                    
                    execution_history.append(exec_data)
                
                return {
                    "id": str(workflow.id),
                    "name": workflow.name,
                    "description": workflow.description,
                    "workflow_type": workflow.workflow_type,
                    "status": workflow.status,
                    "steps": workflow.steps,
                    "timeout_minutes": workflow.timeout_minutes,
                    "metadata": workflow.metadata_json,
                    "execution_history": execution_history,
                    "statistics": {
                        "total_executions": len(executions),
                        "successful_executions": len([e for e in executions if e.status == "completed"]),
                        "failed_executions": len([e for e in executions if e.status == "failed"])
                    },
                    "created_at": workflow.created_at.isoformat(),
                    "updated_at": workflow.updated_at.isoformat() if workflow.updated_at else None
                }
            
            result = await self.execute_with_session(_get_workflow_status)
            return self.format_success(result, "Workflow status retrieved")

        @mcp.tool()
        async def list_workflows(
            status: Optional[str] = None,
            workflow_type: Optional[str] = None,
            limit: int = 50
        ) -> Dict[str, Any]:
            """
            List workflows with optional filtering.
            
            Retrieves workflows matching specified criteria with summary information.
            
            Args:
                status: Filter by workflow status
                workflow_type: Filter by workflow type
                limit: Maximum number of workflows to return
                
            Returns:
                Dict containing filtered workflow list
            """
            async def _list_workflows(session, services):
                workflow_service = services['workflow_service']
                
                filters = {}
                if status:
                    filters['status'] = status
                if workflow_type:
                    filters['workflow_type'] = workflow_type
                
                workflows = await workflow_service.list_workflows(filters=filters, limit=limit)
                
                workflow_list = []
                for workflow in workflows:
                    # Get execution summary
                    recent_executions = await workflow_service.get_workflow_executions(
                        str(workflow.id), limit=3
                    )
                    
                    workflow_data = {
                        "id": str(workflow.id),
                        "name": workflow.name,
                        "description": workflow.description,
                        "workflow_type": workflow.workflow_type,
                        "status": workflow.status,
                        "step_count": len(workflow.steps),
                        "timeout_minutes": workflow.timeout_minutes,
                        "recent_executions": [
                            {
                                "execution_id": str(e.id),
                                "status": e.status,
                                "started_at": e.started_at.isoformat() if e.started_at else None
                            }
                            for e in recent_executions
                        ],
                        "created_at": workflow.created_at.isoformat()
                    }
                    workflow_list.append(workflow_data)
                
                return {
                    "count": len(workflow_list),
                    "filters": {
                        "status": status,
                        "workflow_type": workflow_type
                    },
                    "workflows": workflow_list
                }
            
            result = await self.execute_with_session(_list_workflows)
            return self.format_success(result, f"Retrieved {result.get('count', 0)} workflows")

        @mcp.tool()
        async def update_workflow(
            workflow_id: str,
            name: Optional[str] = None,
            description: Optional[str] = None,
            steps: Optional[List[Dict[str, Any]]] = None,
            status: Optional[str] = None,
            metadata: Optional[Dict[str, Any]] = None,
            timeout_minutes: Optional[int] = None
        ) -> Dict[str, Any]:
            """
            Update an existing workflow.
            
            Allows modification of workflow configuration while preserving
            execution history and existing data.
            
            Args:
                workflow_id: ID of workflow to update
                name: New workflow name
                description: New description
                steps: New workflow steps
                status: New workflow status
                metadata: New metadata
                timeout_minutes: New timeout value
                
            Returns:
                Dict containing updated workflow information
            """
            async def _update_workflow(session, services):
                workflow_service = services['workflow_service']
                
                updates = {}
                if name is not None:
                    updates['name'] = name
                if description is not None:
                    updates['description'] = description
                if status is not None:
                    updates['status'] = status
                if metadata is not None:
                    updates['metadata'] = metadata
                if timeout_minutes is not None:
                    updates['timeout_minutes'] = timeout_minutes
                
                if steps is not None:
                    # Validate and format steps
                    validated_steps = []
                    for i, step in enumerate(steps):
                        if not isinstance(step, dict):
                            raise ValueError(f"Step {i} must be a dictionary")
                        if "action" not in step:
                            raise ValueError(f"Step {i} missing required 'action' field")
                        
                        validated_step = {
                            "step_id": step.get("step_id", f"step_{i}"),
                            "action": step["action"],
                            "parameters": step.get("parameters", {}),
                            "condition": step.get("condition"),
                            "on_error": step.get("on_error", "halt"),
                            "timeout_seconds": step.get("timeout_seconds", 300),
                            "retry_attempts": step.get("retry_attempts", 0)
                        }
                        validated_steps.append(validated_step)
                    
                    updates['steps'] = validated_steps
                
                workflow = await workflow_service.update_workflow(workflow_id, updates)
                
                return {
                    "id": str(workflow.id),
                    "name": workflow.name,
                    "description": workflow.description,
                    "workflow_type": workflow.workflow_type,
                    "status": workflow.status,
                    "step_count": len(workflow.steps),
                    "timeout_minutes": workflow.timeout_minutes,
                    "updated_at": workflow.updated_at.isoformat()
                }
            
            result = await self.execute_with_session(_update_workflow)
            return self.format_success(result, "Workflow updated successfully")

        @mcp.tool()
        async def cancel_workflow_execution(execution_id: str) -> Dict[str, Any]:
            """
            Cancel a running workflow execution.
            
            Attempts to gracefully stop workflow execution and cleanup resources.
            
            Args:
                execution_id: ID of execution to cancel
                
            Returns:
                Dict containing cancellation confirmation
            """
            async def _cancel_execution(session, services):
                workflow_service = services['workflow_service']
                
                result = await workflow_service.cancel_workflow_execution(execution_id)
                
                return {
                    "execution_id": execution_id,
                    "cancellation_requested": True,
                    "cancelled_at": datetime.utcnow().isoformat(),
                    "cancellation_result": result
                }
            
            result = await self.execute_with_session(_cancel_execution)
            return self.format_success(result, "Workflow execution cancellation requested")

        @mcp.tool()
        async def get_workflow_execution_logs(
            execution_id: str,
            limit: int = 100
        ) -> Dict[str, Any]:
            """
            Get detailed execution logs for a workflow run.
            
            Provides step-by-step execution details, timing, and error information.
            
            Args:
                execution_id: Execution ID to retrieve logs for
                limit: Maximum number of log entries to return
                
            Returns:
                Dict containing detailed execution logs
            """
            async def _get_execution_logs(session, services):
                workflow_service = services['workflow_service']
                
                execution = await workflow_service.get_workflow_execution(execution_id)
                if not execution:
                    raise ValueError(f"Workflow execution {execution_id} not found")
                
                logs = await workflow_service.get_execution_logs(execution_id, limit=limit)
                
                return {
                    "execution_id": execution_id,
                    "workflow_id": str(execution.workflow_id),
                    "status": execution.status,
                    "started_at": execution.started_at.isoformat() if execution.started_at else None,
                    "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                    "log_count": len(logs),
                    "logs": [
                        {
                            "timestamp": log.timestamp.isoformat(),
                            "level": log.level,
                            "step_id": log.step_id,
                            "message": log.message,
                            "details": log.details
                        }
                        for log in logs
                    ]
                }
            
            result = await self.execute_with_session(_get_execution_logs)
            return self.format_success(result, "Execution logs retrieved")

        @mcp.tool()
        async def get_workflow_analytics() -> Dict[str, Any]:
            """
            Get workflow analytics and performance metrics.
            
            Provides insights into workflow execution patterns, success rates,
            and performance characteristics.
            
            Returns:
                Dict containing comprehensive workflow analytics
            """
            async def _get_workflow_analytics(session, services):
                workflow_service = services['workflow_service']
                
                # Get overall statistics
                total_workflows = await workflow_service.count_workflows()
                active_workflows = await workflow_service.count_active_workflows()
                
                # Get execution statistics
                execution_stats = await workflow_service.get_execution_statistics()
                
                # Get workflow type distribution
                workflow_types = await workflow_service.get_workflow_type_distribution()
                
                # Calculate success rates
                total_executions = execution_stats.get("total_executions", 0)
                successful_executions = execution_stats.get("successful_executions", 0)
                success_rate = (
                    successful_executions / total_executions * 100 
                    if total_executions > 0 else 0
                )
                
                # Get average execution times
                avg_execution_time = execution_stats.get("avg_execution_time_seconds", 0)
                
                return {
                    "overview": {
                        "total_workflows": total_workflows,
                        "active_workflows": active_workflows,
                        "total_executions": total_executions,
                        "successful_executions": successful_executions,
                        "failed_executions": execution_stats.get("failed_executions", 0),
                        "success_rate_percent": round(success_rate, 2)
                    },
                    "performance": {
                        "avg_execution_time_seconds": round(avg_execution_time, 2),
                        "fastest_execution_seconds": execution_stats.get("min_execution_time_seconds", 0),
                        "slowest_execution_seconds": execution_stats.get("max_execution_time_seconds", 0)
                    },
                    "workflow_types": workflow_types,
                    "generated_at": datetime.utcnow().isoformat()
                }
            
            result = await self.execute_with_session(_get_workflow_analytics)
            return self.format_success(result, "Workflow analytics generated")