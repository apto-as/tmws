"""
API Dependencies for TMWS
Provides dependency injection for FastAPI routes
"""

import logging
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..core.database import get_db_session_dependency
from ..services.task_service import TaskService
from ..services.workflow_service import WorkflowService
from ..services.memory_service import MemoryService
from ..services.persona_service import PersonaService

logger = logging.getLogger(__name__)
settings = get_settings()

# Security scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Dict[str, Any]:
    """
    Get current user from JWT token.
    In development mode with auth disabled, returns a mock user.
    """
    if not settings.auth_enabled:
        # Development mode - return mock user
        return {
            "id": "dev-user",
            "username": "developer",
            "roles": ["admin"],
            "is_authenticated": True
        }
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # TODO: Implement JWT validation when auth is enabled
    # For now, just return a mock authenticated user
    return {
        "id": "authenticated-user",
        "username": "user",
        "roles": ["user"],
        "is_authenticated": True
    }


def get_task_service() -> TaskService:
    """Get task service instance"""
    return TaskService()


def get_workflow_service() -> WorkflowService:
    """Get workflow service instance"""
    return WorkflowService()


def get_memory_service() -> MemoryService:
    """Get memory service instance"""
    return MemoryService()


def get_persona_service() -> PersonaService:
    """Get persona service instance"""
    return PersonaService()


async def verify_api_key(
    request: Request,
    api_key: Optional[str] = None
) -> bool:
    """
    Verify API key for service-to-service authentication.
    """
    if not settings.auth_enabled:
        return True
    
    # Check header for API key
    if not api_key:
        api_key = request.headers.get("X-API-Key")
    
    if not api_key:
        return False
    
    # TODO: Implement actual API key validation
    # For now, just check if key is present
    return bool(api_key)


async def check_rate_limit(
    request: Request,
    user: Dict[str, Any] = Depends(get_current_user)
) -> None:
    """
    Check rate limiting for the current user.
    Rate limiting is handled by middleware, this is for custom checks.
    """
    # Rate limiting is primarily handled by UnifiedSecurityMiddleware
    # This dependency can be used for route-specific rate limiting
    pass


async def require_admin(
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Require admin role for access.
    """
    if "admin" not in user.get("roles", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user


async def get_request_metadata(
    request: Request,
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Extract metadata from request for auditing.
    """
    return {
        "user_id": user.get("id"),
        "username": user.get("username"),
        "ip_address": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", "unknown"),
        "method": request.method,
        "path": request.url.path,
        "timestamp": "now()"  # Will be set by database
    }


# Export public interface
__all__ = [
    "get_current_user",
    "get_task_service",
    "get_workflow_service",
    "get_memory_service", 
    "get_persona_service",
    "verify_api_key",
    "check_rate_limit",
    "require_admin",
    "get_request_metadata",
    "security"
]