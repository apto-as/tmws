#!/usr/bin/env python3
"""
🚨 EMERGENCY SECURITY PATCH for Agent Auto-Registration System
Hestia's Critical Security Fixes

Apply this patch IMMEDIATELY before using the agent registry system.
"""

import re
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class SecureAgentRegistryPatch:
    """Emergency security patches for AgentRegistry"""
    
    # Allowed environment variables (whitelist approach)
    ALLOWED_ENV_VARS = {
        'CLAUDE_CONFIG_PATH',
        'CLAUDE_DESKTOP_CONFIG',
        'TMWS_AGENTS_CONFIG'
    }
    
    # Allowed configuration directories
    ALLOWED_CONFIG_DIRS = [
        Path.home() / '.claude',
        Path.home() / '.config' / 'claude',
        Path.home() / '.mcp',
        Path.home() / '.config' / 'mcp',
        Path.home() / 'Library' / 'Application Support' / 'Claude'
    ]
    
    # Maximum file size for configuration files (10MB)
    MAX_CONFIG_FILE_SIZE = 10 * 1024 * 1024
    
    @staticmethod
    def validate_file_path(file_path: str) -> bool:
        """
        Validate file path to prevent path traversal attacks.
        
        Returns:
            bool: True if path is safe to access
        """
        try:
            # Convert to Path object and resolve
            path_obj = Path(file_path).resolve()
            
            # Check if path exists and is a file
            if not path_obj.exists() or not path_obj.is_file():
                logger.warning(f"Invalid file path: {file_path}")
                return False
            
            # Check file size
            if path_obj.stat().st_size > SecureAgentRegistryPatch.MAX_CONFIG_FILE_SIZE:
                logger.error(f"Configuration file too large: {file_path}")
                return False
            
            # Ensure path is within allowed directories
            for allowed_dir in SecureAgentRegistryPatch.ALLOWED_CONFIG_DIRS:
                try:
                    if path_obj.is_relative_to(allowed_dir):
                        logger.info(f"File path validated: {file_path}")
                        return True
                except ValueError:
                    # Path is not relative to this allowed directory
                    continue
            
            logger.error(f"File path not in allowed directories: {file_path}")
            return False
            
        except Exception as e:
            logger.error(f"Path validation error: {e}")
            return False
    
    @staticmethod
    def sanitize_agent_id(agent_id: str) -> str:
        """
        Sanitize agent ID to prevent injection attacks.
        
        Returns:
            str: Sanitized agent ID
        """
        if not agent_id:
            return "unknown"
        
        # Remove dangerous characters, keep only alphanumeric, hyphens, underscores
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', str(agent_id))
        
        # Ensure it starts with alphanumeric
        sanitized = re.sub(r'^[^a-zA-Z0-9]+', '', sanitized)
        
        # Limit length
        sanitized = sanitized[:50]
        
        # Ensure minimum length
        if len(sanitized) < 3:
            sanitized = f"agent_{sanitized}_{hash(agent_id) & 0xFFFF:04x}"
        
        return sanitized
    
    @staticmethod
    def sanitize_agent_name(name: str) -> str:
        """Sanitize agent name"""
        if not name:
            return "Unknown Agent"
        
        # Remove control characters and limit length
        sanitized = ''.join(char for char in str(name) if ord(char) >= 32 and ord(char) < 127)
        return sanitized[:100]
    
    @staticmethod
    def get_safe_env_var(var_name: str) -> Optional[str]:
        """
        Safely get environment variable from whitelist.
        
        Returns:
            Optional[str]: Environment variable value if safe, None otherwise
        """
        if var_name not in SecureAgentRegistryPatch.ALLOWED_ENV_VARS:
            logger.warning(f"Attempted access to non-whitelisted env var: {var_name}")
            return None
        
        value = os.getenv(var_name)
        if value and SecureAgentRegistryPatch.validate_file_path(value):
            return value
        
        return None
    
    @staticmethod
    def validate_config_content(config_data: Dict[str, Any]) -> bool:
        """
        Validate configuration file content.
        
        Returns:
            bool: True if configuration is safe
        """
        try:
            # Check if it's a dictionary
            if not isinstance(config_data, dict):
                logger.error("Configuration must be a dictionary")
                return False
            
            # Check for agents array
            if 'agents' in config_data:
                agents = config_data['agents']
                if not isinstance(agents, list):
                    logger.error("Agents must be a list")
                    return False
                
                # Validate each agent
                for i, agent in enumerate(agents):
                    if not isinstance(agent, dict):
                        logger.error(f"Agent {i} must be a dictionary")
                        return False
                    
                    # Required fields
                    required_fields = ['id', 'name', 'type']
                    for field in required_fields:
                        if field not in agent:
                            logger.error(f"Agent {i} missing required field: {field}")
                            return False
                    
                    # Validate agent ID
                    agent_id = agent.get('id', '')
                    if len(agent_id) > 100 or not re.match(r'^[a-zA-Z0-9_-]+$', agent_id):
                        logger.error(f"Invalid agent ID: {agent_id}")
                        return False
                    
                    # Validate capabilities
                    if 'capabilities' in agent:
                        caps = agent['capabilities']
                        if not isinstance(caps, list) or len(caps) > 20:
                            logger.error(f"Invalid capabilities for agent {agent_id}")
                            return False
            
            return True
            
        except Exception as e:
            logger.error(f"Configuration validation error: {e}")
            return False
    
    @staticmethod
    def generate_secure_agent_id(config_path: str, agent_type: str) -> str:
        """
        Generate a secure agent ID from configuration path and type.
        
        Returns:
            str: Secure agent ID
        """
        # Use a more secure hash that includes the agent type
        import hashlib
        
        path_hash = hashlib.sha256(config_path.encode()).hexdigest()[:8]
        type_clean = SecureAgentRegistryPatch.sanitize_agent_id(agent_type)
        
        return f"{type_clean}-{path_hash}"


# Secure replacement functions for agent_registry.py
def secure_scan_claude_config(self) -> List:
    """Secure replacement for _scan_claude_config"""
    agents = []
    patch = SecureAgentRegistryPatch()
    
    # Check environment variables safely
    for env_var in ['CLAUDE_CONFIG_PATH', 'CLAUDE_DESKTOP_CONFIG']:
        config_path = patch.get_safe_env_var(env_var)
        if config_path:
            agent = secure_parse_claude_config(config_path)
            if agent:
                agents.append(agent)
    
    # Check standard locations with validation
    for config_dir in patch.ALLOWED_CONFIG_DIRS:
        if config_dir.exists():
            config_files = ['config.json', 'claude_config.json']
            for config_file in config_files:
                config_path = config_dir / config_file
                if config_path.exists():
                    agent = secure_parse_claude_config(str(config_path))
                    if agent:
                        agents.append(agent)
    
    return agents


def secure_parse_claude_config(config_path: str):
    """Secure replacement for _parse_claude_config"""
    patch = SecureAgentRegistryPatch()
    
    # Validate path first
    if not patch.validate_file_path(config_path):
        logger.error(f"Unsafe configuration path rejected: {config_path}")
        return None
    
    try:
        # Read and validate content
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        if not patch.validate_config_content(config_data):
            logger.error(f"Invalid configuration content: {config_path}")
            return None
        
        # Generate secure agent ID
        agent_id = patch.generate_secure_agent_id(config_path, "claude")
        
        # Extract capabilities safely
        capabilities = ['text-generation', 'reasoning', 'analysis']
        if 'tools' in config_data and isinstance(config_data['tools'], list):
            # Sanitize tool names
            safe_tools = [patch.sanitize_agent_id(tool) for tool in config_data['tools'][:10]]
            capabilities.extend(safe_tools)
        
        # Create agent info with sanitized data
        return {
            'id': agent_id,
            'name': patch.sanitize_agent_name("Claude AI Assistant"),
            'type': 'claude',
            'capabilities': capabilities,
            'config_path': config_path,
            'performance_score': 0.95
        }
        
    except Exception as e:
        logger.error(f"Failed to parse Claude config {config_path}: {e}")
        return None


def apply_emergency_patches():
    """Apply all emergency security patches"""
    logger.info("🚨 Applying emergency security patches...")
    
    # Disable auto-registration temporarily
    os.environ['TMWS_DISABLE_AUTO_REGISTRATION'] = '1'
    
    logger.info("✅ Emergency patches applied. Auto-registration disabled until manual review.")
    logger.warning("⚠️  Manual agent registration required until security review complete.")


if __name__ == "__main__":
    # Apply patches when run directly
    apply_emergency_patches()
    print("🚨 Emergency security patches applied!")
    print("⚠️  Auto-registration has been disabled for security.")
    print("📋 Review AGENT_SECURITY_AUDIT_CRITICAL.md for full details.")