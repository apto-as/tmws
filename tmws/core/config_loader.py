"""
Configuration Loader for TMWS Unified Server
Loads and merges configuration from YAML files and environment variables
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import yaml
from string import Template

logger = logging.getLogger(__name__)


class ConfigLoader:
    """
    Configuration loader with environment variable substitution
    Supports hierarchical configuration with overrides
    """
    
    @staticmethod
    def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Load configuration from YAML file with environment variable substitution
        
        Args:
            config_path: Path to configuration file (optional)
        
        Returns:
            Merged configuration dictionary
        """
        # Default configuration path
        if not config_path:
            config_path = os.environ.get(
                'TMWS_CONFIG_PATH',
                './config/unified_server.yaml'
            )
        
        config_file = Path(config_path)
        
        # Load base configuration
        if config_file.exists():
            logger.info(f"Loading configuration from {config_file}")
            config = ConfigLoader._load_yaml_with_env(config_file)
        else:
            logger.warning(f"Configuration file not found: {config_file}")
            config = ConfigLoader._get_default_config()
        
        # Apply environment-specific overrides
        environment = os.environ.get('TMWS_ENVIRONMENT', 'development')
        config = ConfigLoader._apply_environment_overrides(config, environment)
        
        # Apply direct environment variable overrides
        config = ConfigLoader._apply_env_overrides(config)
        
        return config
    
    @staticmethod
    def _load_yaml_with_env(file_path: Path) -> Dict[str, Any]:
        """Load YAML file with environment variable substitution"""
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Substitute environment variables using Template
        template = Template(content)
        
        # Get all environment variables
        env_vars = os.environ.copy()
        
        # Provide defaults for common variables
        defaults = {
            'TMWS_ENVIRONMENT': 'development',
            'TMWS_DB_HOST': 'localhost',
            'TMWS_DB_PORT': '5432',
            'TMWS_DB_NAME': 'tmws',
            'TMWS_DB_USER': 'tmws_user',
            'TMWS_DB_PASSWORD': 'tmws_password',
            'TMWS_SECRET_KEY': 'dev-secret-key-change-in-production',
            'REDIS_HOST': 'localhost',
            'REDIS_PORT': '6379',
            'LOG_LEVEL': 'INFO',
            'LOCAL_LLM_ENDPOINT': 'http://localhost:1234/v1',
            'LOCAL_LLM_MODEL': 'auto'
        }
        
        # Merge defaults with actual environment variables
        substitutions = {**defaults, **env_vars}
        
        # Perform substitution
        substituted_content = template.safe_substitute(substitutions)
        
        # Parse YAML
        return yaml.safe_load(substituted_content)
    
    @staticmethod
    def _get_default_config() -> Dict[str, Any]:
        """Get default configuration when no config file is found"""
        return {
            "server": {
                "name": "TMWS Unified Server",
                "version": "1.0.0",
                "environment": os.environ.get("TMWS_ENVIRONMENT", "development")
            },
            "protocols": {
                "mcp": {"enabled": True, "stdio_mode": True},
                "fastapi": {"enabled": True, "host": "0.0.0.0", "port": 8000}
            },
            "database": {
                "primary": "postgresql",
                "connection": {
                    "host": os.environ.get("TMWS_DB_HOST", "localhost"),
                    "port": int(os.environ.get("TMWS_DB_PORT", "5432")),
                    "database": os.environ.get("TMWS_DB_NAME", "tmws"),
                    "user": os.environ.get("TMWS_DB_USER", "tmws_user"),
                    "password": os.environ.get("TMWS_DB_PASSWORD", "tmws_password")
                }
            },
            "memory": {
                "cache_size_mb": 100,
                "persistence": True
            },
            "security": {
                "auth_enabled": False
            },
            "logging": {
                "level": os.environ.get("LOG_LEVEL", "INFO"),
                "format": "structured"
            },
            "tactical": {
                "enabled": True,
                "mode": "peacetime"
            }
        }
    
    @staticmethod
    def _apply_environment_overrides(config: Dict[str, Any], environment: str) -> Dict[str, Any]:
        """Apply environment-specific configuration overrides"""
        if environment == "production":
            # Production overrides
            config.setdefault("security", {})["auth_enabled"] = True
            config.setdefault("logging", {})["level"] = "WARNING"
            config.setdefault("protocols", {}).setdefault("fastapi", {})["auto_reload"] = False
            config.setdefault("development", {})["debug"] = False
            
        elif environment == "development":
            # Development overrides
            config.setdefault("security", {})["auth_enabled"] = False
            config.setdefault("logging", {})["level"] = "INFO"
            config.setdefault("protocols", {}).setdefault("fastapi", {})["auto_reload"] = True
            config.setdefault("development", {})["debug"] = True
        
        return config
    
    @staticmethod
    def _apply_env_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply direct environment variable overrides"""
        # FastAPI port override
        if "TMWS_API_PORT" in os.environ:
            config.setdefault("protocols", {}).setdefault("fastapi", {})["port"] = int(os.environ["TMWS_API_PORT"])
        
        # Auth override
        if "TMWS_AUTH_ENABLED" in os.environ:
            auth_value = os.environ["TMWS_AUTH_ENABLED"].lower()
            config.setdefault("security", {})["auth_enabled"] = auth_value in ("true", "1", "yes", "on")
        
        # MCP enable/disable
        if "TMWS_MCP_ENABLED" in os.environ:
            mcp_value = os.environ["TMWS_MCP_ENABLED"].lower()
            config.setdefault("protocols", {}).setdefault("mcp", {})["enabled"] = mcp_value in ("true", "1", "yes", "on")
        
        # Tactical mode
        if "TMWS_TACTICAL_MODE" in os.environ:
            config.setdefault("tactical", {})["mode"] = os.environ["TMWS_TACTICAL_MODE"]
        
        return config
    
    @staticmethod
    def merge_configs(*configs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge multiple configuration dictionaries
        Later configs override earlier ones
        """
        result = {}
        
        for config in configs:
            result = ConfigLoader._deep_merge(result, config)
        
        return result
    
    @staticmethod
    def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigLoader._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    @staticmethod
    def save_config(config: Dict[str, Any], path: str):
        """Save configuration to YAML file"""
        config_path = Path(path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        logger.info(f"Configuration saved to {config_path}")
    
    @staticmethod
    def validate_config(config: Dict[str, Any]) -> bool:
        """Validate configuration for required fields"""
        required_fields = [
            ("server", "name"),
            ("protocols", "mcp", "enabled"),
            ("protocols", "fastapi", "enabled"),
            ("database", "primary")
        ]
        
        for field_path in required_fields:
            current = config
            for field in field_path:
                if field not in current:
                    logger.error(f"Missing required configuration: {'.'.join(field_path)}")
                    return False
                current = current[field]
        
        # At least one protocol must be enabled
        if not (config["protocols"]["mcp"]["enabled"] or config["protocols"]["fastapi"]["enabled"]):
            logger.error("At least one protocol (MCP or FastAPI) must be enabled")
            return False
        
        return True