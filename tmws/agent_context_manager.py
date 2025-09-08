"""
Agent Context Manager for Trinitas System
Manages agent switching and context management for multi-agent operations.
"""

import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class AgentContextManager:
    """Agent context management for dynamic agent switching with custom agent support."""
    
    # Pre-defined Trinitas agents configuration (immutable default)
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
            "display_name": "Athena - Harmonious Conductor",
            "is_system": True
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
            "display_name": "Artemis - Technical Perfectionist",
            "is_system": True
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
            "display_name": "Hestia - Security Guardian",
            "is_system": True
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
            "display_name": "Eris - Tactical Coordinator",
            "is_system": True
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
            "display_name": "Hera - Strategic Commander",
            "is_system": True
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
            "display_name": "Muses - Knowledge Architect",
            "is_system": True
        }
    }
    
    def __init__(self):
        """Initialize the agent context manager with support for custom agents."""
        # Initialize custom agents registry
        self.custom_agents: Dict[str, Dict[str, Any]] = {}
        
        # Combined registry (Trinitas + custom)
        self.all_agents = self.TRINITAS_AGENTS.copy()
        
        # Default agent from environment variable or fallback to athena
        default_agent_env = os.getenv("TMWS_AGENT_ID", "athena-conductor")
        self.default_agent = self._normalize_agent_id(default_agent_env)
        self.current_agent = self.default_agent
        self.agent_history: List[Dict[str, Any]] = []
        self.switch_count = 0
        self.session_start = datetime.now(timezone.utc)
        
        # Load custom agents from config if exists
        self._load_custom_agents_from_config()
        
        logger.info(f"AgentContextManager initialized with default agent: {self.current_agent}")
        logger.info(f"Available agents: {len(self.all_agents)} (Trinitas: 6, Custom: {len(self.custom_agents)})")
    
    def _load_custom_agents_from_config(self):
        """Load custom agents from configuration file if exists."""
        config_paths = [
            "custom_agents.json",
            os.path.expanduser("~/.tmws/custom_agents.json"),
            "/etc/tmws/custom_agents.json"
        ]
        
        for config_path in config_paths:
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r') as f:
                        import json
                        config = json.load(f)
                        if "custom_agents" in config:
                            for agent in config["custom_agents"]:
                                self.register_custom_agent(
                                    short_name=agent["name"],
                                    full_id=agent["full_id"],
                                    capabilities=agent.get("capabilities", []),
                                    namespace=agent.get("namespace", "custom"),
                                    display_name=agent.get("display_name"),
                                    metadata=agent.get("metadata")
                                )
                            logger.info(f"Loaded {len(config['custom_agents'])} custom agents from {config_path}")
                            break
                except Exception as e:
                    logger.warning(f"Failed to load custom agents from {config_path}: {e}")
    
    def register_custom_agent(self,
                             short_name: str,
                             full_id: str,
                             capabilities: List[str],
                             namespace: str = "custom",
                             display_name: Optional[str] = None,
                             access_level: str = "private",
                             metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Register a custom agent dynamically.
        
        Args:
            short_name: Short identifier for the agent
            full_id: Full unique identifier
            capabilities: List of agent capabilities
            namespace: Agent namespace
            display_name: Human-readable display name
            access_level: Access level (private, team, shared, public)
            metadata: Additional metadata
            
        Returns:
            Registration result with success status
        """
        import re
        
        # Validation
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9\-_]{1,31}$', short_name):
            return {
                "success": False,
                "error": "Invalid agent name. Must start with letter, alphanumeric with hyphens/underscores, 2-32 chars"
            }
        
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-_\.]{2,63}$', full_id):
            return {
                "success": False,
                "error": "Invalid full ID. Must be alphanumeric with hyphens/underscores/dots, 3-64 chars"
            }
        
        # Check for conflicts with Trinitas agents
        if short_name in self.TRINITAS_AGENTS:
            return {
                "success": False,
                "error": f"Name '{short_name}' conflicts with system agent. Please choose another name."
            }
        
        # Check for duplicate registration
        if short_name in self.custom_agents:
            return {
                "success": False,
                "error": f"Agent '{short_name}' is already registered. Use unregister first to update."
            }
        
        # Register the agent
        agent_config = {
            "full_id": full_id,
            "namespace": namespace,
            "capabilities": capabilities,
            "access_level": access_level,
            "display_name": display_name or f"Custom Agent - {short_name}",
            "is_system": False,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {}
        }
        
        self.custom_agents[short_name] = agent_config
        self.all_agents[short_name] = agent_config
        
        logger.info(f"Registered custom agent: {short_name} ({full_id})")
        
        return {
            "success": True,
            "message": f"Agent '{short_name}' registered successfully",
            "agent_info": agent_config
        }
    
    def unregister_custom_agent(self, short_name: str) -> Dict[str, Any]:
        """
        Unregister a custom agent.
        
        Args:
            short_name: Short name of the agent to unregister
            
        Returns:
            Result with success status
        """
        # Cannot unregister Trinitas agents
        if short_name in self.TRINITAS_AGENTS:
            return {
                "success": False,
                "error": f"Cannot unregister system agent '{short_name}'"
            }
        
        if short_name not in self.custom_agents:
            return {
                "success": False,
                "error": f"Agent '{short_name}' is not registered"
            }
        
        # Remove the agent
        agent_info = self.custom_agents.pop(short_name)
        self.all_agents.pop(short_name)
        
        # If current agent is the one being unregistered, switch to default
        if self.current_agent == agent_info["full_id"]:
            self.current_agent = self.default_agent
            logger.warning(f"Current agent was unregistered, switching to default: {self.default_agent}")
        
        logger.info(f"Unregistered custom agent: {short_name}")
        
        return {
            "success": True,
            "message": f"Agent '{short_name}' unregistered successfully",
            "removed_agent": agent_info
        }
    
    def save_custom_agents(self, filepath: Optional[str] = None) -> Dict[str, Any]:
        """
        Save custom agents to a configuration file.
        
        Args:
            filepath: Path to save config (default: custom_agents.json)
            
        Returns:
            Save result
        """
        import json
        
        if not filepath:
            filepath = "custom_agents.json"
        
        try:
            config = {
                "version": "1.0",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "custom_agents": list(self.custom_agents.values())
            }
            
            with open(filepath, 'w') as f:
                json.dump(config, f, indent=2)
            
            logger.info(f"Saved {len(self.custom_agents)} custom agents to {filepath}")
            
            return {
                "success": True,
                "message": f"Saved {len(self.custom_agents)} agents to {filepath}",
                "filepath": filepath
            }
        except Exception as e:
            logger.error(f"Failed to save custom agents: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _normalize_agent_id(self, agent_id: str) -> str:
        """
        Normalize agent ID to handle both short names and full IDs.
        
        Args:
            agent_id: Either short name or full ID
            
        Returns:
            Full agent ID
        """
        # Check in all agents (Trinitas + custom)
        if agent_id in self.all_agents:
            return self.all_agents[agent_id]["full_id"]
        
        # Check if it's already a full ID
        for agent_info in self.all_agents.values():
            if agent_info["full_id"] == agent_id:
                return agent_id
        
        # Default to the input if not recognized
        logger.warning(f"Unknown agent ID: {agent_id}, using as-is")
        return agent_id
    
    def get_agent_info(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """
        Get agent information by name.
        
        Args:
            agent_name: Short agent name
            
        Returns:
            Agent information dictionary or None if not found
        """
        return self.all_agents.get(agent_name)
    
    def switch_agent(self, agent_name: str) -> Dict[str, Any]:
        """
        Switch to a different agent context.
        
        Args:
            agent_name: Short agent name to switch to
            
        Returns:
            Result dictionary with success status and agent info
        """
        if agent_name not in self.all_agents:
            return {
                "success": False,
                "error": f"Unknown agent: {agent_name}",
                "available_agents": list(self.all_agents.keys())
            }
        
        agent_info = self.all_agents[agent_name]
        previous_agent = self.current_agent
        
        # Record history
        self.agent_history.append({
            "from_agent": previous_agent,
            "to_agent": agent_info["full_id"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
            "display_name": agent_info.get("display_name", agent_name),
            "is_system": agent_info.get("is_system", False)
        }
    
    def get_current_agent_context(self) -> Dict[str, Any]:
        """
        Get the current agent context information.
        
        Returns:
            Current agent context dictionary
        """
        # Find current agent info
        current_info = None
        for name, info in self.all_agents.items():
            if info["full_id"] == self.current_agent:
                current_info = info
                break
        
        if not current_info:
            # Not a known agent, return basic info
            return {
                "current_agent": self.current_agent,
                "is_trinitas_agent": False,
                "is_custom_agent": False,
                "history": self.agent_history[-5:] if self.agent_history else []
            }
        
        return {
            "current_agent": self.current_agent,
            "namespace": current_info["namespace"],
            "capabilities": current_info["capabilities"],
            "access_level": current_info["access_level"],
            "display_name": current_info.get("display_name", self.current_agent),
            "is_trinitas_agent": current_info.get("is_system", False),
            "is_custom_agent": not current_info.get("is_system", False),
            "switch_count": self.switch_count,
            "session_duration": (datetime.now(timezone.utc) - self.session_start).total_seconds(),
            "history": self.agent_history[-5:] if self.agent_history else []
        }
    
    def get_agent_by_full_id(self, full_id: str) -> Optional[Dict[str, Any]]:
        """
        Get agent information by full ID.
        
        Args:
            full_id: Full agent ID
            
        Returns:
            Agent information or None if not found
        """
        for name, info in self.all_agents.items():
            if info["full_id"] == full_id:
                return {**info, "short_name": name}
        return None
    
    def list_available_agents(self) -> List[Dict[str, Any]]:
        """
        List all available agents (Trinitas + custom).
        
        Returns:
            List of agent information dictionaries
        """
        agents = []
        for name, info in self.all_agents.items():
            agents.append({
                "name": name,
                "full_id": info["full_id"],
                "display_name": info.get("display_name", name),
                "capabilities": info["capabilities"],
                "access_level": info["access_level"],
                "is_system": info.get("is_system", False),
                "namespace": info["namespace"]
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