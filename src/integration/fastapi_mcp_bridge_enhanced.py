"""
Enhanced FastAPI-MCP Integration Bridge for TMWS
Dynamic MCP tool invocation with complete tool registry access
"""

import asyncio
import logging
import inspect
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..mcp_server_v2 import TMWSFastMCPServer, create_server
from ..tools import (
    MemoryTools, PersonaTools, TaskTools,
    WorkflowTools, SystemTools, LearningTools
)

logger = logging.getLogger(__name__)


class DynamicMCPBridge:
    """
    Enhanced bridge with dynamic tool discovery and invocation.
    """
    
    def __init__(self, mcp_server: TMWSFastMCPServer):
        self.mcp_server = mcp_server
        self.tool_registry: Dict[str, Callable] = {}
        self.tool_metadata: Dict[str, Dict[str, Any]] = {}
        
        # Register all tool modules
        self._register_tool_modules()
    
    def _register_tool_modules(self) -> None:
        """Dynamically register all MCP tool modules."""
        
        tool_modules = [
            ("memory", MemoryTools),
            ("persona", PersonaTools),
            ("task", TaskTools),
            ("workflow", WorkflowTools),
            ("system", SystemTools),
            ("learning", LearningTools)
        ]
        
        for module_name, module_class in tool_modules:
            try:
                # Instantiate tool module with database session
                # Note: In production, this would use proper dependency injection
                module_instance = module_class(self.mcp_server.db_manager)
                
                # Discover all tool methods in the module
                for method_name in dir(module_instance):
                    if not method_name.startswith('_'):  # Skip private methods
                        method = getattr(module_instance, method_name, None)
                        if callable(method) and not method_name.startswith('__'):
                            # Register tool
                            tool_full_name = f"{module_name}_{method_name}"
                            self.tool_registry[tool_full_name] = method
                            
                            # Extract metadata
                            self.tool_metadata[tool_full_name] = {
                                "module": module_name,
                                "method": method_name,
                                "description": method.__doc__ or "No description available",
                                "signature": str(inspect.signature(method)),
                                "async": inspect.iscoroutinefunction(method)
                            }
                            
                logger.info(f"Registered {len(self.tool_metadata)} tools from {module_name} module")
                
            except Exception as e:
                logger.error(f"Failed to register {module_name} module: {e}")
    
    async def invoke_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Dynamically invoke any registered MCP tool.
        
        Args:
            tool_name: Full tool name (e.g., "memory_create_memory")
            parameters: Tool parameters
            
        Returns:
            Tool execution result
        """
        
        # Check if tool exists
        if tool_name not in self.tool_registry:
            # Try to find partial match
            matches = [t for t in self.tool_registry if tool_name in t]
            if len(matches) == 1:
                tool_name = matches[0]
            elif len(matches) > 1:
                return {
                    "success": False,
                    "error": f"Ambiguous tool name. Matches: {matches}",
                    "available_tools": list(self.tool_registry.keys())
                }
            else:
                return {
                    "success": False,
                    "error": f"Tool '{tool_name}' not found",
                    "available_tools": list(self.tool_registry.keys())
                }
        
        # Get tool function and metadata
        tool_func = self.tool_registry[tool_name]
        tool_meta = self.tool_metadata[tool_name]
        
        try:
            # Execute tool (handle both sync and async)
            if tool_meta["async"]:
                result = await tool_func(**parameters)
            else:
                # Run sync function in thread pool
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, tool_func, **parameters)
            
            return {
                "success": True,
                "tool_name": tool_name,
                "result": result,
                "metadata": tool_meta
            }
            
        except TypeError as e:
            # Parameter mismatch
            return {
                "success": False,
                "error": f"Parameter error: {str(e)}",
                "expected_signature": tool_meta["signature"],
                "provided_parameters": list(parameters.keys())
            }
        except Exception as e:
            # Tool execution error
            logger.error(f"Tool execution failed for {tool_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "tool_name": tool_name,
                "metadata": tool_meta
            }
    
    def get_tool_info(self, tool_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get information about available tools.
        
        Args:
            tool_name: Specific tool name or None for all tools
            
        Returns:
            Tool information
        """
        
        if tool_name:
            if tool_name in self.tool_metadata:
                return {
                    "tool_name": tool_name,
                    "metadata": self.tool_metadata[tool_name],
                    "available": True
                }
            else:
                return {
                    "tool_name": tool_name,
                    "available": False,
                    "error": "Tool not found"
                }
        else:
            # Return all tools grouped by module
            tools_by_module = {}
            for tool_full_name, metadata in self.tool_metadata.items():
                module = metadata["module"]
                if module not in tools_by_module:
                    tools_by_module[module] = []
                
                tools_by_module[module].append({
                    "name": tool_full_name,
                    "method": metadata["method"],
                    "description": metadata["description"].split('\n')[0] if metadata["description"] else "No description",
                    "async": metadata["async"]
                })
            
            return {
                "total_tools": len(self.tool_metadata),
                "modules": list(tools_by_module.keys()),
                "tools_by_module": tools_by_module
            }
    
    async def batch_invoke(
        self,
        tool_invocations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Invoke multiple tools in parallel.
        
        Args:
            tool_invocations: List of {"tool_name": str, "parameters": dict}
            
        Returns:
            List of results in the same order
        """
        
        tasks = []
        for invocation in tool_invocations:
            task = self.invoke_tool(
                invocation.get("tool_name"),
                invocation.get("parameters", {})
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error responses
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "success": False,
                    "error": str(result),
                    "tool_name": tool_invocations[i].get("tool_name")
                })
            else:
                processed_results.append(result)
        
        return processed_results


def create_enhanced_bridge_routes(app: FastAPI, bridge: DynamicMCPBridge) -> None:
    """
    Create enhanced API routes for dynamic tool invocation.
    """
    
    class ToolInvocationRequest(BaseModel):
        """Request for single tool invocation."""
        tool_name: str
        parameters: Dict[str, Any] = Field(default_factory=dict)
    
    class BatchInvocationRequest(BaseModel):
        """Request for batch tool invocation."""
        invocations: List[ToolInvocationRequest]
        parallel: bool = Field(default=True, description="Execute in parallel")
    
    @app.post("/api/v2/tools/invoke")
    async def invoke_tool_dynamic(request: ToolInvocationRequest):
        """Dynamically invoke any registered MCP tool."""
        result = await bridge.invoke_tool(request.tool_name, request.parameters)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result)
        
        return result
    
    @app.post("/api/v2/tools/batch")
    async def batch_invoke_tools(request: BatchInvocationRequest):
        """Invoke multiple tools in a single request."""
        
        invocations = [
            {"tool_name": inv.tool_name, "parameters": inv.parameters}
            for inv in request.invocations
        ]
        
        if request.parallel:
            results = await bridge.batch_invoke(invocations)
        else:
            # Sequential execution
            results = []
            for inv in invocations:
                result = await bridge.invoke_tool(inv["tool_name"], inv["parameters"])
                results.append(result)
        
        return {
            "success": all(r["success"] for r in results),
            "results": results,
            "total": len(results),
            "failed": sum(1 for r in results if not r["success"])
        }
    
    @app.get("/api/v2/tools/catalog")
    async def get_tool_catalog(module: Optional[str] = None):
        """Get catalog of available tools."""
        info = bridge.get_tool_info()
        
        if module:
            # Filter by module
            if module in info["tools_by_module"]:
                return {
                    "module": module,
                    "tools": info["tools_by_module"][module],
                    "count": len(info["tools_by_module"][module])
                }
            else:
                raise HTTPException(status_code=404, detail=f"Module '{module}' not found")
        
        return info
    
    @app.get("/api/v2/tools/{tool_name}/info")
    async def get_tool_details(tool_name: str):
        """Get detailed information about a specific tool."""
        info = bridge.get_tool_info(tool_name)
        
        if not info["available"]:
            raise HTTPException(status_code=404, detail=info)
        
        return info
    
    @app.post("/api/v2/tools/discover")
    async def discover_tools_by_capability(capability: str):
        """Discover tools by capability description."""
        
        # Simple keyword matching for now
        # In production, this could use semantic search
        matching_tools = []
        capability_lower = capability.lower()
        
        for tool_name, metadata in bridge.tool_metadata.items():
            description_lower = (metadata.get("description") or "").lower()
            if (capability_lower in tool_name.lower() or 
                capability_lower in description_lower):
                matching_tools.append({
                    "tool_name": tool_name,
                    "module": metadata["module"],
                    "description": metadata["description"].split('\n')[0] if metadata["description"] else "No description",
                    "relevance_score": 1.0  # Simple binary match for now
                })
        
        return {
            "query": capability,
            "matches": len(matching_tools),
            "tools": sorted(matching_tools, key=lambda x: x["relevance_score"], reverse=True)
        }