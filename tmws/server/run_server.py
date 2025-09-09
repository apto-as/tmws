#!/usr/bin/env python3
"""
TMWS Server Runner
Starts the TMWS server with WebSocket support
"""

import asyncio
import sys
import uvicorn
from pathlib import Path
import argparse
import structlog

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tmws.core.config import Settings

logger = structlog.get_logger()


def main():
    """Main entry point for TMWS server."""
    parser = argparse.ArgumentParser(description="TMWS Server with WebSocket support")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--log-level", default="info", help="Log level")
    
    args = parser.parse_args()
    
    # Load settings
    settings = Settings()
    
    # Override with command line arguments
    host = args.host or settings.api_host
    port = args.port or settings.api_port
    
    logger.info("Starting TMWS Server",
               host=host,
               port=port,
               reload=args.reload)
    
    # Run the server
    uvicorn.run(
        "tmws.server.app:app",
        host=host,
        port=port,
        reload=args.reload,
        log_level=args.log_level.lower(),
        access_log=True
    )


if __name__ == "__main__":
    main()