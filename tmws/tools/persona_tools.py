"""
Persona Management Tools for TMWS MCP Server
Handles Trinitas persona creation, management, and interaction
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from fastmcp import FastMCP

from .base_tool import BaseTool


class PersonaCreateRequest(BaseModel):
    """Persona creation parameters."""
    name: str = Field(..., description="Persona name")
    description: str = Field(..., description="Persona description")
    capabilities: List[str] = Field(..., description="List of persona capabilities")
    personality_traits: Dict[str, Any] = Field(default_factory=dict, description="Personality traits")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class PersonaUpdateRequest(BaseModel):
    """Persona update parameters."""
    persona_id: str = Field(..., description="Persona ID to update")
    name: Optional[str] = Field(None, description="New name")
    description: Optional[str] = Field(None, description="New description")
    capabilities: Optional[List[str]] = Field(None, description="New capabilities")
    personality_traits: Optional[Dict[str, Any]] = Field(None, description="New personality traits")
    metadata: Optional[Dict[str, Any]] = Field(None, description="New metadata")
    is_active: Optional[bool] = Field(None, description="Active status")


class PersonaTools(BaseTool):
    """Persona management tools for TMWS MCP server."""

    async def register_tools(self, mcp: FastMCP) -> None:
        """Register persona tools with FastMCP instance."""

        @mcp.tool()
        async def create_persona(
            name: str,
            description: str,
            capabilities: List[str],
            personality_traits: Dict[str, Any] = None,
            metadata: Dict[str, Any] = None
        ) -> Dict[str, Any]:
            """
            Create a new Trinitas persona.
            
            Personas represent specialized AI agents with specific capabilities and traits.
            Each persona has unique characteristics that define their behavior and expertise.
            
            Args:
                name: Persona name (e.g., "Athena", "Artemis")
                description: Detailed description of persona's role and purpose
                capabilities: List of specific capabilities and skills
                personality_traits: Dict of personality characteristics
                metadata: Additional structured metadata
                
            Returns:
                Dict containing persona details and creation info
            """
            request = PersonaCreateRequest(
                name=name,
                description=description,
                capabilities=capabilities,
                personality_traits=personality_traits or {},
                metadata=metadata or {}
            )
            
            async def _create_persona(session, services):
                persona_service = services['persona_service']
                
                persona = await persona_service.create_persona(
                    name=request.name,
                    description=request.description,
                    capabilities=request.capabilities,
                    personality_traits=request.personality_traits,
                    metadata=request.metadata
                )
                
                return {
                    "id": str(persona.id),
                    "name": persona.name,
                    "description": persona.description,
                    "capabilities": persona.capabilities,
                    "personality_traits": persona.personality_traits,
                    "metadata": persona.metadata_json,
                    "is_active": persona.is_active,
                    "created_at": persona.created_at.isoformat(),
                    "capability_count": len(persona.capabilities)
                }
            
            result = await self.execute_with_session(_create_persona)
            return self.format_success(result, f"Persona '{name}' created successfully")

        @mcp.tool()
        async def get_persona(persona_id: str) -> Dict[str, Any]:
            """
            Get persona details by ID.
            
            Retrieves complete persona information including capabilities,
            personality traits, and associated metadata.
            
            Args:
                persona_id: Unique persona identifier
                
            Returns:
                Dict containing complete persona information
            """
            async def _get_persona(session, services):
                persona_service = services['persona_service']
                persona = await persona_service.get_persona(persona_id)
                
                if not persona:
                    raise ValueError(f"Persona {persona_id} not found")
                
                # Get associated memories and tasks
                memory_service = services['memory_service']
                task_service = services['task_service']
                
                memory_count = await memory_service.count_memories(persona_id=persona_id)
                active_tasks = await task_service.count_active_tasks(persona_id=persona_id)
                
                return {
                    "id": str(persona.id),
                    "name": persona.name,
                    "description": persona.description,
                    "capabilities": persona.capabilities,
                    "personality_traits": persona.personality_traits,
                    "metadata": persona.metadata_json,
                    "is_active": persona.is_active,
                    "created_at": persona.created_at.isoformat(),
                    "updated_at": persona.updated_at.isoformat() if persona.updated_at else None,
                    "statistics": {
                        "memory_count": memory_count,
                        "active_tasks": active_tasks,
                        "capability_count": len(persona.capabilities)
                    }
                }
            
            result = await self.execute_with_session(_get_persona)
            return self.format_success(result, "Persona retrieved successfully")

        @mcp.tool()
        async def list_personas(
            active_only: bool = True,
            include_stats: bool = False,
            limit: int = 50
        ) -> Dict[str, Any]:
            """
            List all available personas.
            
            Retrieves personas with optional filtering and statistics.
            
            Args:
                active_only: Only return active personas
                include_stats: Include memory and task statistics
                limit: Maximum number of personas to return
                
            Returns:
                Dict containing list of personas with optional statistics
            """
            async def _list_personas(session, services):
                persona_service = services['persona_service']
                personas = await persona_service.list_personas(
                    active_only=active_only,
                    limit=limit
                )
                
                persona_list = []
                for p in personas:
                    persona_data = {
                        "id": str(p.id),
                        "name": p.name,
                        "description": p.description,
                        "capabilities": p.capabilities,
                        "is_active": p.is_active,
                        "created_at": p.created_at.isoformat()
                    }
                    
                    if include_stats:
                        memory_service = services['memory_service']
                        task_service = services['task_service']
                        
                        memory_count = await memory_service.count_memories(persona_id=str(p.id))
                        active_tasks = await task_service.count_active_tasks(persona_id=str(p.id))
                        
                        persona_data["statistics"] = {
                            "memory_count": memory_count,
                            "active_tasks": active_tasks
                        }
                    
                    persona_list.append(persona_data)
                
                return {
                    "count": len(persona_list),
                    "active_filter": active_only,
                    "include_stats": include_stats,
                    "personas": persona_list
                }
            
            result = await self.execute_with_session(_list_personas)
            return self.format_success(result, f"Retrieved {result.get('count', 0)} personas")

        @mcp.tool()
        async def update_persona(
            persona_id: str,
            name: Optional[str] = None,
            description: Optional[str] = None,
            capabilities: Optional[List[str]] = None,
            personality_traits: Optional[Dict[str, Any]] = None,
            metadata: Optional[Dict[str, Any]] = None,
            is_active: Optional[bool] = None
        ) -> Dict[str, Any]:
            """
            Update an existing persona.
            
            Allows partial updates to persona information while preserving
            existing data for unspecified fields.
            
            Args:
                persona_id: ID of persona to update
                name: New persona name
                description: New description
                capabilities: New capabilities list
                personality_traits: New personality traits
                metadata: New metadata
                is_active: New active status
                
            Returns:
                Dict containing updated persona information
            """
            request = PersonaUpdateRequest(
                persona_id=persona_id,
                name=name,
                description=description,
                capabilities=capabilities,
                personality_traits=personality_traits,
                metadata=metadata,
                is_active=is_active
            )
            
            async def _update_persona(session, services):
                persona_service = services['persona_service']
                
                updates = {}
                if request.name is not None:
                    updates['name'] = request.name
                if request.description is not None:
                    updates['description'] = request.description
                if request.capabilities is not None:
                    updates['capabilities'] = request.capabilities
                if request.personality_traits is not None:
                    updates['personality_traits'] = request.personality_traits
                if request.metadata is not None:
                    updates['metadata'] = request.metadata
                if request.is_active is not None:
                    updates['is_active'] = request.is_active
                
                persona = await persona_service.update_persona(request.persona_id, updates)
                
                return {
                    "id": str(persona.id),
                    "name": persona.name,
                    "description": persona.description,
                    "capabilities": persona.capabilities,
                    "personality_traits": persona.personality_traits,
                    "metadata": persona.metadata_json,
                    "is_active": persona.is_active,
                    "updated_at": persona.updated_at.isoformat()
                }
            
            result = await self.execute_with_session(_update_persona)
            return self.format_success(result, "Persona updated successfully")

        @mcp.tool()
        async def delete_persona(persona_id: str) -> Dict[str, Any]:
            """
            Delete a persona by ID.
            
            Permanently removes persona and optionally handles associated memories
            and tasks based on configured cascade behavior.
            
            Args:
                persona_id: ID of persona to delete
                
            Returns:
                Dict confirming deletion with cleanup summary
            """
            async def _delete_persona(session, services):
                persona_service = services['persona_service']
                memory_service = services['memory_service']
                task_service = services['task_service']
                
                # Get counts before deletion
                memory_count = await memory_service.count_memories(persona_id=persona_id)
                task_count = await task_service.count_active_tasks(persona_id=persona_id)
                
                await persona_service.delete_persona(persona_id)
                
                return {
                    "id": persona_id,
                    "deleted_at": datetime.utcnow().isoformat(),
                    "cleanup_summary": {
                        "associated_memories": memory_count,
                        "associated_tasks": task_count
                    }
                }
            
            result = await self.execute_with_session(_delete_persona)
            return self.format_success(result, "Persona deleted successfully")

        @mcp.tool()
        async def get_persona_capabilities() -> Dict[str, Any]:
            """
            Get all available persona capabilities.
            
            Returns a comprehensive list of all capabilities defined across
            all personas, with usage statistics.
            
            Returns:
                Dict containing capability catalog with usage metrics
            """
            async def _get_capabilities(session, services):
                persona_service = services['persona_service']
                
                # Get all personas to analyze capabilities
                all_personas = await persona_service.list_personas(active_only=False, limit=1000)
                
                capability_usage = {}
                total_personas = len(all_personas)
                
                for persona in all_personas:
                    for capability in persona.capabilities:
                        if capability not in capability_usage:
                            capability_usage[capability] = {
                                "count": 0,
                                "personas": []
                            }
                        capability_usage[capability]["count"] += 1
                        capability_usage[capability]["personas"].append(persona.name)
                
                # Sort by usage frequency
                sorted_capabilities = sorted(
                    capability_usage.items(),
                    key=lambda x: x[1]["count"],
                    reverse=True
                )
                
                return {
                    "total_capabilities": len(capability_usage),
                    "total_personas": total_personas,
                    "capabilities": {
                        name: {
                            "usage_count": data["count"],
                            "usage_percentage": (data["count"] / total_personas) * 100,
                            "used_by": data["personas"]
                        }
                        for name, data in sorted_capabilities
                    }
                }
            
            result = await self.execute_with_session(_get_capabilities)
            return self.format_success(result, "Persona capabilities retrieved")

        @mcp.tool()
        async def find_personas_by_capability(capability: str) -> Dict[str, Any]:
            """
            Find personas that have a specific capability.
            
            Searches for personas with the specified capability, returning
            detailed information about matching personas.
            
            Args:
                capability: Capability to search for
                
            Returns:
                Dict containing matching personas and their details
            """
            async def _find_by_capability(session, services):
                persona_service = services['persona_service']
                
                personas = await persona_service.find_personas_by_capability(capability)
                
                return {
                    "capability": capability,
                    "match_count": len(personas),
                    "personas": [
                        {
                            "id": str(p.id),
                            "name": p.name,
                            "description": p.description,
                            "is_active": p.is_active,
                            "all_capabilities": p.capabilities
                        }
                        for p in personas
                    ]
                }
            
            result = await self.execute_with_session(_find_by_capability)
            return self.format_success(result, f"Found {result.get('match_count', 0)} personas with capability '{capability}'")