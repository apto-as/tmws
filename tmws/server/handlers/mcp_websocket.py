"""
MCP WebSocket Handler
Handles MCP protocol directly over WebSocket
"""

import json
import asyncio
from typing import Dict, Any, Optional
from fastapi import WebSocket
import structlog

from ..daemon import TMWSDaemon
from ...mcp_server import get_mcp_tools, AgentContext

logger = structlog.get_logger()


class MCPWebSocketHandler:
    """Handles MCP protocol over WebSocket."""
    
    def __init__(self, websocket: WebSocket, daemon: TMWSDaemon, client_id: str):
        """Initialize MCP WebSocket handler."""
        self.websocket = websocket
        self.daemon = daemon
        self.client_id = client_id
        self.agent_context: Optional[AgentContext] = None
        self.initialized = False
        
    async def run(self):
        """Run the MCP protocol handler."""
        try:
            while True:
                # Receive message
                data = await self.websocket.receive_text()
                message = json.loads(data)
                
                # Process MCP message
                response = await self.process_mcp_message(message)
                
                # Send response if any
                if response:
                    await self.websocket.send_text(json.dumps(response))
                    
        except Exception as e:
            logger.error("MCP WebSocket error", 
                        client_id=self.client_id,
                        error=str(e))
            raise
    
    async def process_mcp_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process an MCP protocol message."""
        jsonrpc = message.get("jsonrpc", "2.0")
        method = message.get("method")
        params = message.get("params", {})
        msg_id = message.get("id")
        
        # Ensure we have an ID for requests
        if method and msg_id is None:
            return {
                "jsonrpc": jsonrpc,
                "error": {
                    "code": -32600,
                    "message": "Invalid request: missing id"
                }
            }
        
        try:
            # Route to appropriate handler
            if method == "initialize":
                result = await self.handle_initialize(params)
            elif method == "initialized":
                # Client confirmation of initialization
                self.initialized = True
                logger.info("MCP client fully initialized", client_id=self.client_id)
                return None  # No response needed
            elif method == "tools/list":
                result = await self.handle_tools_list(params)
            elif method == "tools/call":
                result = await self.handle_tools_call(params)
            elif method == "resources/list":
                result = await self.handle_resources_list(params)
            elif method == "resources/read":
                result = await self.handle_resources_read(params)
            elif method == "prompts/list":
                result = await self.handle_prompts_list(params)
            elif method == "prompts/get":
                result = await self.handle_prompts_get(params)
            elif method == "completion/complete":
                result = await self.handle_completion(params)
            elif method == "logging/setLevel":
                result = await self.handle_logging_set_level(params)
            elif method == "ping":
                result = {}  # Simple pong
            else:
                # Unknown method
                return {
                    "jsonrpc": jsonrpc,
                    "id": msg_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
            
            # Return successful response
            return {
                "jsonrpc": jsonrpc,
                "id": msg_id,
                "result": result
            }
            
        except Exception as e:
            logger.error(f"Error handling MCP method: {method}", 
                        error=str(e),
                        client_id=self.client_id)
            return {
                "jsonrpc": jsonrpc,
                "id": msg_id,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
    
    async def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP initialization."""
        # Extract client info
        client_info = params.get("clientInfo", {})
        protocol_version = params.get("protocolVersion", "2024-11-05")
        
        # Create agent context
        self.agent_context = AgentContext(
            agent_id=params.get("agent_id"),
            namespace=params.get("namespace", "default"),
            capabilities=params.get("capabilities", [])
        )
        
        # Update daemon client info
        await self.daemon.register_client(self.client_id, {
            "type": "mcp",
            "agent_id": self.agent_context.agent_id,
            "namespace": self.agent_context.namespace,
            "client_info": client_info,
            "protocol_version": protocol_version
        })
        
        logger.info("MCP initialization complete",
                   client_id=self.client_id,
                   agent_id=self.agent_context.agent_id)
        
        return {
            "protocolVersion": protocol_version,
            "serverInfo": {
                "name": "TMWS",
                "version": "2.0.0"
            },
            "capabilities": {
                "tools": {"listChanged": True},
                "resources": {"listChanged": True},
                "prompts": {"listChanged": True},
                "logging": {},
                "completion": {"models": []}
            }
        }
    
    async def handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List available MCP tools."""
        # Get tools from MCP server
        tools = get_mcp_tools()
        
        # Convert to MCP format
        tool_list = []
        for tool in tools:
            tool_list.append({
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.parameters
            })
        
        return {"tools": tool_list}
    
    async def handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an MCP tool."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        try:
            # Execute tool through daemon services
            if tool_name == "create_memory":
                if self.daemon.memory_service:
                    memory = await self.daemon.memory_service.create_memory(**arguments)
                    result = {
                        "id": str(memory.id),
                        "status": "created"
                    }
                else:
                    raise RuntimeError("Memory service not available")
                    
            elif tool_name == "search_memories":
                if self.daemon.memory_service:
                    memories = await self.daemon.memory_service.search_memories(**arguments)
                    result = [
                        {
                            "id": str(m.id),
                            "content": m.content,
                            "importance": m.importance
                        }
                        for m in memories
                    ]
                else:
                    raise RuntimeError("Memory service not available")
                    
            elif tool_name == "create_task":
                if self.daemon.task_service:
                    task = await self.daemon.task_service.create_task(**arguments)
                    result = {
                        "id": str(task.id),
                        "status": task.status
                    }
                else:
                    raise RuntimeError("Task service not available")
                    
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
            logger.error(f"Tool execution failed: {tool_name}",
                        error=str(e),
                        client_id=self.client_id)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error: {str(e)}"
                    }
                ],
                "isError": True
            }
    
    async def handle_resources_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List available resources."""
        # TODO: Implement resource listing
        return {"resources": []}
    
    async def handle_resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Read a resource."""
        # TODO: Implement resource reading
        raise NotImplementedError("Resource reading not yet implemented")
    
    async def handle_prompts_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List available prompts."""
        # TODO: Implement prompt listing
        return {"prompts": []}
    
    async def handle_prompts_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get a prompt."""
        # TODO: Implement prompt retrieval
        raise NotImplementedError("Prompt retrieval not yet implemented")
    
    async def handle_completion(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle completion request."""
        # TODO: Implement completion if needed
        raise NotImplementedError("Completion not yet implemented")
    
    async def handle_logging_set_level(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set logging level."""
        level = params.get("level", "info")
        logger.info(f"Setting log level to {level}", client_id=self.client_id)
        # TODO: Actually set the logging level
        return {}