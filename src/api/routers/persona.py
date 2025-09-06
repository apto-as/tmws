"""
Persona management endpoints for TMWS.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ...core.database import get_db_session_dependency
from ...models.persona import Persona, PersonaType, PersonaRole
from ..security import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


# Response Models
class PersonaResponse(BaseModel):
    """Persona response model."""
    id: str
    name: str
    type: str
    role: str
    display_name: str
    description: str
    specialties: List[str]
    capabilities: List[str]
    is_active: bool
    total_tasks: int
    successful_tasks: int
    success_rate: float
    average_response_time: Optional[float]
    created_at: datetime
    updated_at: datetime
    last_active_at: Optional[datetime]
    
    class Config:
        from_attributes = True


@router.get("/", response_model=List[PersonaResponse])
async def list_personas(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[PersonaResponse]:
    """
    List all available personas.
    
    Args:
        active_only: Only return active personas
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List of personas
    """
    try:
        query = select(Persona)
        if active_only:
            query = query.where(Persona.is_active == True)
        
        query = query.order_by(Persona.name)
        
        result = await db.execute(query)
        personas = result.scalars().all()
        
        return [
            PersonaResponse(
                id=str(persona.id),
                name=persona.name,
                type=persona.type.value if hasattr(persona.type, 'value') else persona.type,
                role=persona.role.value if hasattr(persona.role, 'value') else persona.role,
                display_name=persona.display_name,
                description=persona.description,
                specialties=persona.specialties,
                capabilities=persona.capabilities,
                is_active=persona.is_active,
                total_tasks=persona.total_tasks,
                successful_tasks=persona.successful_tasks,
                success_rate=persona.success_rate,
                average_response_time=persona.average_response_time,
                created_at=persona.created_at,
                updated_at=persona.updated_at,
                last_active_at=persona.last_active_at
            )
            for persona in personas
        ]
        
    except Exception as e:
        logger.error(f"Failed to list personas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve personas"
        )


@router.get("/{persona_name}", response_model=PersonaResponse)
async def get_persona(
    persona_name: str,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> PersonaResponse:
    """
    Get a specific persona by name.
    
    Args:
        persona_name: Persona name
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Persona data
    """
    try:
        result = await db.execute(
            select(Persona).where(Persona.name == persona_name)
        )
        persona = result.scalar_one_or_none()
        
        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Persona '{persona_name}' not found"
            )
        
        return PersonaResponse.from_orm(persona)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get persona {persona_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve persona"
        )


@router.post("/initialize", status_code=status.HTTP_201_CREATED)
async def initialize_default_personas(
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Initialize default Trinitas personas.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Initialization result
    """
    try:
        # Check if personas already exist
        result = await db.execute(select(Persona))
        existing_personas = result.scalars().all()
        
        if existing_personas:
            return {
                "message": "Personas already initialized",
                "count": len(existing_personas),
                "personas": [p.name for p in existing_personas]
            }
        
        # Create default personas
        default_personas = Persona.get_default_personas()
        created_personas = []
        
        for persona_data in default_personas:
            persona = Persona(**persona_data)
            db.add(persona)
            created_personas.append(persona.name)
        
        await db.commit()
        
        logger.info(f"Default personas initialized by user {current_user.get('id')}")
        
        return {
            "message": "Default personas initialized successfully",
            "count": len(created_personas),
            "personas": created_personas
        }
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to initialize personas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize personas"
        )


@router.get("/{persona_name}/stats")
async def get_persona_stats(
    persona_name: str,
    db: AsyncSession = Depends(get_db_session_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get detailed statistics for a specific persona.
    
    Args:
        persona_name: Persona name
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Persona statistics
    """
    try:
        result = await db.execute(
            select(Persona).where(Persona.name == persona_name)
        )
        persona = result.scalar_one_or_none()
        
        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Persona '{persona_name}' not found"
            )
        
        return {
            "name": persona.name,
            "display_name": persona.display_name,
            "type": persona.type.value,
            "role": persona.role.value,
            "performance": {
                "total_tasks": persona.total_tasks,
                "successful_tasks": persona.successful_tasks,
                "failed_tasks": persona.total_tasks - persona.successful_tasks,
                "success_rate": persona.success_rate,
                "average_response_time_ms": persona.average_response_time,
            },
            "activity": {
                "is_active": persona.is_active,
                "last_active_at": persona.last_active_at.isoformat() if persona.last_active_at else None,
                "created_at": persona.created_at.isoformat(),
                "updated_at": persona.updated_at.isoformat(),
            },
            "capabilities": {
                "specialties": persona.specialties,
                "capabilities": persona.capabilities,
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get persona stats for {persona_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve persona statistics"
        )