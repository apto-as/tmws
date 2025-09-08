"""
Agent Context Manager for Trinitas System
Manages agent switching and context management for multi-agent operations.
"""

import os
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AgentContextManager:
    """Agent context management for dynamic agent switching."""
    
    # Pre-defined Trinitas agents configuration
    TRINITAS_AGENTS = {
        "athena": {
            "full_id": "athena-conductor",
            "namespace": "trinitas",
            "capabilities": [
                "orchestration", 
                "workflow_automation",
                "resource_optimization",
                "parallel_execution",
                "task_delegation",
                "system_coordination"
            ],
            "access_level": "system",
            "display_name": "Athena - Harmonious Conductor"
        },
        "artemis": {
            "full_id": "artemis-optimizer",
            "namespace": "trinitas",
            "capabilities": [
                "performance_optimization",
                "code_quality",
                "technical_excellence",
                "algorithm_design",
                "efficiency_improvement",
                "best_practices"
            ],
            "access_level": "team",
            "display_name": "Artemis - Technical Perfectionist"
        },
        "hestia": {
            "full_id": "hestia-auditor",
            "namespace": "trinitas",
            "capabilities": [
                "security_analysis",
                "vulnerability_assessment",
                "risk_management",
                "threat_modeling",
                "compliance_verification",
                "audit_logging"
            ],
            "access_level": "system",
            "special_permissions": ["audit_all"],
            "display_name": "Hestia - Security Guardian"
        },
        "eris": {
            "full_id": "eris-coordinator",
            "namespace": "trinitas",
            "capabilities": [
                "tactical_planning",
                "team_coordination",
                "conflict_resolution",
                "workflow_orchestration",
                "collaboration",
                "balance_adjustment"
            ],
            "access_level": "team",
            "display_name": "Eris - Tactical Coordinator"
        },
        "hera": {
            "full_id": "hera-strategist",
            "namespace": "trinitas",
            "capabilities": [
                "strategic_planning",
                "architecture_design",
                "long_term_vision",
                "roadmap_development",
                "stakeholder_management",
                "user_experience"
            ],
            "access_level": "team",
            "display_name": "Hera - Strategic Commander"
        },
        "muses": {
            "full_id": "muses-documenter",
            "namespace": "trinitas",
            "capabilities": [
                "documentation",
                "knowledge_management",
                "specification_writing",
                "api_documentation",
                "archive_management",
                "content_structuring"
            ],
            "access_level": "public",
            "display_name": "Muses - Knowledge Architect"
        }
    }
    
    def __init__(self):
        """Initialize the agent context manager."""
        # Default agent from environment variable or fallback to athena
        default_agent_env = os.getenv("TMWS_AGENT_ID", "athena-conductor")
        self.default_agent = self._normalize_agent_id(default_agent_env)
        self.current_agent = self.default_agent
        self.agent_history: List[Dict[str, Any]] = []
        self.switch_count = 0
        self.session_start = datetime.utcnow()
        
        logger.info(f"AgentContextManager initialized with default agent: {self.current_agent}")
    
    def _normalize_agent_id(self, agent_id: str) -> str:
        """
        Normalize agent ID to handle both short names and full IDs.
        
        Args:
            agent_id: Either short name (e.g., "athena") or full ID (e.g., "athena-conductor")
            
        Returns:
            Full agent ID
        """
        # Check if it's a short name
        if agent_id in self.TRINITAS_AGENTS:
            return self.TRINITAS_AGENTS[agent_id]["full_id"]
        
        # Check if it's already a full ID
        for agent_info in self.TRINITAS_AGENTS.values():
            if agent_info["full_id"] == agent_id:
                return agent_id
        
        # Default to the input if not recognized
        logger.warning(f"Unknown agent ID: {agent_id}, using as-is")
        return agent_id
    
    def get_agent_info(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """
        Get agent information by name.
        
        Args:
            agent_name: Short agent name (e.g., "athena")
            
        Returns:
            Agent information dictionary or None if not found
        """
        return self.TRINITAS_AGENTS.get(agent_name)
    
    def switch_agent(self, agent_name: str) -> Dict[str, Any]:
        """
        Switch to a different agent context.
        
        Args:
            agent_name: Short agent name to switch to
            
        Returns:
            Result dictionary with success status and agent info
        """
        if agent_name not in self.TRINITAS_AGENTS:
            return {
                "success": False,
                "error": f"Unknown agent: {agent_name}",
                "available_agents": list(self.TRINITAS_AGENTS.keys())
            }
        
        agent_info = self.TRINITAS_AGENTS[agent_name]
        previous_agent = self.current_agent
        
        # Record history
        self.agent_history.append({
            "from_agent": previous_agent,
            "to_agent": agent_info["full_id"],
            "timestamp": datetime.utcnow().isoformat(),
            "switch_count": self.switch_count
        })
        
        # Update current context
        self.current_agent = agent_info["full_id"]
        self.switch_count += 1
        
        logger.info(f"Agent switched from {previous_agent} to {self.current_agent}")
        
        return {
            "success": True,
            "previous_agent": previous_agent,
            "current_agent": agent_name,
            "full_id": agent_info["full_id"],
            "capabilities": agent_info["capabilities"],
            "access_level": agent_info["access_level"],
            "display_name": agent_info.get("display_name", agent_name)
        }
    
    def get_current_agent_context(self) -> Dict[str, Any]:
        """
        Get the current agent context information.
        
        Returns:
            Current agent context dictionary
        """
        # Find current agent info
        current_info = None
        for name, info in self.TRINITAS_AGENTS.items():
            if info["full_id"] == self.current_agent:
                current_info = info
                break
        
        if not current_info:
            # Not a Trinitas agent, return basic info
            return {
                "current_agent": self.current_agent,
                "is_trinitas_agent": False,
                "history": self.agent_history[-5:] if self.agent_history else []
            }
        
        return {
            "current_agent": self.current_agent,
            "namespace": current_info["namespace"],
            "capabilities": current_info["capabilities"],
            "access_level": current_info["access_level"],
            "display_name": current_info.get("display_name", self.current_agent),
            "is_trinitas_agent": True,
            "switch_count": self.switch_count,
            "session_duration": (datetime.utcnow() - self.session_start).total_seconds(),
            "history": self.agent_history[-5:] if self.agent_history else []
        }
    
    def get_agent_by_full_id(self, full_id: str) -> Optional[Dict[str, Any]]:
        """
        Get agent information by full ID.
        
        Args:
            full_id: Full agent ID (e.g., "athena-conductor")
            
        Returns:
            Agent information or None if not found
        """
        for name, info in self.TRINITAS_AGENTS.items():
            if info["full_id"] == full_id:
                return {**info, "short_name": name}
        return None
    
    def list_available_agents(self) -> List[Dict[str, Any]]:
        """
        List all available Trinitas agents.
        
        Returns:
            List of agent information dictionaries
        """
        agents = []
        for name, info in self.TRINITAS_AGENTS.items():
            agents.append({
                "name": name,
                "full_id": info["full_id"],
                "display_name": info.get("display_name", name),
                "capabilities": info["capabilities"],
                "access_level": info["access_level"]
            })
        return agents
    
    def reset_to_default(self) -> str:
        """
        Reset to the default agent.
        
        Returns:
            The default agent ID
        """
        self.current_agent = self.default_agent
        logger.info(f"Reset to default agent: {self.default_agent}")
        return self.default_agent