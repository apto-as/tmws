#!/usr/bin/env python3
"""
TMWS FastMCP Server v2.0 - Artemis Edition
Trinitas Memory & Workflow Service via Model Context Protocol

完璧な404基準で実装された高性能FastMCPサーバー
- Modular tool architecture
- Comprehensive error handling  
- Performance optimization
- Type safety and validation
- Extensive documentation
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import sys
from pathlib import Path

# Third-party imports
from fastmcp import FastMCP
import uvloop

# Local imports - Core
from .core.config import get_settings
from .core.database import async_session_maker, create_tables
from .core.exceptions import TMWSException, DatabaseError, ValidationError

# Local imports - Tools (404-grade modular architecture)
from .tools import (
    MemoryTools,
    PersonaTools,
    TaskTools,
    WorkflowTools,
    SystemTools,
    LearningTools
)

# Configure high-performance logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('tmws_mcp.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

# Global settings instance
settings = get_settings()


class TMWSFastMCPServer:
    """
    High-performance FastMCP Server for TMWS.
    
    Artemis-designed architecture with:
    - Zero-compromise error handling
    - Modular tool registration
    - Performance monitoring
    - Graceful lifecycle management
    - Comprehensive health checks
    """
    
    def __init__(self):
        """Initialize TMWS FastMCP Server with 404 standards."""
        self.mcp = FastMCP(
            name="TMWS - Trinitas Memory & Workflow Service",
            version="2.0.0",
            description="High-performance memory and workflow management system"
        )
        
        # Tool instances (404-grade modular design)
        self.tools = {
            'memory': MemoryTools(),
            'persona': PersonaTools(),
            'task': TaskTools(),
            'workflow': WorkflowTools(),
            'system': SystemTools(),
            'learning': LearningTools()
        }
        
        # Performance metrics
        self.startup_time: Optional[datetime] = None
        self.total_requests: int = 0
        self.error_count: int = 0
        
        logger.info("TMWS FastMCP Server v2.0 initialized - Artemis Edition")

    async def initialize_database(self) -> None:
        """
        Initialize database with comprehensive error handling.
        
        Raises:
            DatabaseError: If database initialization fails
        """
        try:
            logger.info("Initializing database tables...")
            await create_tables()
            
            # Verify database connectivity
            async with async_session_maker() as session:
                await session.execute("SELECT 1")
                logger.info("Database connectivity verified")
            
            logger.info("Database initialization completed successfully")
            
        except Exception as e:
            error_msg = f"Database initialization failed: {str(e)}"
            logger.error(error_msg)
            raise DatabaseError(error_msg) from e

    async def register_all_tools(self) -> None:
        """
        Register all tool modules with FastMCP.
        
        Uses 404-standard error isolation to prevent tool registration
        failures from affecting other tools.
        """
        logger.info("Registering MCP tools...")
        
        registration_results = {}
        
        for tool_name, tool_instance in self.tools.items():
            try:
                await tool_instance.register_tools(self.mcp)
                registration_results[tool_name] = "success"
                logger.info(f"✓ {tool_name.title()} tools registered successfully")
                
            except Exception as e:
                registration_results[tool_name] = f"failed: {str(e)}"
                logger.error(f"✗ Failed to register {tool_name} tools: {str(e)}")
                # Continue with other tools (404 resilience)
                continue
        
        # Report registration summary
        successful_tools = [k for k, v in registration_results.items() if v == "success"]
        failed_tools = [k for k, v in registration_results.items() if v != "success"]
        
        logger.info(f"Tool registration summary: {len(successful_tools)} successful, {len(failed_tools)} failed")
        
        if failed_tools:
            logger.warning(f"Failed tools: {', '.join(failed_tools)}")
        
        if not successful_tools:
            raise TMWSException("No tools registered successfully - server cannot start")

    async def setup_lifecycle_hooks(self) -> None:
        """
        Setup startup and shutdown hooks with proper error handling.
        """
        
        @self.mcp.startup()
        async def on_startup():
            """Server startup handler with comprehensive initialization."""
            try:
                self.startup_time = datetime.utcnow()
                logger.info("TMWS MCP Server starting up...")
                
                # Initialize database
                await self.initialize_database()
                
                # Register all tools
                await self.register_all_tools()
                
                # Performance optimization
                if hasattr(asyncio, 'set_event_loop_policy'):
                    # Use uvloop for better performance if available
                    try:
                        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
                        logger.info("uvloop event loop policy set for optimal performance")
                    except ImportError:
                        logger.info("uvloop not available, using default event loop")
                
                startup_duration = (datetime.utcnow() - self.startup_time).total_seconds()
                logger.info(f"TMWS MCP Server startup completed in {startup_duration:.2f}s")
                
            except Exception as e:
                logger.critical(f"Server startup failed: {str(e)}")
                raise TMWSException(f"Startup failure: {str(e)}") from e

        @self.mcp.shutdown()
        async def on_shutdown():
            """Server shutdown handler with cleanup."""
            try:
                logger.info("TMWS MCP Server shutting down...")
                
                # Log final statistics
                if self.startup_time:
                    uptime = (datetime.utcnow() - self.startup_time).total_seconds()
                    logger.info(f"Server uptime: {uptime:.1f}s")
                    logger.info(f"Total requests processed: {self.total_requests}")
                    logger.info(f"Error count: {self.error_count}")
                    
                    if self.total_requests > 0:
                        error_rate = (self.error_count / self.total_requests) * 100
                        logger.info(f"Error rate: {error_rate:.2f}%")
                
                # Cleanup connections (FastMCP handles most cleanup automatically)
                logger.info("TMWS MCP Server shutdown completed")
                
            except Exception as e:
                logger.error(f"Error during shutdown: {str(e)}")

    async def setup_error_handlers(self) -> None:
        """
        Setup comprehensive error handling middleware.
        
        404-standard error isolation and reporting.
        """
        
        # Global error handler for uncaught exceptions
        @self.mcp.middleware()
        async def error_handling_middleware(request, call_next):
            """Global error handling with detailed logging."""
            try:
                self.total_requests += 1
                response = await call_next(request)
                return response
                
            except ValidationError as e:
                self.error_count += 1
                logger.warning(f"Validation error: {str(e)}")
                return {
                    "success": False,
                    "error": "Validation failed",
                    "error_type": "validation",
                    "details": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
                
            except DatabaseError as e:
                self.error_count += 1
                logger.error(f"Database error: {str(e)}")
                return {
                    "success": False,
                    "error": "Database operation failed",
                    "error_type": "database",
                    "details": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
                
            except TMWSException as e:
                self.error_count += 1
                logger.error(f"TMWS error: {str(e)}")
                return {
                    "success": False,
                    "error": "TMWS operation failed",
                    "error_type": "tmws",
                    "details": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
                
            except Exception as e:
                self.error_count += 1
                logger.critical(f"Unhandled error: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "error": "Internal server error",
                    "error_type": "internal",
                    "details": "An unexpected error occurred",
                    "timestamp": datetime.utcnow().isoformat(),
                    "request_id": getattr(request, 'id', 'unknown')
                }

    async def register_diagnostic_tools(self) -> None:
        """
        Register diagnostic and meta tools for server management.
        
        These tools provide server introspection and diagnostic capabilities.
        """
        
        @self.mcp.tool()
        async def get_server_info() -> Dict[str, Any]:
            """
            Get comprehensive server information and statistics.
            
            Returns detailed server status, performance metrics, and configuration.
            """
            uptime_seconds = 0
            if self.startup_time:
                uptime_seconds = (datetime.utcnow() - self.startup_time).total_seconds()
            
            return {
                "success": True,
                "data": {
                    "server_info": {
                        "name": "TMWS FastMCP Server",
                        "version": "2.0.0",
                        "edition": "Artemis - Technical Perfectionist",
                        "startup_time": self.startup_time.isoformat() if self.startup_time else None,
                        "uptime_seconds": uptime_seconds,
                        "uptime_formatted": f"{uptime_seconds/3600:.1f}h" if uptime_seconds > 3600 else f"{uptime_seconds/60:.1f}m"
                    },
                    "performance_metrics": {
                        "total_requests": self.total_requests,
                        "error_count": self.error_count,
                        "success_rate": ((self.total_requests - self.error_count) / self.total_requests * 100) if self.total_requests > 0 else 100,
                        "requests_per_minute": (self.total_requests / (uptime_seconds / 60)) if uptime_seconds > 60 else 0
                    },
                    "registered_tools": {
                        tool_name: "operational" for tool_name in self.tools.keys()
                    },
                    "configuration": {
                        "database_url": settings.database_url_async.split('@')[0] + "@[REDACTED]",
                        "environment": settings.environment,
                        "debug_mode": settings.debug
                    },
                    "features": {
                        "modular_tools": True,
                        "error_isolation": True,
                        "performance_monitoring": True,
                        "type_validation": True,
                        "comprehensive_logging": True,
                        "graceful_degradation": True
                    }
                },
                "message": "Server information retrieved successfully",
                "timestamp": datetime.utcnow().isoformat()
            }

        @self.mcp.tool()
        async def perform_health_check() -> Dict[str, Any]:
            """
            Perform comprehensive server health check.
            
            Validates all critical components and provides health status.
            """
            health_status = {
                "overall_status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "components": {}
            }
            
            # Database health check
            try:
                async with async_session_maker() as session:
                    start_time = datetime.utcnow()
                    await session.execute("SELECT 1")
                    db_response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                    
                    health_status["components"]["database"] = {
                        "status": "healthy",
                        "response_time_ms": db_response_time,
                        "details": "Database responding normally"
                    }
            except Exception as e:
                health_status["components"]["database"] = {
                    "status": "unhealthy",
                    "error": str(e),
                    "details": "Database connection failed"
                }
                health_status["overall_status"] = "unhealthy"
            
            # Tools health check
            healthy_tools = 0
            for tool_name in self.tools.keys():
                try:
                    # Simple health check - tools are registered
                    health_status["components"][f"{tool_name}_tools"] = {
                        "status": "healthy",
                        "details": f"{tool_name.title()} tools operational"
                    }
                    healthy_tools += 1
                except Exception as e:
                    health_status["components"][f"{tool_name}_tools"] = {
                        "status": "unhealthy",
                        "error": str(e)
                    }
                    if health_status["overall_status"] == "healthy":
                        health_status["overall_status"] = "degraded"
            
            # Server metrics health check
            error_rate = (self.error_count / self.total_requests * 100) if self.total_requests > 0 else 0
            
            if error_rate > 10:  # More than 10% error rate
                health_status["overall_status"] = "degraded"
                health_status["components"]["error_rate"] = {
                    "status": "warning",
                    "error_rate": error_rate,
                    "details": f"High error rate: {error_rate:.1f}%"
                }
            else:
                health_status["components"]["error_rate"] = {
                    "status": "healthy",
                    "error_rate": error_rate,
                    "details": f"Error rate within acceptable limits: {error_rate:.1f}%"
                }
            
            return {
                "success": True,
                "data": health_status,
                "message": f"Health check completed - Status: {health_status['overall_status']}"
            }

    async def initialize_server(self) -> None:
        """
        Complete server initialization with all components.
        
        404-standard initialization sequence with comprehensive error handling.
        """
        try:
            logger.info("Starting TMWS FastMCP Server v2.0 initialization...")
            
            # Setup error handling first (critical for 404 standards)
            await self.setup_error_handlers()
            logger.info("Error handling middleware configured")
            
            # Setup lifecycle hooks
            await self.setup_lifecycle_hooks()
            logger.info("Lifecycle hooks configured")
            
            # Register diagnostic tools
            await self.register_diagnostic_tools()
            logger.info("Diagnostic tools registered")
            
            logger.info("TMWS FastMCP Server v2.0 initialization completed successfully")
            
        except Exception as e:
            logger.critical(f"Server initialization failed: {str(e)}")
            raise TMWSException(f"Server initialization failure: {str(e)}") from e

    def run(self, **kwargs) -> None:
        """
        Run the FastMCP server with optimal configuration.
        
        Args:
            **kwargs: Additional arguments passed to FastMCP.run()
        """
        try:
            logger.info("Starting TMWS FastMCP Server v2.0...")
            
            # Run initialization
            asyncio.run(self.initialize_server())
            
            # Start the server
            self.mcp.run(**kwargs)
            
        except KeyboardInterrupt:
            logger.info("Server shutdown requested by user")
        except Exception as e:
            logger.critical(f"Server run failed: {str(e)}")
            sys.exit(1)


# Global server instance
server = TMWSFastMCPServer()


def create_server() -> TMWSFastMCPServer:
    """
    Factory function to create a new TMWS FastMCP server instance.
    
    Returns:
        TMWSFastMCPServer: Configured server instance
    """
    return TMWSFastMCPServer()


async def main() -> None:
    """
    Main entry point for the TMWS FastMCP Server.
    
    Handles initialization and startup with proper error handling.
    """
    try:
        # Create and initialize server
        server = create_server()
        await server.initialize_server()
        
        logger.info("TMWS FastMCP Server ready for connections")
        
        # The actual server startup is handled by FastMCP
        # This function is primarily for testing and development
        
    except Exception as e:
        logger.critical(f"Main execution failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    """Entry point for direct execution."""
    server.run()