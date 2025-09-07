#!/usr/bin/env python3
"""
🛡️ SECURE AGENT REGISTRY IMPLEMENTATION
Hestia's Hardened Agent Registration System

This replaces the vulnerable parts of agent_registry.py with secure implementations.
Apply these changes to fix critical security vulnerabilities.
"""

import os
import json
import re
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class SecureAgentRegistryMixin:
    """Secure implementations to replace vulnerable methods"""
    
    # Security configuration
    ALLOWED_CONFIG_DIRS = [
        Path.home() / '.claude',
        Path.home() / '.config' / 'claude',
        Path.home() / '.mcp',
        Path.home() / '.config' / 'mcp',
        Path.home() / 'Library' / 'Application Support' / 'Claude'
    ]
    
    ALLOWED_ENV_VARS = {
        'CLAUDE_CONFIG_PATH',
        'CLAUDE_DESKTOP_CONFIG', 
        'TMWS_AGENTS_CONFIG'
    }
    
    MAX_CONFIG_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_AGENTS_PER_CONFIG = 50
    
    def _validate_file_path(self, file_path: str) -> bool:
        """
        🛡️ SECURITY FIX: Validate file path to prevent path traversal attacks
        
        Original vulnerability:
        - Direct os.path.exists() on user input
        - No path validation or sanitization
        
        Security improvements:
        - Path resolution and canonicalization
        - Whitelist of allowed directories
        - File size limits
        """
        try:
            path_obj = Path(file_path).resolve()
            
            # Check if file exists and is readable
            if not path_obj.exists() or not path_obj.is_file():
                logger.warning(f"Invalid file: {file_path}")
                return False
            
            # Check file size to prevent DoS
            if path_obj.stat().st_size > self.MAX_CONFIG_FILE_SIZE:
                logger.error(f"Config file too large: {file_path}")
                return False
            
            # Ensure path is within allowed directories
            for allowed_dir in self.ALLOWED_CONFIG_DIRS:
                try:
                    if path_obj.is_relative_to(allowed_dir):
                        logger.debug(f"File path validated: {file_path}")
                        return True
                except (ValueError, OSError):
                    continue
            
            logger.error(f"File path not in allowed directories: {file_path}")
            return False
            
        except Exception as e:
            logger.error(f"Path validation failed: {e}")
            return False
    
    def _sanitize_agent_id(self, agent_id: str) -> str:
        """
        🛡️ SECURITY FIX: Sanitize agent ID to prevent injection
        
        Original vulnerability:
        - Direct use of hash(config_path) 
        - No input validation on agent IDs
        - Potential for SQL injection or path manipulation
        """
        if not agent_id:
            return "unknown"
        
        # Remove dangerous characters
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', str(agent_id))
        
        # Ensure starts with alphanumeric
        sanitized = re.sub(r'^[^a-zA-Z0-9]+', '', sanitized)
        
        # Length limits
        sanitized = sanitized[:50]
        
        # Minimum length requirement
        if len(sanitized) < 3:
            secure_hash = hashlib.sha256(str(agent_id).encode()).hexdigest()[:8]
            sanitized = f"agent_{secure_hash}"
        
        return sanitized
    
    def _sanitize_string(self, value: str, max_length: int = 100) -> str:
        """Sanitize string inputs"""
        if not value:
            return "unknown"
        
        # Remove control characters, keep printable ASCII
        sanitized = ''.join(char for char in str(value) if 32 <= ord(char) < 127)
        return sanitized[:max_length].strip()
    
    def _get_safe_env_var(self, var_name: str) -> Optional[str]:
        """
        🛡️ SECURITY FIX: Safe environment variable access
        
        Original vulnerability:
        - Direct os.getenv() without validation
        - No whitelist of allowed variables
        """
        if var_name not in self.ALLOWED_ENV_VARS:
            logger.warning(f"Blocked access to env var: {var_name}")
            return None
        
        value = os.getenv(var_name)
        if value and self._validate_file_path(value):
            return value
        
        return None
    
    def _validate_config_content(self, config_data: Dict[str, Any]) -> bool:
        """
        🛡️ SECURITY FIX: Validate configuration file content
        
        Original vulnerability:
        - No content validation
        - Direct trust of JSON data
        """
        try:
            if not isinstance(config_data, dict):
                return False
            
            # Check agents section
            if 'agents' in config_data:
                agents = config_data['agents']
                
                if not isinstance(agents, list):
                    return False
                
                if len(agents) > self.MAX_AGENTS_PER_CONFIG:
                    logger.error(f"Too many agents in config: {len(agents)}")
                    return False
                
                # Validate each agent
                for agent in agents:
                    if not isinstance(agent, dict):
                        return False
                    
                    required_fields = ['id', 'name', 'type']
                    if not all(field in agent for field in required_fields):
                        return False
                    
                    # Validate agent ID format
                    agent_id = agent.get('id', '')
                    if not re.match(r'^[a-zA-Z0-9_-]{3,50}$', str(agent_id)):
                        return False
                    
                    # Validate capabilities list
                    if 'capabilities' in agent:
                        caps = agent['capabilities']
                        if not isinstance(caps, list) or len(caps) > 20:
                            return False
            
            return True
            
        except Exception as e:
            logger.error(f"Config validation error: {e}")
            return False
    
    def _secure_read_json_file(self, file_path: str) -> Optional[Dict]:
        """
        🛡️ SECURITY FIX: Secure JSON file reading
        
        Original vulnerability:
        - Direct file opening without validation
        - No size limits or content validation
        """
        try:
            # Validate path first
            if not self._validate_file_path(file_path):
                return None
            
            # Read with size limit
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read(self.MAX_CONFIG_FILE_SIZE)
                config_data = json.loads(content)
            
            # Validate content structure
            if not self._validate_config_content(config_data):
                logger.error(f"Invalid config content: {file_path}")
                return None
            
            return config_data
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error in {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"File read error for {file_path}: {e}")
            return None
    
    async def _secure_scan_claude_config(self) -> List:
        """
        🛡️ SECURITY FIX: Secure Claude configuration scanning
        
        Replaces the vulnerable _scan_claude_config method
        """
        agents = []
        
        # Check environment variables with validation
        for env_var in ['CLAUDE_CONFIG_PATH', 'CLAUDE_DESKTOP_CONFIG']:
            config_path = self._get_safe_env_var(env_var)
            if config_path:
                agent = await self._secure_parse_claude_config(config_path)
                if agent:
                    agents.append(agent)
        
        # Check standard locations with validation
        for config_dir in self.ALLOWED_CONFIG_DIRS:
            if config_dir.exists() and config_dir.is_dir():
                config_files = ['config.json', 'claude_config.json']
                for config_file in config_files:
                    config_path = config_dir / config_file
                    if config_path.exists():
                        agent = await self._secure_parse_claude_config(str(config_path))
                        if agent:
                            agents.append(agent)
        
        logger.info(f"Securely scanned Claude configs, found {len(agents)} agents")
        return agents
    
    async def _secure_parse_claude_config(self, config_path: str):
        """
        🛡️ SECURITY FIX: Secure Claude configuration parsing
        
        Replaces the vulnerable _parse_claude_config method
        """
        try:
            # Use secure file reading
            loop = asyncio.get_event_loop()
            config_data = await loop.run_in_executor(
                self._executor, self._secure_read_json_file, config_path
            )
            
            if not config_data:
                return None
            
            # Generate secure agent ID
            secure_id = self._generate_secure_agent_id(config_path, "claude")
            
            # Extract and sanitize capabilities
            capabilities = ['text-generation', 'reasoning', 'analysis']
            if 'tools' in config_data and isinstance(config_data['tools'], list):
                safe_tools = []
                for tool in config_data['tools'][:10]:  # Limit number of tools
                    safe_tool = self._sanitize_string(str(tool), 50)
                    if safe_tool and safe_tool not in safe_tools:
                        safe_tools.append(safe_tool)
                capabilities.extend(safe_tools)
            
            return AgentInfo(
                id=secure_id,
                name=self._sanitize_string("Claude AI Assistant"),
                type="claude",
                capabilities=capabilities,
                config_path=config_path,
                performance_score=0.95
            )
            
        except Exception as e:
            logger.error(f"Secure parse failed for {config_path}: {e}")
            return None
    
    def _generate_secure_agent_id(self, config_path: str, agent_type: str) -> str:
        """Generate cryptographically secure agent ID"""
        # Use SHA-256 instead of hash() for consistency across runs
        path_hash = hashlib.sha256(config_path.encode()).hexdigest()[:12]
        type_clean = self._sanitize_agent_id(agent_type)
        return f"{type_clean}-{path_hash}"
    
    async def _secure_scan_custom_configs(self) -> List:
        """
        🛡️ SECURITY FIX: Secure custom configuration scanning
        """
        agents = []
        
        # Use safe environment variable access
        tmws_config = self._get_safe_env_var('TMWS_AGENTS_CONFIG')
        if tmws_config:
            try:
                loop = asyncio.get_event_loop()
                config_data = await loop.run_in_executor(
                    self._executor, self._secure_read_json_file, tmws_config
                )
                
                if config_data and 'agents' in config_data:
                    for agent_config in config_data['agents']:
                        # Sanitize all agent data
                        agent_id = self._sanitize_agent_id(
                            agent_config.get('id', f"custom-{len(agents)}")
                        )
                        agent_name = self._sanitize_string(
                            agent_config.get('name', 'Custom Agent')
                        )
                        agent_type = self._sanitize_string(
                            agent_config.get('type', 'custom')
                        )
                        
                        # Validate and sanitize capabilities
                        capabilities = []
                        if 'capabilities' in agent_config:
                            caps = agent_config['capabilities']
                            if isinstance(caps, list):
                                for cap in caps[:10]:  # Limit capabilities
                                    safe_cap = self._sanitize_string(str(cap), 30)
                                    if safe_cap:
                                        capabilities.append(safe_cap)
                        
                        agent = AgentInfo(
                            id=agent_id,
                            name=agent_name,
                            type=agent_type,
                            capabilities=capabilities,
                            config_path=tmws_config,
                            performance_score=max(0.1, min(1.0, 
                                agent_config.get('performance_score', 0.80)
                            ))
                        )
                        agents.append(agent)
                        
            except Exception as e:
                logger.error(f"Secure custom config scan failed: {e}")
        
        return agents


# Instructions for applying the patch
PATCH_INSTRUCTIONS = """
🛡️ SECURE AGENT REGISTRY PATCH INSTRUCTIONS

1. IMMEDIATE ACTION:
   - Run: python EMERGENCY_SECURITY_PATCH.py
   - This will disable auto-registration until patches are applied

2. APPLY SECURITY FIXES:
   Replace these methods in tmws/core/agent_registry.py:
   
   Line 126: _scan_claude_config() → _secure_scan_claude_config()
   Line 154: _parse_claude_config() → _secure_parse_claude_config()  
   Line 239: _scan_custom_configs() → _secure_scan_custom_configs()
   Line 264: _read_json_file() → _secure_read_json_file()

3. ADD SECURITY METHODS:
   Copy all methods from SecureAgentRegistryMixin into AgentRegistry class

4. UPDATE ENVIRONMENT VARIABLE ACCESS:
   Replace all os.getenv() calls with _get_safe_env_var()

5. TESTING:
   - Run security tests
   - Verify path traversal is blocked
   - Test agent ID injection prevention

6. MONITORING:
   - Enable audit logging
   - Monitor for failed validation attempts
   - Set up alerts for security events

⚠️  DO NOT use the current system in production until patched!
"""

if __name__ == "__main__":
    print("🛡️ Secure Agent Registry Patch")
    print("=" * 50)
    print(PATCH_INSTRUCTIONS)