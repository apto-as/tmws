"""
Agent authentication and authorization for TMWS v2.0.
Provides secure multi-agent access control.
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import jwt
from passlib.context import CryptContext

from ..core.config import settings
from ..models.agent import Agent, AccessLevel


class AgentAuthService:
    """Service for agent authentication and authorization."""
    
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.secret_key = settings.TMWS_SECRET_KEY or "dev-secret-key-change-in-production"
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 60
        
    def generate_api_key(self) -> str:
        """Generate a secure API key for an agent."""
        return secrets.token_urlsafe(32)
    
    def hash_api_key(self, api_key: str) -> str:
        """Hash an API key for storage."""
        return self.pwd_context.hash(api_key)
    
    def verify_api_key(self, plain_api_key: str, hashed_api_key: str) -> bool:
        """Verify an API key against its hash."""
        return self.pwd_context.verify(plain_api_key, hashed_api_key)
    
    def create_access_token(
        self, 
        agent_id: str, 
        namespace: str = "default",
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a JWT access token for an agent."""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode = {
            "sub": agent_id,
            "namespace": namespace,
            "exp": expire,
            "iat": datetime.utcnow(),
        }
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_access_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode a JWT access token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.JWTError:
            return None
    
    def check_memory_access(
        self,
        agent_id: str,
        agent_namespace: str,
        memory_agent_id: str,
        memory_namespace: str,
        memory_access_level: AccessLevel,
        shared_agents: List[str] = None
    ) -> bool:
        """Check if an agent can access a specific memory."""
        
        # Owner always has access
        if agent_id == memory_agent_id:
            return True
        
        # Check access level
        if memory_access_level == AccessLevel.PUBLIC:
            return True
        elif memory_access_level == AccessLevel.SYSTEM:
            return True
        elif memory_access_level == AccessLevel.TEAM:
            # Same namespace means same team
            return agent_namespace == memory_namespace
        elif memory_access_level == AccessLevel.SHARED:
            # Check explicit sharing
            return shared_agents and agent_id in shared_agents
        else:  # PRIVATE
            return False
    
    def generate_agent_token(self, agent_id: str, api_key: str) -> Optional[str]:
        """Generate a token after validating agent credentials."""
        # This would check against database in production
        # For now, simple validation
        if not agent_id or not api_key:
            return None
        
        # Create token
        return self.create_access_token(agent_id)


class MemoryAccessControl:
    """Fine-grained access control for memories."""
    
    def __init__(self):
        self.permissions = {
            "read": 1,
            "write": 2,
            "share": 4,
            "delete": 8,
        }
    
    def has_permission(
        self,
        agent_id: str,
        memory_owner_id: str,
        required_permission: str,
        granted_permissions: int = 1  # Default read-only
    ) -> bool:
        """Check if agent has required permission on memory."""
        
        # Owner has all permissions
        if agent_id == memory_owner_id:
            return True
        
        # Check specific permission
        required_perm_value = self.permissions.get(required_permission, 0)
        return (granted_permissions & required_perm_value) == required_perm_value
    
    def grant_permissions(self, *permissions: str) -> int:
        """Create permission bitmask from permission names."""
        result = 0
        for perm in permissions:
            result |= self.permissions.get(perm, 0)
        return result


class RateLimiter:
    """Rate limiting for agent API calls."""
    
    def __init__(self):
        self.limits = {
            "default": {"requests": 1000, "window": 60},  # 1000 req/min
            "search": {"requests": 100, "window": 60},     # 100 searches/min
            "write": {"requests": 500, "window": 60},      # 500 writes/min
        }
        self.agent_requests = {}  # agent_id -> list of timestamps
    
    def check_rate_limit(
        self,
        agent_id: str,
        operation: str = "default"
    ) -> bool:
        """Check if agent is within rate limits."""
        
        limit_config = self.limits.get(operation, self.limits["default"])
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=limit_config["window"])
        
        # Get agent's request history
        if agent_id not in self.agent_requests:
            self.agent_requests[agent_id] = []
        
        # Clean old requests
        self.agent_requests[agent_id] = [
            ts for ts in self.agent_requests[agent_id]
            if ts > window_start
        ]
        
        # Check limit
        if len(self.agent_requests[agent_id]) >= limit_config["requests"]:
            return False
        
        # Record this request
        self.agent_requests[agent_id].append(now)
        return True
    
    def get_remaining_requests(
        self,
        agent_id: str,
        operation: str = "default"
    ) -> int:
        """Get remaining requests for agent in current window."""
        
        limit_config = self.limits.get(operation, self.limits["default"])
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=limit_config["window"])
        
        if agent_id not in self.agent_requests:
            return limit_config["requests"]
        
        # Count recent requests
        recent_requests = [
            ts for ts in self.agent_requests[agent_id]
            if ts > window_start
        ]
        
        return max(0, limit_config["requests"] - len(recent_requests))