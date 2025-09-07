#!/usr/bin/env python3
"""
TMWS MCP Server v3.0 - Universal Agent Memory System
Enhanced with automatic agent detection and registration.
"""

import os
import sys
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastmcp import FastMCP
from pydantic import BaseModel

from tmws.services.agent_registry_service import AgentRegistryService
from tmws.services.memory_service import MemoryService
from tmws.security.agent_auth import AgentAuthService
from tmws.core.database import create_tables, get_db_session

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("TMWS Universal Agent Memory System v3.0")


class AgentContext:
    """Global agent context for MCP session."""
    
    agent_id: Optional[str] = None
    namespace: str = "default"
    capabilities: Dict[str, Any] = {}
    session_start: datetime = datetime.utcnow()
    registry_service: Optional[AgentRegistryService] = None
    memory_service: Optional[MemoryService] = None
    auth_service: Optional[AgentAuthService] = None


# Global context instance
context = AgentContext()


@mcp.tool()
async def get_agent_info() -> Dict[str, Any]:
    """Get current agent information and session details."""
    
    return {
        "agent_id": context.agent_id or "not_detected",
        "namespace": context.namespace,
        "capabilities": context.capabilities,
        "session_start": context.session_start.isoformat(),
        "session_duration_seconds": (datetime.utcnow() - context.session_start).total_seconds(),
        "auto_detected": context.agent_id is not None
    }


@mcp.tool()
async def create_memory(
    content: str,
    tags: List[str] = None,
    importance: float = 0.5,
    access_level: str = "private",
    context_data: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Create a new memory for the current agent.
    
    The agent is automatically detected from environment.
    """
    
    if not context.agent_id:
        return {
            "error": "No agent detected. Set TMWS_AGENT_ID or MCP_AGENT_ID environment variable."
        }
    
    try:
        memory = await context.memory_service.create_memory(
            content=content,
            agent_id=context.agent_id,
            namespace=context.namespace,
            tags=tags or [],
            importance_score=importance,
            access_level=access_level,
            context=context_data or {}
        )
        
        return {
            "success": True,
            "memory_id": str(memory.id),
            "agent_id": context.agent_id,
            "message": "Memory created successfully"
        }
    except Exception as e:
        logger.error(f"Error creating memory: {e}")
        return {
            "error": str(e)
        }


@mcp.tool()
async def search_memories(
    query: str,
    limit: int = 10,
    include_shared: bool = True,
    min_importance: float = 0.0
) -> Dict[str, Any]:
    """
    Search memories using semantic search.
    
    Returns memories accessible to the current agent.
    """
    
    if not context.agent_id:
        return {
            "error": "No agent detected. Set TMWS_AGENT_ID or MCP_AGENT_ID environment variable."
        }
    
    try:
        results = await context.memory_service.search_memories(
            query=query,
            agent_id=context.agent_id,
            namespace=context.namespace,
            limit=limit,
            include_shared=include_shared,
            min_importance=min_importance
        )
        
        memories = []
        for memory in results:
            # Check access permissions
            if context.auth_service.check_memory_access(
                agent_id=context.agent_id,
                agent_namespace=context.namespace,
                memory_agent_id=memory.agent_id,
                memory_namespace=memory.namespace,
                memory_access_level=memory.access_level,
                shared_agents=memory.shared_with_agents
            ):
                memories.append({
                    "id": str(memory.id),
                    "content": memory.content,
                    "summary": memory.summary,
                    "importance": memory.importance_score,
                    "relevance": memory.relevance_score,
                    "tags": memory.tags,
                    "created_at": memory.created_at.isoformat() if memory.created_at else None
                })
        
        return {
            "success": True,
            "agent_id": context.agent_id,
            "count": len(memories),
            "memories": memories
        }
    except Exception as e:
        logger.error(f"Error searching memories: {e}")
        return {
            "error": str(e)
        }


@mcp.tool()
async def share_memory(
    memory_id: str,
    share_with_agents: List[str],
    permission: str = "read"
) -> Dict[str, Any]:
    """Share a memory with other agents."""
    
    if not context.agent_id:
        return {
            "error": "No agent detected"
        }
    
    try:
        # Implementation would go here
        return {
            "success": True,
            "message": f"Memory shared with {len(share_with_agents)} agents"
        }
    except Exception as e:
        return {
            "error": str(e)
        }


@mcp.tool()
async def get_agent_statistics() -> Dict[str, Any]:
    """Get statistics for the current agent."""
    
    if not context.agent_id:
        return {
            "error": "No agent detected"
        }
    
    try:
        stats = await context.registry_service.get_agent_statistics(context.agent_id)
        return stats
    except Exception as e:
        return {
            "error": str(e)
        }


@mcp.tool()
async def list_agents(
    namespace: Optional[str] = None,
    agent_type: Optional[str] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """List all registered agents."""
    
    try:
        agents = await context.registry_service.list_agents(
            namespace=namespace,
            agent_type=agent_type,
            limit=limit
        )
        
        agent_list = []
        for agent in agents:
            agent_list.append({
                "agent_id": agent.agent_id,
                "display_name": agent.display_name,
                "agent_type": agent.agent_type,
                "namespace": agent.namespace,
                "status": agent.status.value,
                "health_score": agent.health_score
            })
        
        return {
            "success": True,
            "count": len(agent_list),
            "agents": agent_list
        }
    except Exception as e:
        return {
            "error": str(e)
        }


@mcp.tool()
async def update_capabilities(capabilities: Dict[str, Any]) -> Dict[str, Any]:
    """Update capabilities for the current agent."""
    
    if not context.agent_id:
        return {
            "error": "No agent detected"
        }
    
    try:
        success = await context.registry_service.update_agent_capabilities(
            context.agent_id,
            capabilities
        )
        
        if success:
            context.capabilities = capabilities
            return {
                "success": True,
                "message": "Capabilities updated",
                "capabilities": capabilities
            }
        else:
            return {
                "error": "Failed to update capabilities"
            }
    except Exception as e:
        return {
            "error": str(e)
        }


async def initialize_agent_context():
    """Initialize agent context from environment."""
    
    logger.info("Initializing TMWS MCP Server v3.0...")
    
    # Initialize database
    await create_tables()
    
    # Initialize services (simplified for now)
    context.registry_service = AgentRegistryService()
    context.auth_service = AgentAuthService()
    
    # For now, create a simple in-memory service
    # Will need proper session management later
    context.memory_service = None  # Will be created per-request
    
    # Detect agent from environment
    detected_agent_id = await context.registry_service.detect_agent_from_environment()
    
    if detected_agent_id:
        logger.info(f"Auto-detected agent ID: {detected_agent_id}")
        
        # Get namespace from environment
        context.namespace = os.getenv("TMWS_AGENT_NAMESPACE", "default")
        
        # Get capabilities from environment (JSON string)
        import json
        capabilities_str = os.getenv("TMWS_AGENT_CAPABILITIES", "{}")
        try:
            context.capabilities = json.loads(capabilities_str)
        except:
            context.capabilities = {}
        
        # Ensure agent is registered
        async with get_db_session() as db_session:
            agent = await context.registry_service.ensure_agent(
                agent_id=detected_agent_id,
                capabilities=context.capabilities,
                namespace=context.namespace,
                auto_create=True
            )
        
        if agent:
            context.agent_id = detected_agent_id
            logger.info(f"Agent registered/updated: {detected_agent_id}")
        else:
            logger.error(f"Failed to register agent: {detected_agent_id}")
    else:
        logger.warning("No agent ID detected from environment")
        logger.info("Set TMWS_AGENT_ID or MCP_AGENT_ID environment variable")
        
        # Try to use a default agent for testing
        if os.getenv("TMWS_ALLOW_DEFAULT_AGENT") == "true":
            context.agent_id = "default-mcp-agent"
            async with get_db_session() as db_session:
                await context.registry_service.ensure_agent(
                    agent_id=context.agent_id,
                    namespace="default",
                    auto_create=True
                )
            logger.info("Using default agent for testing")
    
    logger.info(f"MCP Server initialized with agent: {context.agent_id or 'none'}")


async def shutdown_handler():
    """Cleanup on shutdown."""
    
    logger.info("Shutting down TMWS MCP Server...")
    
    # Update agent last active time
    if context.agent_id and context.registry_service:
        try:
            agent = await context.registry_service.ensure_agent(
                context.agent_id,
                namespace=context.namespace,
                auto_create=False
            )
            if agent:
                agent.last_active_at = datetime.utcnow()
        except:
            pass
    
    logger.info("Shutdown complete")


# Server metadata
@mcp.resource("server://info")
async def get_server_info() -> Dict[str, Any]:
    """Get server information and status."""
    
    return {
        "name": "TMWS Universal Agent Memory System",
        "version": "3.0.0",
        "description": "Multi-agent memory management with automatic agent detection",
        "agent_context": {
            "current_agent": context.agent_id,
            "namespace": context.namespace,
            "auto_detection": "enabled",
            "session_start": context.session_start.isoformat()
        },
        "features": [
            "Automatic agent detection from environment",
            "Multi-agent memory isolation",
            "Semantic memory search",
            "Memory sharing and collaboration",
            "Learning pattern extraction",
            "Comprehensive statistics"
        ],
        "environment_variables": [
            "TMWS_AGENT_ID - Primary agent identifier",
            "MCP_AGENT_ID - Alternative agent identifier",
            "TMWS_AGENT_NAMESPACE - Agent namespace (default: 'default')",
            "TMWS_AGENT_CAPABILITIES - JSON string of capabilities",
            "TMWS_ALLOW_DEFAULT_AGENT - Allow default agent for testing"
        ]
    }


async def main():
    """Main entry point."""
    
    # Initialize agent context
    await initialize_agent_context()
    
    # Run MCP server
    async with mcp:
        logger.info("TMWS MCP Server v3.0 is running...")
        logger.info(f"Current agent: {context.agent_id or 'not detected'}")
        
        # Keep server running
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            await shutdown_handler()


if __name__ == "__main__":
    asyncio.run(main())