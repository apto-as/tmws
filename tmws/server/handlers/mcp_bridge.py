"""
MCP Bridge Handler
Translates between MCP protocol and WebSocket messages
"""

import json
from typing import Any, Dict, Optional, List
import structlog
from datetime import datetime

from .websocket_handler import WebSocketHandler
from ..daemon import TMWSDaemon

logger = structlog.get_logger()


class MCPBridge:
    """Bridges MCP protocol with WebSocket communication."""
    
    def __init__(self, daemon: TMWSDaemon, ws_handler: WebSocketHandler):
        """Initialize MCP bridge."""
        self.daemon = daemon
        self.ws_handler = ws_handler
        self.request_handlers = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resources_read,
            "prompts/list": self._handle_prompts_list,
            "prompts/get": self._handle_prompts_get,
            "ping": self._handle_ping,
        }
        self.agent_context = {}
        
    async def process_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process incoming MCP message."""
        try:
            # Extract message components
            method = message.get("method")
            params = message.get("params", {})
            request_id = message.get("id")
            
            # Handle different message types
            if method:
                # Request message
                if method in self.request_handlers:
                    handler = self.request_handlers[method]
                    result = await handler(params)
                    
                    if request_id is not None:
                        return {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "result": result
                        }
                    return None
                else:
                    # Unknown method
                    if request_id is not None:
                        return {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "error": {
                                "code": -32601,
                                "message": f"Method not found: {method}"
                            }
                        }
            
            # Handle result/error responses
            if "result" in message or "error" in message:
                # This is a response to our request
                # For now, just log it
                logger.debug("Received response", message=message)
                return None
                
        except Exception as e:
            logger.error("Error processing MCP message", error=str(e), message=message)
            if request_id := message.get("id"):
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}"
                    }
                }
        
        return None
    
    async def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialization request."""
        # Extract client info
        client_info = params.get("clientInfo", {})
        self.agent_context = {
            "agent_id": params.get("agent_id"),
            "namespace": params.get("namespace", "default"),
            "client_name": client_info.get("name", "unknown"),
            "client_version": client_info.get("version", "unknown")
        }
        
        logger.info("MCP client initialized", **self.agent_context)
        
        return {
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": "TMWS",
                "version": "2.0.0"
            },
            "capabilities": {
                "tools": {"listChanged": True},
                "resources": {"listChanged": True},
                "prompts": {"listChanged": True},
                "logging": {}
            }
        }
    
    async def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List available tools."""
        tools = [
            {
                "name": "create_memory",
                "description": "Create a new memory",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "importance": {"type": "number"},
                        "tags": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["content"]
                }
            },
            {
                "name": "search_memories",
                "description": "Search memories using semantic search",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer"},
                        "min_importance": {"type": "number"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "create_task",
                "description": "Create a new task",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "priority": {"type": "string"},
                        "assigned_persona": {"type": "string"}
                    },
                    "required": ["title"]
                }
            },
            {
                "name": "execute_workflow",
                "description": "Execute a workflow",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "workflow_id": {"type": "string"},
                        "parameters": {"type": "object"}
                    },
                    "required": ["workflow_id"]
                }
            }
        ]
        
        return {"tools": tools}
    
    async def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool call."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        try:
            # Route to appropriate service
            if tool_name == "create_memory":
                result = await self._create_memory(arguments)
            elif tool_name == "search_memories":
                result = await self._search_memories(arguments)
            elif tool_name == "create_task":
                result = await self._create_task(arguments)
            elif tool_name == "execute_workflow":
                result = await self._execute_workflow(arguments)
            else:
                raise ValueError(f"Unknown tool: {tool_name}")
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, indent=2)
                    }
                ]
            }
            
        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name}", error=str(e))
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error: {str(e)}"
                    }
                ],
                "isError": True
            }
    
    async def _create_memory(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a memory using the memory service."""
        if not self.daemon.memory_service:
            raise RuntimeError("Memory service not available")
        
        # Add agent context
        params["persona_id"] = self.agent_context.get("agent_id")
        
        # Create memory
        memory = await self.daemon.memory_service.create_memory(**params)
        
        return {
            "id": str(memory.id),
            "status": "created",
            "message": "Memory created successfully"
        }
    
    async def _search_memories(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search memories using the memory service."""
        if not self.daemon.memory_service:
            raise RuntimeError("Memory service not available")
        
        # Search memories
        memories = await self.daemon.memory_service.search_memories(**params)
        
        return [
            {
                "id": str(m.id),
                "content": m.content,
                "importance": m.importance,
                "created_at": m.created_at.isoformat() if hasattr(m.created_at, 'isoformat') else str(m.created_at)
            }
            for m in memories
        ]
    
    async def _create_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a task using the task service."""
        if not self.daemon.task_service:
            raise RuntimeError("Task service not available")
        
        # Create task
        task = await self.daemon.task_service.create_task(**params)
        
        return {
            "id": str(task.id),
            "status": "created",
            "message": "Task created successfully"
        }
    
    async def _execute_workflow(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a workflow using the workflow service."""
        if not self.daemon.workflow_service:
            raise RuntimeError("Workflow service not available")
        
        # Execute workflow
        workflow_id = params.get("workflow_id")
        parameters = params.get("parameters", {})
        
        result = await self.daemon.workflow_service.execute_workflow(
            workflow_id, 
            parameters
        )
        
        return {
            "workflow_id": workflow_id,
            "status": "started",
            "message": "Workflow execution started"
        }
    
    async def _handle_resources_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List available resources."""
        # For now, return empty list
        return {"resources": []}
    
    async def _handle_resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Read a resource."""
        # For now, return error
        raise NotImplementedError("Resource reading not yet implemented")
    
    async def _handle_prompts_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List available prompts."""
        # For now, return empty list
        return {"prompts": []}
    
    async def _handle_prompts_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get a prompt."""
        # For now, return error
        raise NotImplementedError("Prompt retrieval not yet implemented")
    
    async def _handle_ping(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ping request."""
        return {"pong": True, "timestamp": datetime.utcnow().isoformat()}