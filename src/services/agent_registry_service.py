"""
Agent Registry Service for TMWS v2.0
Secure automatic agent registration with environment detection.
"""

import os
import re
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from ..models.agent import Agent, AgentStatus, AccessLevel
from ..core.database import get_session
from ..core.exceptions import TMWSException

logger = logging.getLogger(__name__)


class AgentRegistryService:
    """Secure agent registry with automatic registration capabilities."""
    
    # Security: Whitelist of allowed environment variable patterns
    ALLOWED_ENV_PATTERNS = [
        r'^TMWS_AGENT_ID$',
        r'^MCP_AGENT_ID$',
        r'^CLAUDE_AGENT_ID$',
        r'^OPENAI_AGENT_ID$',
        r'^ANTHROPIC_AGENT_ID$',
    ]
    
    # Security: Agent ID validation pattern
    AGENT_ID_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9\-_\.]{2,63}$')
    
    # Agent type detection patterns
    AGENT_TYPE_PATTERNS = {
        'anthropic_llm': ['claude', 'anthropic'],
        'openai_llm': ['gpt', 'openai', 'chatgpt'],
        'google_llm': ['gemini', 'bard', 'palm'],
        'meta_llm': ['llama', 'meta'],
        'custom_agent': []  # Default
    }
    
    def __init__(self):
        self.session: Optional[AsyncSession] = None
        self.cached_agent_id: Optional[str] = None
        self.statistics: Dict[str, Any] = {
            'total_registrations': 0,
            'auto_registrations': 0,
            'failed_attempts': 0,
            'last_registration': None
        }
    
    async def initialize(self, session: AsyncSession = None):
        """Initialize the service with database session."""
        self.session = session or await get_session()
    
    async def detect_agent_from_environment(self) -> Optional[str]:
        """
        Securely detect agent ID from environment variables.
        
        Security measures:
        - Whitelist of allowed environment variables
        - Strict validation of agent ID format
        - No path traversal or injection possible
        """
        
        # Check cached value first
        if self.cached_agent_id:
            return self.cached_agent_id
        
        # Try each allowed environment variable pattern
        for pattern in self.ALLOWED_ENV_PATTERNS:
            pattern_re = re.compile(pattern)
            for env_key in os.environ:
                if pattern_re.match(env_key):
                    agent_id = os.environ.get(env_key, '').strip()
                    
                    # Validate agent ID format
                    if self._validate_agent_id(agent_id):
                        logger.info(f"Detected agent ID from {env_key}: {agent_id}")
                        self.cached_agent_id = agent_id
                        return agent_id
                    else:
                        logger.warning(f"Invalid agent ID format from {env_key}: {agent_id}")
        
        # Default fallback
        return None
    
    def _validate_agent_id(self, agent_id: str) -> bool:
        """
        Validate agent ID format for security.
        
        Rules:
        - 3-64 characters
        - Alphanumeric, hyphens, underscores, dots only
        - Must start with alphanumeric
        - No path traversal patterns
        - No SQL injection patterns
        """
        
        if not agent_id or len(agent_id) < 3 or len(agent_id) > 64:
            return False
        
        # Check against regex pattern
        if not self.AGENT_ID_PATTERN.match(agent_id):
            return False
        
        # Additional security checks
        dangerous_patterns = [
            '../', '..\\', '%2e%2e', '%252e',  # Path traversal
            ';', '--', '/*', '*/', 'union', 'select',  # SQL injection
            '<', '>', '"', "'", '&', '|', '$', '`',  # Command injection
            '\x00', '\n', '\r', '\t',  # Control characters
        ]
        
        agent_id_lower = agent_id.lower()
        for pattern in dangerous_patterns:
            if pattern in agent_id_lower:
                logger.warning(f"Dangerous pattern detected in agent_id: {pattern}")
                return False
        
        return True
    
    def _detect_agent_type(self, agent_id: str) -> str:
        """Detect agent type from agent ID."""
        
        agent_id_lower = agent_id.lower()
        
        for agent_type, patterns in self.AGENT_TYPE_PATTERNS.items():
            for pattern in patterns:
                if pattern in agent_id_lower:
                    return agent_type
        
        return 'custom_agent'
    
    def _generate_display_name(self, agent_id: str) -> str:
        """Generate a human-friendly display name from agent ID."""
        
        # Remove common prefixes/suffixes
        display = agent_id
        for prefix in ['agent-', 'ai-', 'bot-']:
            if display.lower().startswith(prefix):
                display = display[len(prefix):]
        
        # Convert to title case
        display = display.replace('-', ' ').replace('_', ' ')
        display = ' '.join(word.capitalize() for word in display.split())
        
        return display or f"Agent {agent_id[:8]}"
    
    async def ensure_agent(
        self,
        agent_id: str,
        capabilities: Optional[Dict[str, Any]] = None,
        namespace: str = "default",
        auto_create: bool = True
    ) -> Optional[Agent]:
        """
        Ensure agent exists, creating if necessary.
        
        Args:
            agent_id: Agent identifier
            capabilities: Optional capabilities to record
            namespace: Agent namespace
            auto_create: Whether to auto-create if not exists
        
        Returns:
            Agent instance or None if validation fails
        """
        
        # Validate agent ID
        if not self._validate_agent_id(agent_id):
            logger.error(f"Invalid agent ID: {agent_id}")
            self.statistics['failed_attempts'] += 1
            return None
        
        try:
            # Check if agent exists
            result = await self.session.execute(
                select(Agent).where(Agent.agent_id == agent_id)
            )
            agent = result.scalar_one_or_none()
            
            if agent:
                # Update existing agent
                agent.last_active_at = datetime.utcnow()
                if capabilities:
                    agent.capabilities.update(capabilities)
                await self.session.commit()
                logger.info(f"Updated existing agent: {agent_id}")
                
            elif auto_create:
                # Create new agent
                agent = Agent(
                    agent_id=agent_id,
                    display_name=self._generate_display_name(agent_id),
                    namespace=namespace,
                    agent_type=self._detect_agent_type(agent_id),
                    capabilities=capabilities or {},
                    status=AgentStatus.ACTIVE,
                    health_score=1.0,
                    default_access_level=AccessLevel.PRIVATE
                )
                
                self.session.add(agent)
                await self.session.commit()
                
                logger.info(f"Auto-registered new agent: {agent_id}")
                self.statistics['auto_registrations'] += 1
                self.statistics['total_registrations'] += 1
                self.statistics['last_registration'] = datetime.utcnow()
            else:
                logger.warning(f"Agent not found and auto-create disabled: {agent_id}")
                return None
            
            return agent
            
        except Exception as e:
            logger.error(f"Error ensuring agent {agent_id}: {e}")
            await self.session.rollback()
            self.statistics['failed_attempts'] += 1
            raise TMWSException(f"Failed to ensure agent: {e}")
    
    async def get_agent_statistics(self, agent_id: str) -> Dict[str, Any]:
        """Get detailed statistics for an agent."""
        
        if not self._validate_agent_id(agent_id):
            return {'error': 'Invalid agent ID'}
        
        try:
            # Get agent
            result = await self.session.execute(
                select(Agent).where(Agent.agent_id == agent_id)
            )
            agent = result.scalar_one_or_none()
            
            if not agent:
                return {'error': 'Agent not found'}
            
            # Calculate statistics
            stats = {
                'agent_id': agent.agent_id,
                'display_name': agent.display_name,
                'agent_type': agent.agent_type,
                'namespace': agent.namespace,
                'status': agent.status.value,
                'health_score': agent.health_score,
                'total_memories': agent.total_memories,
                'total_tasks': agent.total_tasks,
                'success_rate': agent.success_rate,
                'average_response_time_ms': agent.average_response_time_ms,
                'created_at': agent.created_at.isoformat() if agent.created_at else None,
                'last_active_at': agent.last_active_at.isoformat() if agent.last_active_at else None,
                'capabilities': agent.capabilities,
                'access_stats': {
                    'default_access_level': agent.default_access_level.value,
                    'total_accesses': getattr(agent, 'total_accesses', 0)
                }
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting statistics for {agent_id}: {e}")
            return {'error': str(e)}
    
    async def list_agents(
        self,
        namespace: Optional[str] = None,
        agent_type: Optional[str] = None,
        status: Optional[AgentStatus] = None,
        limit: int = 100
    ) -> List[Agent]:
        """List agents with optional filters."""
        
        query = select(Agent)
        
        if namespace:
            query = query.where(Agent.namespace == namespace)
        if agent_type:
            query = query.where(Agent.agent_type == agent_type)
        if status:
            query = query.where(Agent.status == status)
        
        query = query.limit(limit)
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def update_agent_capabilities(
        self,
        agent_id: str,
        capabilities: Dict[str, Any]
    ) -> bool:
        """Update agent capabilities."""
        
        if not self._validate_agent_id(agent_id):
            return False
        
        try:
            result = await self.session.execute(
                update(Agent)
                .where(Agent.agent_id == agent_id)
                .values(
                    capabilities=capabilities,
                    updated_at=datetime.utcnow()
                )
            )
            await self.session.commit()
            return result.rowcount > 0
            
        except Exception as e:
            logger.error(f"Error updating capabilities for {agent_id}: {e}")
            await self.session.rollback()
            return False
    
    async def get_registry_statistics(self) -> Dict[str, Any]:
        """Get overall registry statistics."""
        
        return {
            **self.statistics,
            'cached_agent_id': self.cached_agent_id,
            'active_agents': await self._count_active_agents(),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    async def _count_active_agents(self) -> int:
        """Count active agents."""
        
        try:
            from sqlalchemy import func
            result = await self.session.execute(
                select(func.count(Agent.id)).where(Agent.status == AgentStatus.ACTIVE)
            )
            return result.scalar() or 0
        except:
            return 0