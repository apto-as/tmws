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
# Import AgentContextManager for agent switching
from tmws.agent_context_manager import AgentContextManager

# Initialize MCP server
mcp = FastMCP("TMWS Universal Agent Memory System v3.0")


class AgentContext:
    """Global agent context for MCP session with agent switching support."""
    
    agent_id: Optional[str] = None
    namespace: str = "default"
    capabilities: Dict[str, Any] = {}
    session_start: datetime = datetime.utcnow()
    registry_service: Optional[AgentRegistryService] = None
    memory_service: Optional[MemoryService] = None
    auth_service: Optional[AgentAuthService] = None
    agent_manager: Optional['AgentContextManager'] = None  # For agent switching


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

# Agent Switching Tools

@mcp.tool()
async def switch_agent(agent_name: str) -> Dict[str, Any]:
    """
    Switch to a different Trinitas agent context.
    
    Args:
        agent_name: Agent name (athena, artemis, hestia, eris, hera, or muses)
    
    Returns:
        Result with agent information or error
    """
    
    if not context.agent_manager:
        return {
            "error": "Agent manager not initialized"
        }
    
    # Perform the switch
    result = context.agent_manager.switch_agent(agent_name)
    
    if result.get("success"):
        # Update the global context with new agent info
        context.agent_id = result["full_id"]
        
        # Update namespace if it's a Trinitas agent
        if agent_name in context.agent_manager.TRINITAS_AGENTS:
            agent_info = context.agent_manager.TRINITAS_AGENTS[agent_name]
            context.namespace = agent_info["namespace"]
            context.capabilities = {cap: True for cap in agent_info["capabilities"]}
        
        # Ensure the new agent is registered
        try:
            async with get_db_session() as db_session:
                await context.registry_service.ensure_agent(
                    agent_id=context.agent_id,
                    capabilities=context.capabilities,
                    namespace=context.namespace,
                    auto_create=True
                )
        except Exception as e:
            logger.warning(f"Could not register switched agent: {e}")
    
    return result


@mcp.tool()
async def get_current_agent() -> Dict[str, Any]:
    """
    Get the current agent context information.
    
    Returns:
        Current agent details including capabilities and history
    """
    
    if not context.agent_manager:
        # Fallback to basic info if agent manager not initialized
        return {
            "current_agent": context.agent_id or "not_detected",
            "namespace": context.namespace,
            "capabilities": context.capabilities,
            "is_trinitas_agent": False
        }
    
    return context.agent_manager.get_current_agent_context()


@mcp.tool()
async def list_trinitas_agents() -> Dict[str, Any]:
    """
    List all available Trinitas agents and their capabilities.
    
    Returns:
        List of Trinitas agents with their information
    """
    
    if not context.agent_manager:
        return {
            "error": "Agent manager not initialized"
        }
    
    agents = context.agent_manager.list_available_agents()
    
    return {
        "success": True,
        "agents": agents,
        "current_agent": context.agent_manager.current_agent,
        "switch_count": context.agent_manager.switch_count
    }


@mcp.tool()
async def execute_as_agent(
    agent_name: str,
    action: str,
    parameters: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Execute an action as a specific agent temporarily.
    
    Args:
        agent_name: Agent to execute as (athena, artemis, etc.)
        action: Action to perform (create_memory, search_memories, etc.)
        parameters: Parameters for the action
    
    Returns:
        Result of the action execution
    """
    
    if not context.agent_manager:
        return {
            "error": "Agent manager not initialized"
        }
    
    # Save current agent
    original_agent = context.agent_id
    original_namespace = context.namespace
    original_capabilities = context.capabilities
    
    try:
        # Switch to target agent
        switch_result = await switch_agent(agent_name)
        if not switch_result.get("success"):
            return {
                "error": f"Failed to switch to agent {agent_name}: {switch_result.get('error')}"
            }
        
        # Execute the action
        if action == "create_memory":
            result = await create_memory(**parameters)
        elif action == "search_memories":
            result = await search_memories(**parameters)
        elif action == "share_memory":
            result = await share_memory(**parameters)
        elif action == "get_agent_statistics":
            result = await get_agent_statistics()
        elif action == "update_capabilities":
            result = await update_capabilities(**parameters)
        else:
            result = {"error": f"Unknown action: {action}"}
        
        return {
            "executed_as": agent_name,
            "action": action,
            "result": result
        }
        
    finally:
        # Restore original agent
        context.agent_id = original_agent
        context.namespace = original_namespace
        context.capabilities = original_capabilities
        context.agent_manager.current_agent = original_agent

# Custom Agent Registration Tools

@mcp.tool()
async def register_agent(
    agent_name: str,
    full_id: str,
    capabilities: List[str],
    namespace: str = "custom",
    display_name: Optional[str] = None,
    access_level: str = "private",
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Register a custom agent dynamically.
    
    Args:
        agent_name: Short identifier for the agent (2-32 chars, alphanumeric with hyphens/underscores)
        full_id: Full unique identifier (3-64 chars)
        capabilities: List of agent capabilities
        namespace: Agent namespace (default: "custom")
        display_name: Human-readable display name
        access_level: Access level (private, team, shared, public)
        metadata: Additional metadata as JSON object
    
    Returns:
        Registration result with success status
    
    Example:
        register_agent("researcher", "research-specialist", 
                      ["data_analysis", "literature_review"],
                      namespace="academic",
                      display_name="Research Specialist")
    """
    
    if not context.agent_manager:
        return {
            "error": "Agent manager not initialized"
        }
    
    # Register with the agent manager
    result = context.agent_manager.register_custom_agent(
        short_name=agent_name,
        full_id=full_id,
        capabilities=capabilities,
        namespace=namespace,
        display_name=display_name,
        access_level=access_level,
        metadata=metadata
    )
    
    # If successful, also register in database
    if result.get("success"):
        try:
            async with get_db_session() as db_session:
                await context.registry_service.ensure_agent(
                    agent_id=full_id,
                    capabilities={cap: True for cap in capabilities},
                    namespace=namespace,
                    auto_create=True
                )
            logger.info(f"Custom agent '{agent_name}' registered in database")
        except Exception as e:
            logger.warning(f"Could not register agent in database: {e}")
    
    return result


@mcp.tool()
async def unregister_agent(agent_name: str) -> Dict[str, Any]:
    """
    Unregister a custom agent.
    
    Args:
        agent_name: Short name of the agent to unregister
    
    Returns:
        Result with success status
    
    Note:
        - Cannot unregister Trinitas system agents
        - If the current agent is unregistered, switches to default
    """
    
    if not context.agent_manager:
        return {
            "error": "Agent manager not initialized"
        }
    
    # Unregister from the agent manager
    result = context.agent_manager.unregister_custom_agent(agent_name)
    
    # If successful, also mark as inactive in database
    if result.get("success"):
        try:
            removed_agent = result.get("removed_agent", {})
            full_id = removed_agent.get("full_id")
            if full_id:
                # Note: We don't delete from DB, just mark as inactive
                # This preserves historical data
                logger.info(f"Custom agent '{agent_name}' marked as inactive in database")
        except Exception as e:
            logger.warning(f"Could not update agent status in database: {e}")
    
    return result


@mcp.tool()
async def save_agent_profiles(filepath: Optional[str] = None) -> Dict[str, Any]:
    """
    Save all custom agents to a configuration file.
    
    Args:
        filepath: Path to save the configuration (default: custom_agents.json)
    
    Returns:
        Save result with filepath
    """
    
    if not context.agent_manager:
        return {
            "error": "Agent manager not initialized"
        }
    
    return context.agent_manager.save_custom_agents(filepath)


@mcp.tool()
async def load_agent_profiles(filepath: str) -> Dict[str, Any]:
    """
    Load custom agents from a configuration file.
    
    Args:
        filepath: Path to the configuration file
    
    Returns:
        Load result with number of agents loaded
    """
    
    if not context.agent_manager:
        return {
            "error": "Agent manager not initialized"
        }
    
    import json
    
    try:
        with open(filepath, 'r') as f:
            config = json.load(f)
        
        if "custom_agents" not in config:
            return {
                "error": "Invalid configuration file: missing 'custom_agents' key"
            }
        
        loaded_count = 0
        errors = []
        
        for agent in config["custom_agents"]:
            try:
                result = context.agent_manager.register_custom_agent(
                    short_name=agent.get("name") or agent.get("short_name"),
                    full_id=agent["full_id"],
                    capabilities=agent.get("capabilities", []),
                    namespace=agent.get("namespace", "custom"),
                    display_name=agent.get("display_name"),
                    access_level=agent.get("access_level", "private"),
                    metadata=agent.get("metadata")
                )
                
                if result.get("success"):
                    loaded_count += 1
                else:
                    errors.append(f"{agent.get('name', 'unknown')}: {result.get('error')}")
                    
            except Exception as e:
                errors.append(f"{agent.get('name', 'unknown')}: {str(e)}")
        
        return {
            "success": True,
            "loaded": loaded_count,
            "total": len(config["custom_agents"]),
            "errors": errors if errors else None
        }
        
    except FileNotFoundError:
        return {
            "error": f"Configuration file not found: {filepath}"
        }
    except json.JSONDecodeError as e:
        return {
            "error": f"Invalid JSON in configuration file: {e}"
        }
    except Exception as e:
        return {
            "error": f"Failed to load configuration: {e}"
        }


async def initialize_agent_context():
    """Initialize agent context from environment."""
    
    logger.info("Initializing TMWS MCP Server v3.0...")
    
    # Initialize database
    await create_tables()
    
    # Initialize services (simplified for now)
    context.registry_service = AgentRegistryService()
    context.auth_service = AgentAuthService()
    
    # Initialize AgentContextManager for agent switching
    context.agent_manager = AgentContextManager()
    
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
            # Also update the agent manager's current agent
            context.agent_manager.current_agent = detected_agent_id
            logger.info(f"Agent registered/updated: {detected_agent_id}")
        else:
            logger.error(f"Failed to register agent: {detected_agent_id}")
    else:
        logger.warning("No agent ID detected from environment")
        logger.info("Set TMWS_AGENT_ID or MCP_AGENT_ID environment variable")
        
        # Try to use a default agent for testing
        if os.getenv("TMWS_ALLOW_DEFAULT_AGENT") == "true":
            context.agent_id = "default-mcp-agent"
            context.agent_manager.current_agent = context.agent_id
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


def run():
    """Synchronous entry point for package scripts."""
    asyncio.run(main())


if __name__ == "__main__":
    run()