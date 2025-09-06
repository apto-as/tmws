#!/usr/bin/env python3
"""
TMWS - Trinitas Memory & Workflow Service
Main application entry point.
"""

import logging
import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import uvicorn
from src.core.config import get_settings
from src.api.app import app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def main():
    """Main application entry point."""
    settings = get_settings()
    
    logger.info(f"Starting TMWS v{settings.api_version} in {settings.environment} mode")
    
    # Server configuration
    server_config = {
        "app": "main:app",
        "host": settings.api_host,
        "port": settings.api_port,
        "reload": settings.api_reload and settings.is_development,
        "log_level": settings.log_level.lower(),
        "access_log": not settings.is_production,  # Disable access log in production for performance
    }
    
    # Production-specific settings
    if settings.is_production:
        server_config.update({
            "workers": 4,  # Multiple workers for production
            "loop": "uvloop",  # Use uvloop for better performance
            "http": "httptools",  # Use httptools for better HTTP parsing
        })
        logger.info("Production configuration applied")
    
    # Development-specific settings
    if settings.is_development:
        server_config.update({
            "reload": True,
            "reload_dirs": ["src"],
            "reload_includes": ["*.py"],
            "log_config": None,  # Use default logging in development
        })
        logger.info("Development configuration applied")
    
    # Start the server
    try:
        uvicorn.run(**server_config)
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()