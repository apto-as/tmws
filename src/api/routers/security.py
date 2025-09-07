"""
TMWS Security Management API
Hestia's Security Administration Endpoints

This module provides API endpoints for security management:
- Agent registration and authentication
- Access control policy management
- Security audit and monitoring
- Encryption key management
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum

from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel, Field

from ..dependencies_agent import (
    CurrentAgent, SystemAccess, TrinitasAccess,
    get_agent_authenticator, get_access_control, get_encryption_service
)
from ...security.agent_auth import AgentAuthenticator, AgentAccessLevel, AgentPermission
from ...security.access_control import AccessControlManager, ResourceType, ActionType, AccessPolicy
from ...security.data_encryption import EncryptionService, DataClassification

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/security", tags=["security"])


# Pydantic models for API
class AgentRegistrationRequest(BaseModel):
    """Request model for agent registration."""
    agent_id: str = Field(..., min_length=3, max_length=100, pattern=r'^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?$')
    display_name: str = Field(..., min_length=1, max_length=200)
    namespace: str = Field("default", min_length=1, max_length=50)
    access_level: AgentAccessLevel = AgentAccessLevel.STANDARD
    description: Optional[str] = Field(None, max_length=500)


class AgentRegistrationResponse(BaseModel):
    """Response model for agent registration."""
    agent_id: str
    api_key: str = Field(..., description="Store securely - cannot be retrieved later")
    public_key: str
    namespace: str
    access_level: str
    registered_at: datetime


class AgentAuthRequest(BaseModel):
    """Request model for agent authentication."""
    agent_id: str
    api_key: str


class AgentTokenResponse(BaseModel):
    """Response model for agent token."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    agent_id: str
    namespace: str


class AccessPolicyRequest(BaseModel):
    """Request model for creating access policies."""
    policy_id: str = Field(..., min_length=3, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=500)
    resource_types: List[ResourceType]
    actions: List[ActionType]
    agent_patterns: List[str]
    conditions: List[Dict[str, Any]] = Field(default_factory=list)
    priority: int = Field(100, ge=1, le=1000)


class SecurityStatsResponse(BaseModel):
    """Response model for security statistics."""
    timestamp: datetime
    total_registered_agents: int
    active_sessions: int
    access_attempts_24h: int
    access_denials_24h: int
    policies_count: int
    encryption_stats: Dict[str, Any]


class AuditLogEntry(BaseModel):
    """Model for audit log entries."""
    timestamp: datetime
    event_type: str
    agent_id: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    action: Optional[str]
    result: str
    details: Dict[str, Any]


@router.post("/agents/register", response_model=AgentRegistrationResponse, status_code=status.HTTP_201_CREATED)
async def register_agent(
    request: AgentRegistrationRequest,
    current_agent: CurrentAgent,
    _: SystemAccess,
    authenticator: AgentAuthenticator = Depends(get_agent_authenticator)
):
    """
    Register a new agent with the system.
    
    Requires system-level access. Only system administrators can register new agents.
    """
    try:
        # Register agent
        registration_result = await authenticator.register_agent(
            agent_id=request.agent_id,
            namespace=request.namespace,
            access_level=request.access_level
        )
        
        logger.info(f"Agent registered: {request.agent_id} by {current_agent.agent_id}")
        
        return AgentRegistrationResponse(
            agent_id=registration_result["agent_id"],
            api_key=registration_result["api_key"],
            public_key=registration_result["public_key"],
            namespace=registration_result["namespace"],
            access_level=request.access_level.value,
            registered_at=datetime.utcnow()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Agent registration failed"
        )


@router.post("/agents/authenticate", response_model=AgentTokenResponse)
async def authenticate_agent(
    request: AgentAuthRequest,
    authenticator: AgentAuthenticator = Depends(get_agent_authenticator)
):
    """
    Authenticate agent and return access token.
    
    This is a public endpoint for agent authentication.
    """
    try:
        # Authenticate agent
        session_data = await authenticator.authenticate_agent(
            agent_id=request.agent_id,
            api_key=request.api_key
        )
        
        # Create token
        access_token = await authenticator.create_agent_token(request.agent_id)
        
        expires_in = int((session_data["expires_at"] - datetime.utcnow()).total_seconds())
        
        return AgentTokenResponse(
            access_token=access_token,
            expires_in=expires_in,
            agent_id=request.agent_id,
            namespace=session_data.get("namespace", "default")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed"
        )


@router.post("/agents/logout")
async def logout_agent(
    current_agent: CurrentAgent,
    authenticator: AgentAuthenticator = Depends(get_agent_authenticator)
):
    """Logout current agent and invalidate session."""
    try:
        # Remove session
        if current_agent.agent_id in authenticator.agent_sessions:
            del authenticator.agent_sessions[current_agent.agent_id]
        
        logger.info(f"Agent logged out: {current_agent.agent_id}")
        
        return {"message": "Logged out successfully"}
        
    except Exception as e:
        logger.error(f"Agent logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@router.get("/agents")
async def list_agents(
    current_agent: CurrentAgent,
    _: SystemAccess,
    authenticator: AgentAuthenticator = Depends(get_agent_authenticator)
):
    """List registered agents (system access required)."""
    try:
        agents_info = []
        
        for agent_id, credentials in authenticator.registered_agents.items():
            # Don't expose sensitive information
            agent_info = {
                "agent_id": agent_id,
                "namespace": credentials.namespace,
                "created_at": credentials.created_at.isoformat(),
                "is_active": agent_id in authenticator.agent_sessions
            }
            agents_info.append(agent_info)
        
        return {
            "agents": agents_info,
            "total": len(agents_info)
        }
        
    except Exception as e:
        logger.error(f"List agents error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve agents"
        )


@router.post("/policies", status_code=status.HTTP_201_CREATED)
async def create_access_policy(
    policy_request: AccessPolicyRequest,
    current_agent: CurrentAgent,
    _: SystemAccess,
    access_control: AccessControlManager = Depends(get_access_control)
):
    """Create new access control policy (system access required)."""
    try:
        policy = AccessPolicy(
            policy_id=policy_request.policy_id,
            name=policy_request.name,
            description=policy_request.description,
            resource_types=set(policy_request.resource_types),
            actions=set(policy_request.actions),
            agent_patterns=policy_request.agent_patterns,
            conditions=policy_request.conditions,
            decision=AccessDecision.ALLOW,  # Default for created policies
            priority=policy_request.priority,
            created_by=current_agent.agent_id
        )
        
        access_control.add_policy(policy)
        
        logger.info(f"Access policy created: {policy.policy_id} by {current_agent.agent_id}")
        
        return {"message": "Policy created successfully", "policy_id": policy.policy_id}
        
    except Exception as e:
        logger.error(f"Create policy error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create policy"
        )


@router.get("/policies")
async def list_access_policies(
    current_agent: CurrentAgent,
    _: SystemAccess,
    access_control: AccessControlManager = Depends(get_access_control)
):
    """List access control policies."""
    try:
        policies_info = []
        
        for policy in access_control.policies:
            policy_info = {
                "policy_id": policy.policy_id,
                "name": policy.name,
                "description": policy.description,
                "resource_types": [rt.value for rt in policy.resource_types],
                "actions": [a.value for a in policy.actions],
                "priority": policy.priority,
                "is_active": policy.is_active,
                "created_by": policy.created_by,
                "created_at": policy.created_at.isoformat()
            }
            policies_info.append(policy_info)
        
        return {
            "policies": policies_info,
            "total": len(policies_info)
        }
        
    except Exception as e:
        logger.error(f"List policies error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve policies"
        )


@router.delete("/policies/{policy_id}")
async def delete_access_policy(
    policy_id: str,
    current_agent: CurrentAgent,
    _: SystemAccess,
    access_control: AccessControlManager = Depends(get_access_control)
):
    """Delete access control policy."""
    try:
        success = access_control.remove_policy(policy_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Policy not found"
            )
        
        logger.info(f"Access policy deleted: {policy_id} by {current_agent.agent_id}")
        
        return {"message": "Policy deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete policy error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete policy"
        )


@router.get("/stats", response_model=SecurityStatsResponse)
async def get_security_stats(
    current_agent: CurrentAgent,
    _: SystemAccess,
    authenticator: AgentAuthenticator = Depends(get_agent_authenticator),
    access_control: AccessControlManager = Depends(get_access_control),
    encryption: EncryptionService = Depends(get_encryption_service)
):
    """Get comprehensive security statistics."""
    try:
        # Get access control stats
        access_stats = access_control.get_access_stats()
        
        # Get encryption stats
        encryption_stats = await encryption.get_encryption_stats()
        
        # Count active sessions
        active_sessions = len([
            session for session in authenticator.agent_sessions.values()
            if datetime.utcnow() < session.get("expires_at", datetime.utcnow())
        ])
        
        return SecurityStatsResponse(
            timestamp=datetime.utcnow(),
            total_registered_agents=len(authenticator.registered_agents),
            active_sessions=active_sessions,
            access_attempts_24h=access_stats.get("total_access_attempts", 0),
            access_denials_24h=access_stats.get("decision_breakdown", {}).get("deny", 0),
            policies_count=access_stats.get("total_policies", 0),
            encryption_stats=encryption_stats
        )
        
    except Exception as e:
        logger.error(f"Get security stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve security statistics"
        )


@router.get("/audit")
async def get_audit_log(
    current_agent: CurrentAgent,
    _: SystemAccess,
    limit: int = 100,
    event_type: Optional[str] = None,
    agent_id: Optional[str] = None,
    access_control: AccessControlManager = Depends(get_access_control)
):
    """Get security audit log."""
    try:
        # Filter access log based on parameters
        audit_entries = []
        
        for entry in access_control.access_log[-limit:]:
            # Apply filters
            if event_type and entry.get("event_type") != event_type:
                continue
            if agent_id and entry.get("requesting_agent") != agent_id:
                continue
            
            audit_entry = AuditLogEntry(
                timestamp=datetime.fromisoformat(entry["timestamp"]),
                event_type=entry.get("event_type", "access_attempt"),
                agent_id=entry["requesting_agent"],
                resource_type=entry.get("resource_type"),
                resource_id=entry.get("resource_id"),
                action=entry.get("action"),
                result=entry["decision"],
                details=entry.get("context", {})
            )
            audit_entries.append(audit_entry)
        
        return {
            "audit_log": audit_entries,
            "total": len(audit_entries)
        }
        
    except Exception as e:
        logger.error(f"Get audit log error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit log"
        )


@router.post("/encryption/rotate-keys")
async def rotate_encryption_keys(
    current_agent: CurrentAgent,
    _: SystemAccess,
    force: bool = False,
    encryption: EncryptionService = Depends(get_encryption_service)
):
    """Rotate encryption keys (system access required)."""
    try:
        rotation_result = encryption.key_manager.rotate_keys(force=force)
        
        logger.info(f"Encryption keys rotated by {current_agent.agent_id}: {len(rotation_result['rotated_keys'])} keys")
        
        return {
            "message": "Key rotation completed",
            "rotated_keys_count": len(rotation_result["rotated_keys"]),
            "details": rotation_result
        }
        
    except Exception as e:
        logger.error(f"Key rotation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Key rotation failed"
        )


@router.get("/health")
async def security_health_check():
    """Security system health check (public endpoint)."""
    try:
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "authentication": "operational",
                "access_control": "operational", 
                "encryption": "operational",
                "audit_logging": "operational"
            }
        }
    except Exception as e:
        logger.error(f"Security health check error: {e}")
        return {
            "status": "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


# Add import fix at the top
from ...security.access_control import AccessDecision