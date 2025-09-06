#!/usr/bin/env python3
"""
TMWS API Server Entry Point
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import uvicorn
from src.core.config import get_settings
from src.api.app import create_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def main():
    """Main entry point for TMWS API server."""
    settings = get_settings()
    
    logger.info("=" * 50)
    logger.info("TMWS API Server Starting")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Vector Model: {settings.embedding_model}")
    logger.info(f"Vector Dimension: {settings.vector_dimension}")
    logger.info("=" * 50)
    
    # Create FastAPI app
    app = create_app()
    
    # Run server
    uvicorn.run(
        "src.api.app:app" if settings.environment == "development" else app,
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.environment == "development",
        log_level="info"
    )

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server failed to start: {e}")
        sys.exit(1)