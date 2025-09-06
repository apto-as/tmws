"""
Task Management Tools for TMWS MCP Server
Handles task creation, assignment, tracking, and execution
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from fastmcp import FastMCP

from .base_tool import BaseTool


class TaskCreateRequest(BaseModel):
    """Task creation parameters."""
    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Detailed task description")
    task_type: str = Field(default="general", description="Type of task")
    priority: str = Field(default="medium", description="Task priority (low, medium, high, urgent)")
    assigned_persona_id: Optional[str] = Field(None, description="Assigned persona ID")
    dependencies: List[str] = Field(default_factory=list, description="Task dependency IDs")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    estimated_duration: Optional[int] = Field(None, description="Estimated duration in minutes")
    due_date: Optional[datetime] = Field(None, description="Task due date")


class TaskUpdateRequest(BaseModel):
    """Task update parameters."""
    task_id: str = Field(..., description="Task ID to update")
    title: Optional[str] = Field(None, description="New title")
    description: Optional[str] = Field(None, description="New description")
    status: Optional[str] = Field(None, description="New status")
    priority: Optional[str] = Field(None, description="New priority")
    progress: Optional[float] = Field(None, ge=0.0, le=1.0, description="Progress percentage")
    assigned_persona_id: Optional[str] = Field(None, description="New assigned persona")
    result: Optional[Dict[str, Any]] = Field(None, description="Task result data")
    metadata: Optional[Dict[str, Any]] = Field(None, description="New metadata")


class TaskTools(BaseTool):
    """Task management tools for TMWS MCP server."""

    async def register_tools(self, mcp: FastMCP) -> None:
        """Register task tools with FastMCP instance."""

        @mcp.tool()
        async def create_task(
            title: str,
            description: str,
            task_type: str = "general",
            priority: str = "medium",
            assigned_persona_id: Optional[str] = None,
            dependencies: List[str] = None,
            metadata: Dict[str, Any] = None,
            estimated_duration: Optional[int] = None,
            due_date: Optional[str] = None
        ) -> Dict[str, Any]:
            """
            Create a new task in the system.
            
            Tasks can be assigned to personas and linked with dependencies.
            Supports priority levels, progress tracking, and metadata.
            
            Args:
                title: Concise task title
                description: Detailed task description
                task_type: Type classification (general, technical, strategic, etc.)
                priority: Priority level (low, medium, high, urgent)
                assigned_persona_id: Optional persona assignment
                dependencies: List of dependent task IDs
                metadata: Additional structured data
                estimated_duration: Estimated completion time in minutes
                due_date: Due date in ISO format
                
            Returns:
                Dict containing task details and creation info
            """
            # Parse due_date if provided
            parsed_due_date = None
            if due_date:
                try:
                    parsed_due_date = datetime.fromisoformat(due_date)
                except ValueError:
                    raise ValueError(f"Invalid due_date format. Use ISO format: {due_date}")
            
            request = TaskCreateRequest(
                title=title,
                description=description,
                task_type=task_type,
                priority=priority,
                assigned_persona_id=assigned_persona_id,
                dependencies=dependencies or [],
                metadata=metadata or {},
                estimated_duration=estimated_duration,
                due_date=parsed_due_date
            )
            
            async def _create_task(session, services):
                task_service = services['task_service']
                
                task = await task_service.create_task(
                    title=request.title,
                    description=request.description,
                    task_type=request.task_type,
                    priority=request.priority,
                    assigned_persona_id=request.assigned_persona_id,
                    dependencies=request.dependencies,
                    metadata=request.metadata,
                    estimated_duration=request.estimated_duration,
                    due_date=request.due_date
                )
                
                return {
                    "id": str(task.id),
                    "title": task.title,
                    "description": task.description,
                    "task_type": task.task_type,
                    "status": task.status,
                    "priority": task.priority,
                    "progress": task.progress,
                    "assigned_persona_id": str(task.assigned_persona_id) if task.assigned_persona_id else None,
                    "dependencies": task.dependencies,
                    "estimated_duration": task.estimated_duration,
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                    "created_at": task.created_at.isoformat()
                }
            
            result = await self.execute_with_session(_create_task)
            return self.format_success(result, f"Task '{title}' created successfully")

        @mcp.tool()
        async def update_task_status(
            task_id: str,
            status: str,
            progress: Optional[float] = None,
            result: Optional[Dict[str, Any]] = None,
            notes: Optional[str] = None
        ) -> Dict[str, Any]:
            """
            Update task status and progress.
            
            Updates task execution state with progress tracking and result storage.
            Status transitions are validated for consistency.
            
            Args:
                task_id: ID of task to update
                status: New status (pending, in_progress, completed, failed, cancelled)
                progress: Progress percentage (0.0 to 1.0)
                result: Task execution result data
                notes: Optional status update notes
                
            Returns:
                Dict containing updated task information
            """
            request = TaskUpdateRequest(
                task_id=task_id,
                status=status,
                progress=progress,
                result=result
            )
            
            async def _update_task_status(session, services):
                task_service = services['task_service']
                
                updates = {"status": request.status}
                if request.progress is not None:
                    updates["progress"] = request.progress
                if request.result is not None:
                    updates["result"] = request.result
                if notes is not None:
                    if "metadata" not in updates:
                        # Get existing metadata to preserve it
                        existing_task = await task_service.get_task(request.task_id)
                        updates["metadata"] = existing_task.metadata_json if existing_task else {}
                    updates["metadata"]["status_notes"] = notes
                
                # Auto-set progress based on status
                if request.status == "completed" and request.progress is None:
                    updates["progress"] = 1.0
                elif request.status == "in_progress" and request.progress is None:
                    updates["progress"] = 0.1  # Default start progress
                
                task = await task_service.update_task(request.task_id, updates)
                
                return {
                    "id": str(task.id),
                    "title": task.title,
                    "status": task.status,
                    "priority": task.priority,
                    "progress": task.progress,
                    "assigned_persona_id": str(task.assigned_persona_id) if task.assigned_persona_id else None,
                    "result": task.result,
                    "updated_at": task.updated_at.isoformat(),
                    "status_change": request.status
                }
            
            result = await self.execute_with_session(_update_task_status)
            return self.format_success(result, f"Task status updated to '{status}'")

        @mcp.tool()
        async def get_task_status(task_id: str) -> Dict[str, Any]:
            """
            Get current task status and details.
            
            Retrieves complete task information including dependencies,
            progress, and execution history.
            
            Args:
                task_id: Task ID to retrieve
                
            Returns:
                Dict containing comprehensive task information
            """
            async def _get_task_status(session, services):
                task_service = services['task_service']
                task = await task_service.get_task(task_id)
                
                if not task:
                    raise ValueError(f"Task {task_id} not found")
                
                # Get dependency information
                dependency_info = []
                if task.dependencies:
                    for dep_id in task.dependencies:
                        dep_task = await task_service.get_task(dep_id)
                        if dep_task:
                            dependency_info.append({
                                "id": dep_id,
                                "title": dep_task.title,
                                "status": dep_task.status,
                                "progress": dep_task.progress
                            })
                
                # Get persona information if assigned
                persona_info = None
                if task.assigned_persona_id:
                    persona_service = services['persona_service']
                    persona = await persona_service.get_persona(str(task.assigned_persona_id))
                    if persona:
                        persona_info = {
                            "id": str(persona.id),
                            "name": persona.name,
                            "capabilities": persona.capabilities
                        }
                
                return {
                    "id": str(task.id),
                    "title": task.title,
                    "description": task.description,
                    "task_type": task.task_type,
                    "status": task.status,
                    "priority": task.priority,
                    "progress": task.progress,
                    "assigned_persona": persona_info,
                    "dependencies": dependency_info,
                    "estimated_duration": task.estimated_duration,
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                    "result": task.result,
                    "metadata": task.metadata_json,
                    "created_at": task.created_at.isoformat(),
                    "updated_at": task.updated_at.isoformat() if task.updated_at else None
                }
            
            result = await self.execute_with_session(_get_task_status)
            return self.format_success(result, "Task status retrieved")

        @mcp.tool()
        async def list_tasks(
            status: Optional[str] = None,
            priority: Optional[str] = None,
            assigned_persona_id: Optional[str] = None,
            task_type: Optional[str] = None,
            limit: int = 50,
            include_completed: bool = True
        ) -> Dict[str, Any]:
            """
            List tasks with optional filtering.
            
            Retrieves tasks matching specified criteria with comprehensive details.
            
            Args:
                status: Filter by status
                priority: Filter by priority level
                assigned_persona_id: Filter by assigned persona
                task_type: Filter by task type
                limit: Maximum number of tasks to return
                include_completed: Include completed tasks in results
                
            Returns:
                Dict containing filtered task list with summary statistics
            """
            async def _list_tasks(session, services):
                task_service = services['task_service']
                
                filters = {}
                if status:
                    filters['status'] = status
                if priority:
                    filters['priority'] = priority
                if assigned_persona_id:
                    filters['assigned_persona_id'] = assigned_persona_id
                if task_type:
                    filters['task_type'] = task_type
                if not include_completed:
                    filters['exclude_status'] = 'completed'
                
                tasks = await task_service.list_tasks(filters=filters, limit=limit)
                
                # Generate summary statistics
                status_counts = {}
                priority_counts = {}
                type_counts = {}
                
                for task in tasks:
                    status_counts[task.status] = status_counts.get(task.status, 0) + 1
                    priority_counts[task.priority] = priority_counts.get(task.priority, 0) + 1
                    type_counts[task.task_type] = type_counts.get(task.task_type, 0) + 1
                
                return {
                    "count": len(tasks),
                    "filters_applied": {
                        "status": status,
                        "priority": priority,
                        "assigned_persona_id": assigned_persona_id,
                        "task_type": task_type,
                        "include_completed": include_completed
                    },
                    "summary": {
                        "by_status": status_counts,
                        "by_priority": priority_counts,
                        "by_type": type_counts
                    },
                    "tasks": [
                        {
                            "id": str(t.id),
                            "title": t.title,
                            "task_type": t.task_type,
                            "status": t.status,
                            "priority": t.priority,
                            "progress": t.progress,
                            "assigned_persona_id": str(t.assigned_persona_id) if t.assigned_persona_id else None,
                            "due_date": t.due_date.isoformat() if t.due_date else None,
                            "created_at": t.created_at.isoformat()
                        }
                        for t in tasks
                    ]
                }
            
            result = await self.execute_with_session(_list_tasks)
            return self.format_success(result, f"Retrieved {result.get('count', 0)} tasks")

        @mcp.tool()
        async def assign_task(
            task_id: str,
            persona_id: str,
            notes: Optional[str] = None
        ) -> Dict[str, Any]:
            """
            Assign a task to a persona.
            
            Updates task assignment and notifies the assigned persona.
            Validates persona capabilities against task requirements.
            
            Args:
                task_id: ID of task to assign
                persona_id: ID of persona to assign task to
                notes: Optional assignment notes
                
            Returns:
                Dict containing assignment confirmation and details
            """
            async def _assign_task(session, services):
                task_service = services['task_service']
                persona_service = services['persona_service']
                
                # Validate persona exists and is active
                persona = await persona_service.get_persona(persona_id)
                if not persona:
                    raise ValueError(f"Persona {persona_id} not found")
                if not persona.is_active:
                    raise ValueError(f"Persona {persona.name} is not active")
                
                # Update task assignment
                updates = {
                    "assigned_persona_id": persona_id,
                    "status": "assigned"
                }
                
                if notes:
                    task = await task_service.get_task(task_id)
                    metadata = task.metadata_json if task else {}
                    metadata["assignment_notes"] = notes
                    updates["metadata"] = metadata
                
                updated_task = await task_service.update_task(task_id, updates)
                
                return {
                    "task_id": str(updated_task.id),
                    "task_title": updated_task.title,
                    "assigned_persona": {
                        "id": str(persona.id),
                        "name": persona.name,
                        "capabilities": persona.capabilities
                    },
                    "assignment_date": datetime.utcnow().isoformat(),
                    "assignment_notes": notes,
                    "previous_status": task.status if task else "unknown",
                    "new_status": updated_task.status
                }
            
            result = await self.execute_with_session(_assign_task)
            return self.format_success(result, f"Task assigned to persona successfully")

        @mcp.tool()
        async def complete_task(
            task_id: str,
            result: Dict[str, Any],
            completion_notes: Optional[str] = None
        ) -> Dict[str, Any]:
            """
            Mark a task as completed with results.
            
            Finalizes task execution with result data and completion metrics.
            Updates dependent tasks if applicable.
            
            Args:
                task_id: ID of task to complete
                result: Task completion result data
                completion_notes: Optional completion notes
                
            Returns:
                Dict containing completion confirmation and metrics
            """
            async def _complete_task(session, services):
                task_service = services['task_service']
                
                # Get current task to calculate duration
                task = await task_service.get_task(task_id)
                if not task:
                    raise ValueError(f"Task {task_id} not found")
                
                completion_time = datetime.utcnow()
                duration_minutes = None
                if task.created_at:
                    duration_delta = completion_time - task.created_at
                    duration_minutes = int(duration_delta.total_seconds() / 60)
                
                # Prepare completion metadata
                completion_metadata = task.metadata_json or {}
                completion_metadata.update({
                    "completed_at": completion_time.isoformat(),
                    "actual_duration_minutes": duration_minutes,
                    "completion_notes": completion_notes
                })
                
                # Update task to completed status
                updates = {
                    "status": "completed",
                    "progress": 1.0,
                    "result": result,
                    "metadata": completion_metadata
                }
                
                completed_task = await task_service.update_task(task_id, updates)
                
                # Check for dependent tasks
                dependent_tasks = await task_service.find_dependent_tasks(task_id)
                dependent_task_info = []
                for dep_task in dependent_tasks:
                    dependent_task_info.append({
                        "id": str(dep_task.id),
                        "title": dep_task.title,
                        "status": dep_task.status
                    })
                
                return {
                    "task_id": str(completed_task.id),
                    "task_title": completed_task.title,
                    "completion_time": completion_time.isoformat(),
                    "actual_duration_minutes": duration_minutes,
                    "estimated_duration_minutes": completed_task.estimated_duration,
                    "duration_variance": (
                        duration_minutes - completed_task.estimated_duration 
                        if duration_minutes and completed_task.estimated_duration 
                        else None
                    ),
                    "result": result,
                    "completion_notes": completion_notes,
                    "dependent_tasks": dependent_task_info
                }
            
            result = await self.execute_with_session(_complete_task)
            return self.format_success(result, "Task completed successfully")

        @mcp.tool()
        async def get_task_analytics() -> Dict[str, Any]:
            """
            Get task analytics and performance metrics.
            
            Provides insights into task completion rates, duration accuracy,
            persona performance, and system efficiency.
            
            Returns:
                Dict containing comprehensive task analytics
            """
            async def _get_task_analytics(session, services):
                task_service = services['task_service']
                
                # Get overall statistics
                total_tasks = await task_service.count_all_tasks()
                completed_tasks = await task_service.count_tasks_by_status("completed")
                active_tasks = await task_service.count_active_tasks()
                
                # Calculate completion rate
                completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
                
                # Get recent task metrics
                recent_tasks = await task_service.get_recent_completed_tasks(limit=100)
                
                duration_accuracy = []
                persona_performance = {}
                
                for task in recent_tasks:
                    # Duration accuracy analysis
                    if task.estimated_duration and task.metadata_json:
                        actual = task.metadata_json.get("actual_duration_minutes")
                        if actual:
                            accuracy = abs(actual - task.estimated_duration) / task.estimated_duration
                            duration_accuracy.append(accuracy)
                    
                    # Persona performance tracking
                    if task.assigned_persona_id:
                        persona_id = str(task.assigned_persona_id)
                        if persona_id not in persona_performance:
                            persona_performance[persona_id] = {
                                "completed_tasks": 0,
                                "total_duration": 0
                            }
                        persona_performance[persona_id]["completed_tasks"] += 1
                        if task.metadata_json:
                            actual_duration = task.metadata_json.get("actual_duration_minutes", 0)
                            persona_performance[persona_id]["total_duration"] += actual_duration
                
                avg_duration_accuracy = (
                    sum(duration_accuracy) / len(duration_accuracy) 
                    if duration_accuracy else 0
                )
                
                return {
                    "overview": {
                        "total_tasks": total_tasks,
                        "completed_tasks": completed_tasks,
                        "active_tasks": active_tasks,
                        "completion_rate_percent": round(completion_rate, 2)
                    },
                    "performance_metrics": {
                        "avg_duration_accuracy_percent": round((1 - avg_duration_accuracy) * 100, 2),
                        "tasks_analyzed": len(recent_tasks)
                    },
                    "persona_performance": {
                        persona_id: {
                            "completed_tasks": data["completed_tasks"],
                            "avg_duration_minutes": (
                                data["total_duration"] / data["completed_tasks"]
                                if data["completed_tasks"] > 0 else 0
                            )
                        }
                        for persona_id, data in persona_performance.items()
                    },
                    "generated_at": datetime.utcnow().isoformat()
                }
            
            result = await self.execute_with_session(_get_task_analytics)
            return self.format_success(result, "Task analytics generated")