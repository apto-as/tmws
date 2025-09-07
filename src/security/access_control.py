"""
TMWS Advanced Access Control System
Hestia's Zero-Trust Agent Authorization Framework

This module provides comprehensive access control for multi-agent environments:
- Zero-trust security model (verify every request)
- Fine-grained resource permissions (RBAC + ABAC)
- Dynamic policy enforcement
- Cross-agent access auditing
- Resource isolation and compartmentalization
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Union, Any, Callable
from enum import Enum
import asyncio
import json
import hashlib
import logging
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class ResourceType(Enum):
    """Types of resources in TMWS."""
    MEMORY = "memory"
    TASK = "task"
    WORKFLOW = "workflow"
    AGENT = "agent"
    SYSTEM = "system"
    NAMESPACE = "namespace"
    AUDIT_LOG = "audit_log"
    LEARNING_PATTERN = "learning_pattern"


class ActionType(Enum):
    """Possible actions on resources."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    SHARE = "share"
    ASSIGN = "assign"
    APPROVE = "approve"
    AUDIT = "audit"


class AccessDecision(Enum):
    """Access control decision outcomes."""
    ALLOW = "allow"
    DENY = "deny"
    CONDITIONAL = "conditional"  # Allow with conditions/monitoring
    REQUIRE_APPROVAL = "require_approval"


@dataclass
class AccessContext:
    """Context information for access control decisions."""
    requesting_agent: str
    target_resource: str
    resource_type: ResourceType
    action: ActionType
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Additional context
    request_source: Optional[str] = None  # API, MCP, internal
    user_context: Optional[Dict[str, Any]] = None  # If user-initiated
    resource_metadata: Optional[Dict[str, Any]] = None
    session_info: Optional[Dict[str, Any]] = None


@dataclass
class AccessPolicy:
    """Access control policy definition."""
    policy_id: str
    name: str
    description: str
    
    # Target criteria
    resource_types: Set[ResourceType]
    actions: Set[ActionType]
    agent_patterns: List[str]  # Regex patterns for agent IDs
    
    # Policy logic
    conditions: List[Dict[str, Any]]  # Conditions for policy activation
    decision: AccessDecision
    priority: int = 100  # Higher number = higher priority
    
    # Metadata
    created_by: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    is_active: bool = True


class PolicyEngine(ABC):
    """Abstract base for policy evaluation engines."""
    
    @abstractmethod
    async def evaluate(self, context: AccessContext, policies: List[AccessPolicy]) -> AccessDecision:
        """Evaluate access request against policies."""
        pass


class RBACEngine(PolicyEngine):
    """Role-Based Access Control engine."""
    
    def __init__(self):
        self.role_permissions: Dict[str, Set[str]] = {
            "system_admin": {
                "memory:*:*", "task:*:*", "workflow:*:*", 
                "agent:*:*", "system:*:*", "namespace:*:*", "audit_log:*:*"
            },
            "agent_admin": {
                "memory:read:own", "memory:write:own", "memory:delete:own",
                "task:*:*", "workflow:*:*", "agent:read:*", "learning_pattern:*:own"
            },
            "standard_agent": {
                "memory:read:own", "memory:write:own", "memory:read:namespace",
                "task:create:*", "task:execute:assigned", "task:read:own",
                "workflow:read:own", "learning_pattern:read:*"
            },
            "readonly_agent": {
                "memory:read:own", "task:read:own", "workflow:read:own"
            }
        }
    
    async def evaluate(self, context: AccessContext, policies: List[AccessPolicy]) -> AccessDecision:
        """Evaluate using RBAC rules."""
        # Get agent role (simplified - in real implementation, would query database)
        agent_role = self._get_agent_role(context.requesting_agent)
        
        # Check if agent has required permission
        required_permission = f"{context.resource_type.value}:{context.action.value}:*"
        required_permission_specific = f"{context.resource_type.value}:{context.action.value}:own"
        
        permissions = self.role_permissions.get(agent_role, set())
        
        if required_permission in permissions or required_permission_specific in permissions:
            return AccessDecision.ALLOW
        
        return AccessDecision.DENY
    
    def _get_agent_role(self, agent_id: str) -> str:
        """Get agent role (placeholder implementation)."""
        # In real implementation, this would query agent database
        if agent_id.endswith("-admin"):
            return "system_admin"
        elif agent_id.startswith("system-"):
            return "agent_admin"
        else:
            return "standard_agent"


class ABACEngine(PolicyEngine):
    """Attribute-Based Access Control engine."""
    
    def __init__(self):
        self.attribute_evaluators: Dict[str, Callable] = {
            "time_of_day": self._evaluate_time_of_day,
            "agent_namespace": self._evaluate_agent_namespace,
            "resource_owner": self._evaluate_resource_owner,
            "data_classification": self._evaluate_data_classification,
            "request_frequency": self._evaluate_request_frequency
        }
        
        self.request_history: Dict[str, List[datetime]] = {}
    
    async def evaluate(self, context: AccessContext, policies: List[AccessPolicy]) -> AccessDecision:
        """Evaluate using attribute-based rules."""
        for policy in sorted(policies, key=lambda p: p.priority, reverse=True):
            if not policy.is_active:
                continue
            
            # Check if policy applies to this context
            if not self._policy_applies(policy, context):
                continue
            
            # Evaluate policy conditions
            if await self._evaluate_conditions(policy.conditions, context):
                logger.info(f"Policy {policy.policy_id} matched for {context.requesting_agent}")
                return policy.decision
        
        # Default deny
        return AccessDecision.DENY
    
    def _policy_applies(self, policy: AccessPolicy, context: AccessContext) -> bool:
        """Check if policy applies to the given context."""
        # Check resource type
        if context.resource_type not in policy.resource_types:
            return False
        
        # Check action
        if context.action not in policy.actions:
            return False
        
        # Check agent patterns
        import re
        for pattern in policy.agent_patterns:
            if re.match(pattern, context.requesting_agent):
                return True
        
        return False
    
    async def _evaluate_conditions(self, conditions: List[Dict[str, Any]], context: AccessContext) -> bool:
        """Evaluate policy conditions."""
        if not conditions:
            return True  # No conditions = always applies
        
        for condition in conditions:
            condition_type = condition.get("type")
            if condition_type not in self.attribute_evaluators:
                logger.warning(f"Unknown condition type: {condition_type}")
                continue
            
            evaluator = self.attribute_evaluators[condition_type]
            if not await evaluator(condition, context):
                return False  # AND logic - all conditions must pass
        
        return True
    
    async def _evaluate_time_of_day(self, condition: Dict[str, Any], context: AccessContext) -> bool:
        """Evaluate time-of-day condition."""
        start_hour = condition.get("start_hour", 0)
        end_hour = condition.get("end_hour", 24)
        current_hour = context.timestamp.hour
        
        return start_hour <= current_hour < end_hour
    
    async def _evaluate_agent_namespace(self, condition: Dict[str, Any], context: AccessContext) -> bool:
        """Evaluate agent namespace condition."""
        allowed_namespaces = condition.get("allowed_namespaces", [])
        agent_namespace = context.requesting_agent.split("-")[0]  # Simplified
        
        return agent_namespace in allowed_namespaces
    
    async def _evaluate_resource_owner(self, condition: Dict[str, Any], context: AccessContext) -> bool:
        """Evaluate resource ownership condition."""
        require_ownership = condition.get("require_ownership", False)
        if not require_ownership:
            return True
        
        # Check if agent owns the resource
        resource_metadata = context.resource_metadata or {}
        resource_owner = resource_metadata.get("agent_id", resource_metadata.get("owner"))
        
        return resource_owner == context.requesting_agent
    
    async def _evaluate_data_classification(self, condition: Dict[str, Any], context: AccessContext) -> bool:
        """Evaluate data classification condition."""
        max_classification = condition.get("max_classification", "confidential")
        resource_metadata = context.resource_metadata or {}
        resource_classification = resource_metadata.get("classification", "internal")
        
        classification_levels = {
            "public": 0,
            "internal": 1, 
            "confidential": 2,
            "restricted": 3,
            "top_secret": 4
        }
        
        max_level = classification_levels.get(max_classification, 1)
        resource_level = classification_levels.get(resource_classification, 1)
        
        return resource_level <= max_level
    
    async def _evaluate_request_frequency(self, condition: Dict[str, Any], context: AccessContext) -> bool:
        """Evaluate request frequency condition."""
        max_requests = condition.get("max_requests_per_hour", 100)
        agent_id = context.requesting_agent
        
        # Track request history
        if agent_id not in self.request_history:
            self.request_history[agent_id] = []
        
        # Clean old requests (older than 1 hour)
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        self.request_history[agent_id] = [
            req_time for req_time in self.request_history[agent_id]
            if req_time > cutoff_time
        ]
        
        # Add current request
        self.request_history[agent_id].append(context.timestamp)
        
        return len(self.request_history[agent_id]) <= max_requests


class CompositePolicyEngine(PolicyEngine):
    """Composite engine that combines multiple policy engines."""
    
    def __init__(self, engines: List[PolicyEngine]):
        self.engines = engines
    
    async def evaluate(self, context: AccessContext, policies: List[AccessPolicy]) -> AccessDecision:
        """Evaluate using all engines, apply strictest decision."""
        decisions = []
        
        for engine in self.engines:
            try:
                decision = await engine.evaluate(context, policies)
                decisions.append(decision)
            except Exception as e:
                logger.error(f"Policy engine error: {e}")
                decisions.append(AccessDecision.DENY)  # Fail closed
        
        # Apply strictest decision
        if AccessDecision.DENY in decisions:
            return AccessDecision.DENY
        elif AccessDecision.REQUIRE_APPROVAL in decisions:
            return AccessDecision.REQUIRE_APPROVAL
        elif AccessDecision.CONDITIONAL in decisions:
            return AccessDecision.CONDITIONAL
        else:
            return AccessDecision.ALLOW


class AccessControlManager:
    """Main access control orchestrator."""
    
    def __init__(self, policy_engine: PolicyEngine):
        self.policy_engine = policy_engine
        self.policies: List[AccessPolicy] = []
        self.access_log: List[Dict[str, Any]] = []
        self.approval_requests: Dict[str, Dict[str, Any]] = {}
        
        # Initialize default policies
        self._initialize_default_policies()
    
    def _initialize_default_policies(self):
        """Initialize default security policies."""
        # Self-access policy (agents can access their own resources)
        self_access_policy = AccessPolicy(
            policy_id="default_self_access",
            name="Self Resource Access",
            description="Allow agents to access their own resources",
            resource_types={ResourceType.MEMORY, ResourceType.TASK, ResourceType.LEARNING_PATTERN},
            actions={ActionType.READ, ActionType.UPDATE, ActionType.DELETE},
            agent_patterns=[".*"],
            conditions=[{"type": "resource_owner", "require_ownership": True}],
            decision=AccessDecision.ALLOW,
            priority=200,
            created_by="system"
        )
        
        # Namespace isolation policy
        namespace_policy = AccessPolicy(
            policy_id="namespace_isolation",
            name="Namespace Isolation",
            description="Restrict cross-namespace access",
            resource_types={ResourceType.MEMORY, ResourceType.TASK},
            actions={ActionType.READ, ActionType.UPDATE},
            agent_patterns=[".*"],
            conditions=[{"type": "agent_namespace", "allowed_namespaces": ["trinitas", "system"]}],
            decision=AccessDecision.CONDITIONAL,
            priority=150,
            created_by="system"
        )
        
        # Admin override policy
        admin_policy = AccessPolicy(
            policy_id="admin_override",
            name="Admin Override",
            description="System admins have full access",
            resource_types=set(ResourceType),
            actions=set(ActionType),
            agent_patterns=[r".*-admin$", r"^system-.*"],
            conditions=[],
            decision=AccessDecision.ALLOW,
            priority=300,
            created_by="system"
        )
        
        # Rate limiting policy
        rate_limit_policy = AccessPolicy(
            policy_id="rate_limiting",
            name="Request Rate Limiting",
            description="Limit request frequency per agent",
            resource_types=set(ResourceType),
            actions=set(ActionType),
            agent_patterns=[".*"],
            conditions=[{"type": "request_frequency", "max_requests_per_hour": 1000}],
            decision=AccessDecision.ALLOW,
            priority=50,
            created_by="system"
        )
        
        self.policies.extend([
            self_access_policy,
            namespace_policy,
            admin_policy,
            rate_limit_policy
        ])
    
    async def check_access(
        self,
        requesting_agent: str,
        resource_id: str,
        resource_type: ResourceType,
        action: ActionType,
        resource_metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Check if agent has access to perform action on resource.
        
        Returns:
            bool: True if access granted, False otherwise
            
        Raises:
            HTTPException: If access denied with specific error
        """
        context = AccessContext(
            requesting_agent=requesting_agent,
            target_resource=resource_id,
            resource_type=resource_type,
            action=action,
            resource_metadata=resource_metadata or {}
        )
        
        try:
            decision = await self.policy_engine.evaluate(context, self.policies)
            
            # Log access attempt
            await self._log_access_attempt(context, decision)
            
            if decision == AccessDecision.ALLOW:
                return True
            elif decision == AccessDecision.CONDITIONAL:
                # For now, treat conditional as allow with monitoring
                await self._setup_monitoring(context)
                return True
            elif decision == AccessDecision.REQUIRE_APPROVAL:
                await self._request_approval(context)
                raise HTTPException(
                    status_code=status.HTTP_202_ACCEPTED,
                    detail="Access request pending approval"
                )
            else:  # DENY
                await self._handle_access_denied(context)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: {action.value} on {resource_type.value}"
                )
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Access control error: {e}")
            # Fail closed - deny access on error
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access control system error - access denied"
            )
    
    async def _log_access_attempt(self, context: AccessContext, decision: AccessDecision):
        """Log access control decision for audit trail."""
        log_entry = {
            "timestamp": context.timestamp.isoformat(),
            "requesting_agent": context.requesting_agent,
            "resource_id": context.target_resource,
            "resource_type": context.resource_type.value,
            "action": context.action.value,
            "decision": decision.value,
            "context": {
                "request_source": context.request_source,
                "resource_metadata": context.resource_metadata
            }
        }
        
        self.access_log.append(log_entry)
        
        # Log security events for denied access
        if decision == AccessDecision.DENY:
            logger.warning(f"Access denied: {context.requesting_agent} -> {context.action.value} on {context.resource_type.value}:{context.target_resource}")
    
    async def _setup_monitoring(self, context: AccessContext):
        """Setup additional monitoring for conditional access."""
        logger.info(f"Setting up monitoring for conditional access: {context.requesting_agent}")
        # TODO: Implement monitoring logic
    
    async def _request_approval(self, context: AccessContext):
        """Create approval request for manual review."""
        approval_id = hashlib.sha256(f"{context.requesting_agent}:{context.target_resource}:{context.timestamp}".encode()).hexdigest()[:16]
        
        self.approval_requests[approval_id] = {
            "context": context,
            "status": "pending",
            "created_at": context.timestamp.isoformat(),
            "expires_at": (context.timestamp + timedelta(hours=24)).isoformat()
        }
        
        logger.info(f"Approval request created: {approval_id}")
    
    async def _handle_access_denied(self, context: AccessContext):
        """Handle denied access with additional security measures."""
        # Check for repeated denied attempts
        recent_denials = [
            entry for entry in self.access_log[-100:]  # Check last 100 entries
            if (entry["requesting_agent"] == context.requesting_agent and
                entry["decision"] == "deny" and
                datetime.fromisoformat(entry["timestamp"]) > datetime.utcnow() - timedelta(minutes=10))
        ]
        
        if len(recent_denials) >= 5:
            logger.error(f"Multiple access denials for {context.requesting_agent} - possible attack")
            # TODO: Trigger security alert or temporary lockout
    
    def add_policy(self, policy: AccessPolicy):
        """Add new access control policy."""
        self.policies.append(policy)
        logger.info(f"Added policy: {policy.policy_id}")
    
    def remove_policy(self, policy_id: str) -> bool:
        """Remove access control policy."""
        original_count = len(self.policies)
        self.policies = [p for p in self.policies if p.policy_id != policy_id]
        
        if len(self.policies) < original_count:
            logger.info(f"Removed policy: {policy_id}")
            return True
        return False
    
    def get_access_stats(self) -> Dict[str, Any]:
        """Get access control statistics."""
        recent_logs = [
            entry for entry in self.access_log
            if datetime.fromisoformat(entry["timestamp"]) > datetime.utcnow() - timedelta(hours=24)
        ]
        
        decision_counts = {}
        for entry in recent_logs:
            decision = entry["decision"]
            decision_counts[decision] = decision_counts.get(decision, 0) + 1
        
        return {
            "total_policies": len(self.policies),
            "total_access_attempts": len(recent_logs),
            "decision_breakdown": decision_counts,
            "pending_approvals": len(self.approval_requests),
            "unique_agents": len(set(entry["requesting_agent"] for entry in recent_logs))
        }


def create_access_control_manager() -> AccessControlManager:
    """Create configured access control manager."""
    # Create composite policy engine
    rbac_engine = RBACEngine()
    abac_engine = ABACEngine()
    composite_engine = CompositePolicyEngine([rbac_engine, abac_engine])
    
    return AccessControlManager(composite_engine)


__all__ = [
    "ResourceType",
    "ActionType",
    "AccessDecision",
    "AccessContext",
    "AccessPolicy",
    "PolicyEngine",
    "RBACEngine",
    "ABACEngine",
    "CompositePolicyEngine",
    "AccessControlManager",
    "create_access_control_manager"
]