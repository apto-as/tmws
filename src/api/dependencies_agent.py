"""
TMWS Agent Authentication Dependencies
Hestia's Secure Agent Dependency Injection System

This module provides FastAPI dependency injection for secure agent operations:
- Agent authentication verification
- Access control enforcement
- Request context establishment
- Security audit integration
"""

import logging
from typing import Optional, Dict, Any, Annotated
from datetime import datetime

from fastapi import Depends, HTTPException, status, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..security.agent_auth import AgentAuthenticator, create_agent_authenticator
from ..security.access_control import AccessControlManager, create_access_control_manager, ResourceType, ActionType
from ..security.data_encryption import EncryptionService, create_encryption_service
from ..core.config_loader import get_settings

logger = logging.getLogger(__name__)

# Global security service instances
_agent_authenticator: Optional[AgentAuthenticator] = None
_access_control: Optional[AccessControlManager] = None
_encryption_service: Optional[EncryptionService] = None

# FastAPI security scheme for agent tokens
agent_security = HTTPBearer(
    scheme_name="Agent Bearer Token",
    description="Agent authentication using Bearer token",
    auto_error=False
)


def get_agent_authenticator() -> AgentAuthenticator:
    """Get global agent authenticator instance."""
    global _agent_authenticator
    if _agent_authenticator is None:
        settings = get_settings()
        _agent_authenticator = create_agent_authenticator(settings.secret_key)
    return _agent_authenticator


def get_access_control() -> AccessControlManager:
    """Get global access control manager instance."""
    global _access_control
    if _access_control is None:
        _access_control = create_access_control_manager()
    return _access_control


def get_encryption_service() -> EncryptionService:
    """Get global encryption service instance."""
    global _encryption_service
    if _encryption_service is None:
        settings = get_settings()
        _encryption_service = create_encryption_service(settings.encryption_master_key)
    return _encryption_service


class AgentContext:
    """Agent request context with security information."""
    
    def __init__(
        self,
        agent_id: str,
        namespace: str,
        session_data: Dict[str, Any],
        request: Request,
        permissions: Optional[Dict[str, Any]] = None
    ):
        self.agent_id = agent_id
        self.namespace = namespace
        self.session_data = session_data
        self.request = request
        self.permissions = permissions or {}
        self.authenticated_at = datetime.utcnow()
        
        # Security context
        self.client_ip = self._get_client_ip()
        self.user_agent = request.headers.get("user-agent", "unknown")
        self.request_id = request.headers.get("x-request-id", "unknown")
    
    def _get_client_ip(self) -> str:
        """Extract client IP from request."""
        # Check for forwarded IP headers
        forwarded_for = self.request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = self.request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        return getattr(self.request.client, "host", "unknown")
    
    def has_permission(self, resource_type: ResourceType, action: ActionType) -> bool:
        """Check if agent has specific permission (cached result)."""
        permission_key = f"{resource_type.value}:{action.value}"
        return self.permissions.get(permission_key, False)
    
    def is_system_agent(self) -> bool:
        """Check if this is a system-level agent."""
        return self.namespace == "system" or self.agent_id.startswith("system-")
    
    def is_trinitas_agent(self) -> bool:
        """Check if this is a Trinitas core agent."""
        trinitas_agents = [
            "athena-conductor", "artemis-optimizer", "hestia-auditor",
            "eris-coordinator", "hera-strategist", "muses-documenter"
        ]
        return self.agent_id in trinitas_agents


async def authenticate_agent(
    request: Request,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(agent_security)],
    authenticator: Annotated[AgentAuthenticator, Depends(get_agent_authenticator)]
) -> AgentContext:
    """
    Authenticate agent from Bearer token.
    
    Args:
        request: FastAPI request object
        credentials: Bearer token credentials
        authenticator: Agent authentication service
        
    Returns:
        AgentContext: Authenticated agent context
        
    Raises:
        HTTPException: If authentication fails
    """
    # Check for development mode bypass
    settings = get_settings()
    if not settings.auth_enabled:
        # Development mode - create mock context
        mock_agent_id = request.headers.get("x-agent-id", "dev-agent")
        mock_namespace = request.headers.get("x-agent-namespace", "development")
        
        logger.debug(f"Development mode: bypassing auth for {mock_agent_id}")
        
        return AgentContext(
            agent_id=mock_agent_id,
            namespace=mock_namespace,
            session_data={"dev_mode": True},
            request=request
        )
    
    # Production mode - require authentication
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Agent authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    try:
        # Verify token
        token_payload = await authenticator.verify_agent_token(credentials.credentials)
        
        agent_id = token_payload["sub"]
        namespace = token_payload["namespace"]
        session_id = token_payload["session_id"]
        
        # Get session data
        session_data = authenticator.agent_sessions.get(agent_id, {})
        
        logger.info(f"Agent authenticated: {agent_id} (session: {session_id})")
        
        return AgentContext(
            agent_id=agent_id,
            namespace=namespace,
            session_data=session_data,
            request=request
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid agent credentials"
        )


async def require_agent_access(
    resource_type: ResourceType,
    action: ActionType,
    resource_id: Optional[str] = None
):
    """
    Dependency factory for resource access control.
    
    Usage:
        @app.get("/memories/{memory_id}")
        async def get_memory(
            memory_id: str,
            agent: AgentContext = Depends(authenticate_agent),
            _access: None = Depends(require_agent_access(ResourceType.MEMORY, ActionType.READ))
        ):
            # Agent has verified access to read memories
            pass
    """
    async def check_access(
        agent: Annotated[AgentContext, Depends(authenticate_agent)],
        access_control: Annotated[AccessControlManager, Depends(get_access_control)]
    ):
        """Check agent access to resource."""
        # Use resource_id from path if not provided
        target_resource = resource_id or "unknown"
        
        # For system agents, allow broader access
        if agent.is_system_agent():
            logger.debug(f"System agent {agent.agent_id} granted access to {resource_type.value}:{action.value}")
            return
        
        # Check access control
        try:
            has_access = await access_control.check_access(
                requesting_agent=agent.agent_id,
                resource_id=target_resource,
                resource_type=resource_type,
                action=action,
                resource_metadata={"namespace": agent.namespace}
            )
            
            if not has_access:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: {action.value} on {resource_type.value}"
                )
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Access control error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Access control system error"
            )
    
    return check_access


def require_trinitas_agent():
    """Require authenticated Trinitas core agent."""
    async def check_trinitas_agent(agent: Annotated[AgentContext, Depends(authenticate_agent)]):
        if not agent.is_trinitas_agent():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access restricted to Trinitas core agents"
            )
        return agent
    
    return check_trinitas_agent


def require_system_agent():
    """Require system-level agent."""
    async def check_system_agent(agent: Annotated[AgentContext, Depends(authenticate_agent)]):
        if not agent.is_system_agent():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="System-level access required"
            )
        return agent
    
    return check_system_agent


def require_namespace(required_namespace: str):
    """Require agent from specific namespace."""
    async def check_namespace(agent: Annotated[AgentContext, Depends(authenticate_agent)]):
        if agent.namespace != required_namespace:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access restricted to {required_namespace} namespace"
            )
        return agent
    
    return check_namespace


async def get_encrypted_data_handler(
    agent: Annotated[AgentContext, Depends(authenticate_agent)],
    encryption: Annotated[EncryptionService, Depends(get_encryption_service)]
):
    """Dependency for handling encrypted data operations."""
    class EncryptedDataHandler:
        def __init__(self, agent_context: AgentContext, encryption_service: EncryptionService):
            self.agent = agent_context
            self.encryption = encryption_service
        
        async def encrypt_data(
            self,
            data: Dict[str, Any],
            data_type: str,
            classification: str = "confidential"
        ) -> Dict[str, Any]:
            """Encrypt data for the current agent."""
            from ..security.data_encryption import DataClassification
            
            classification_enum = DataClassification(classification.lower())
            return await self.encryption.encrypt_agent_data(
                data, data_type, self.agent.agent_id, classification_enum
            )
        
        async def decrypt_data(
            self,
            encrypted_data: Dict[str, Any],
            data_type: str
        ) -> Dict[str, Any]:
            """Decrypt data for the current agent."""
            return await self.encryption.decrypt_agent_data(
                encrypted_data, data_type, self.agent.agent_id
            )
    
    return EncryptedDataHandler(agent, encryption)


# Convenience dependencies
CurrentAgent = Annotated[AgentContext, Depends(authenticate_agent)]
MemoryReadAccess = Depends(require_agent_access(ResourceType.MEMORY, ActionType.READ))
MemoryWriteAccess = Depends(require_agent_access(ResourceType.MEMORY, ActionType.UPDATE))
MemoryCreateAccess = Depends(require_agent_access(ResourceType.MEMORY, ActionType.CREATE))
TaskExecuteAccess = Depends(require_agent_access(ResourceType.TASK, ActionType.EXECUTE))
SystemAccess = Depends(require_system_agent())
TrinitasAccess = Depends(require_trinitas_agent())
EncryptedDataHandler = Annotated[object, Depends(get_encrypted_data_handler)]


__all__ = [
    "AgentContext",
    "authenticate_agent", 
    "require_agent_access",
    "require_trinitas_agent",
    "require_system_agent",
    "require_namespace",
    "get_encrypted_data_handler",
    "CurrentAgent",
    "MemoryReadAccess",
    "MemoryWriteAccess", 
    "MemoryCreateAccess",
    "TaskExecuteAccess",
    "SystemAccess",
    "TrinitasAccess",
    "EncryptedDataHandler"
]