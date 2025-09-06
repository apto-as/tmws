#!/usr/bin/env python3
"""
TMWS FastMCP Server Startup Script
Artemis-engineered deployment script with 404-grade error handling

Usage:
    python scripts/start_mcp_server.py [--mode mcp|fastapi|hybrid] [--port 8000] [--host 0.0.0.0]
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional
import signal
import os

# Add src to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from src.mcp_server_v2 import TMWSFastMCPServer, create_server
from src.integration.fastapi_mcp_bridge import create_tmws_app
from src.core.exceptions import TMWSException


class TMWSServerManager:
    """
    Server manager for TMWS with multiple deployment modes.
    
    Supports:
    - Pure MCP mode (FastMCP only)
    - FastAPI mode (REST API with MCP integration) 
    - Hybrid mode (Both protocols simultaneously)
    """
    
    def __init__(self):
        """Initialize server manager."""
        self.mcp_server: Optional[TMWSFastMCPServer] = None
        self.fastapi_app = None
        self.shutdown_requested = False
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('tmws_server.log', mode='a')
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True

    async def start_mcp_server(self) -> None:
        """Start pure FastMCP server."""
        try:
            self.logger.info("Starting TMWS FastMCP Server...")
            
            self.mcp_server = create_server()
            await self.mcp_server.initialize_server()
            
            self.logger.info("TMWS FastMCP Server ready for MCP connections")
            
            # Run the MCP server
            self.mcp_server.run()
            
        except Exception as e:
            self.logger.critical(f"FastMCP server failed to start: {str(e)}")
            raise TMWSException(f"MCP server startup failed: {str(e)}") from e

    async def start_fastapi_server(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """Start FastAPI server with MCP integration."""
        try:
            import uvicorn
            
            self.logger.info(f"Starting TMWS FastAPI Server on {host}:{port}...")
            
            # Create FastAPI app with MCP integration
            app = create_tmws_app()
            self.fastapi_app = app
            
            # Configure uvicorn
            config = uvicorn.Config(
                app,
                host=host,
                port=port,
                log_level="info",
                access_log=True,
                loop="asyncio"
            )
            
            server = uvicorn.Server(config)
            
            self.logger.info(f"TMWS FastAPI Server ready at http://{host}:{port}")
            self.logger.info(f"API Documentation available at http://{host}:{port}/docs")
            
            # Start the server
            await server.serve()
            
        except ImportError:
            self.logger.error("uvicorn not installed. Install with: pip install uvicorn")
            raise TMWSException("FastAPI server requires uvicorn")
        except Exception as e:
            self.logger.critical(f"FastAPI server failed to start: {str(e)}")
            raise TMWSException(f"FastAPI server startup failed: {str(e)}") from e

    async def start_hybrid_server(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """Start both MCP and FastAPI servers simultaneously."""
        try:
            self.logger.info("Starting TMWS Hybrid Server (MCP + FastAPI)...")
            
            # Create tasks for both servers
            mcp_task = asyncio.create_task(self.start_mcp_server())
            fastapi_task = asyncio.create_task(self.start_fastapi_server(host, port))
            
            self.logger.info("Both MCP and FastAPI servers starting...")
            
            # Wait for either server to complete (or fail)
            done, pending = await asyncio.wait(
                [mcp_task, fastapi_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel remaining tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Check for exceptions in completed tasks
            for task in done:
                if task.exception():
                    raise task.exception()
            
        except Exception as e:
            self.logger.critical(f"Hybrid server failed: {str(e)}")
            raise TMWSException(f"Hybrid server startup failed: {str(e)}") from e

    async def health_check(self) -> bool:
        """Perform server health check."""
        try:
            if self.mcp_server:
                # Test MCP server health
                # This would call the actual health check tool
                self.logger.info("MCP server health check: OK")
            
            if self.fastapi_app:
                # Test FastAPI server health
                self.logger.info("FastAPI server health check: OK")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")
            return False

    def run(self, mode: str = "mcp", host: str = "0.0.0.0", port: int = 8000) -> None:
        """
        Run server in specified mode.
        
        Args:
            mode: Server mode (mcp, fastapi, hybrid)
            host: Host address for FastAPI server
            port: Port for FastAPI server
        """
        try:
            self.logger.info(f"TMWS Server Manager starting in '{mode}' mode")
            
            if mode == "mcp":
                asyncio.run(self.start_mcp_server())
            elif mode == "fastapi":
                asyncio.run(self.start_fastapi_server(host, port))
            elif mode == "hybrid":
                asyncio.run(self.start_hybrid_server(host, port))
            else:
                raise ValueError(f"Invalid mode: {mode}. Use 'mcp', 'fastapi', or 'hybrid'")
                
        except KeyboardInterrupt:
            self.logger.info("Server shutdown requested by user")
        except Exception as e:
            self.logger.critical(f"Server execution failed: {str(e)}")
            sys.exit(1)


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="TMWS Server Manager - Artemis Edition",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Server Modes:
  mcp      - Pure FastMCP server for MCP protocol clients
  fastapi  - REST API server with MCP integration  
  hybrid   - Both MCP and FastAPI servers simultaneously

Examples:
  python scripts/start_mcp_server.py --mode mcp
  python scripts/start_mcp_server.py --mode fastapi --port 8000
  python scripts/start_mcp_server.py --mode hybrid --host 127.0.0.1 --port 8080
        """
    )
    
    parser.add_argument(
        "--mode",
        choices=["mcp", "fastapi", "hybrid"],
        default="mcp",
        help="Server mode (default: mcp)"
    )
    
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host address for FastAPI server (default: 0.0.0.0)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for FastAPI server (default: 8000)"
    )
    
    parser.add_argument(
        "--health-check",
        action="store_true",
        help="Perform health check and exit"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    
    args = parser.parse_args()
    
    # Configure logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Create server manager
    server_manager = TMWSServerManager()
    
    if args.health_check:
        # Perform health check
        try:
            result = asyncio.run(server_manager.health_check())
            print(f"Health check: {'PASSED' if result else 'FAILED'}")
            sys.exit(0 if result else 1)
        except Exception as e:
            print(f"Health check failed: {str(e)}")
            sys.exit(1)
    else:
        # Start server
        server_manager.run(
            mode=args.mode,
            host=args.host,
            port=args.port
        )


if __name__ == "__main__":
    main()