#!/usr/bin/env python3
"""
TMWS Unified Server - FastMCP + FastAPI統合実行サーバー
Strategic Architect Athena設計による優雅な統合実装

Single command startup: python -m tmws.unified_server
"""

import asyncio
import argparse
import logging
import signal
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
# FastAPI imports
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import uvicorn

# Security imports - Hestia's Protection
from src.security.middleware import SecurityMiddleware, get_security_middleware
from src.security.rate_limiter import RateLimiter
from src.security.audit_logger import get_audit_logger
import redis

# MCP imports (to be implemented)
from mcp import Server
from mcp.server import stdio
from mcp.types import Tool

# Local imports
from src.core.config import get_settings
from src.core.config_loader import ConfigLoader
from src.core.database import get_database
from src.core.unified_database import (
    initialize_unified_database,
    get_unified_db_session,
    get_unified_health_status,
    shutdown_unified_database,
    get_unified_db_manager
)
from src.api.app import create_app
from src.services.unified_memory_service import UnifiedMemoryService
from src.services.persona_service import PersonaService

# Tactical Coordination - Bellona's Command Center
from src.core.tactical_coordinator import create_tactical_coordinator


class TMWSUnifiedServer:
    """
    TMWS統合サーバー
    FastMCPとFastAPIを単一プロセスで実行する優雅な実装
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config = ConfigLoader.load_config(config_path)
        
        # Validate configuration
        if not ConfigLoader.validate_config(self.config):
            raise ValueError("Invalid configuration")
        
        self.logger = self._setup_logging()
        
        # Core components
        self.fastapi_app: Optional[FastAPI] = None
        self.mcp_server: Optional[Server] = None
        self.memory_service: Optional[UnifiedMemoryService] = None
        self.persona_service: Optional[PersonaService] = None
        
        # Security components - Hestia's Guardian System
        self.rate_limiter: Optional[RateLimiter] = None
        self.security_middleware: Optional[SecurityMiddleware] = None
        self.audit_logger = get_audit_logger()
        self.redis_client: Optional[redis.Redis] = None
        
        # Tactical Coordination - Bellona's Command System
        self.tactical_coordinator = create_tactical_coordinator()
        
        # Runtime state
        self.is_running = False
        self.tasks: list[asyncio.Task] = []
        
        self.logger.info("TMWS Unified Server initialized")
    
    
    def _setup_logging(self) -> logging.Logger:
        """ログシステムを設定"""
        log_config = self.config.get("logging", {})
        
        logging.basicConfig(
            level=getattr(logging, log_config.get("level", "INFO")),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        logger = logging.getLogger("tmws.unified_server")
        logger.info(f"Logging configured: level={log_config.get('level', 'INFO')}")
        
        return logger
    
    async def initialize_services(self):
        """共有サービスを初期化 - Unified Database Pool"""
        try:
            # Initialize unified database pool
            settings = get_settings()
            success = await initialize_unified_database()
            
            if not success:
                raise Exception("Failed to initialize unified database")
            
            self.logger.info("[TACTICAL] Unified database pool initialized")
            
            # Initialize Redis for rate limiting (optional)
            try:
                self.redis_client = redis.Redis(
                    host='localhost', port=6379, db=0,
                    decode_responses=True, socket_timeout=1
                )
                # Test connection
                await self.redis_client.ping()
                self.logger.info("Redis connected for enhanced rate limiting")
            except Exception as e:
                self.logger.warning(f"Redis not available, using in-memory rate limiting: {e}")
                self.redis_client = None
            
            # Initialize security services - Hestia's Guardian System
            self.rate_limiter = RateLimiter(self.redis_client)
            self.security_middleware = SecurityMiddleware(
                None,  # App will be set later
                rate_limiter=self.rate_limiter,
                audit_logger=self.audit_logger
            )
            
            self.logger.info("🛡️ Hestia's Security System initialized")
            
            # Memory service with unified database
            self.memory_service = UnifiedMemoryService()
            await self.memory_service.initialize()
            
            # Persona service with memory service
            self.persona_service = PersonaService(self.memory_service)
            
            self.logger.info("Shared services initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize services: {e}")
            raise
    
    def create_fastapi_app(self) -> FastAPI:
        """FastAPIアプリケーションを作成"""
        if not self.config["protocols"]["fastapi"]["enabled"]:
            return None
        
        # Use existing app creation logic
        app = create_app()
        
        # Add unified server specific middleware
        app.add_middleware(GZipMiddleware, minimum_size=1000)
        
        # Add health endpoint for unified server
        @app.get("/unified/health")
        async def unified_health():
            return {
                "status": "healthy",
                "server": "TMWS Unified",
                "protocols": {
                    "mcp": self.config["protocols"]["mcp"]["enabled"],
                    "fastapi": self.config["protocols"]["fastapi"]["enabled"]
                },
                "services": {
                    "memory": self.memory_service.is_healthy() if self.memory_service else False,
                    "persona": self.persona_service.is_healthy() if self.persona_service else False
                }
            }
        
        # Add configuration endpoint
        @app.get("/unified/config")
        async def get_configuration():
            # Return non-sensitive configuration
            safe_config = self.config.copy()
            # Remove sensitive information
            safe_config.pop("database", None)
            return safe_config
        
        # Tactical Coordination Endpoints - Bellona's Command Interface
        @app.get("/tactical/status")
        async def get_tactical_status():
            """Get comprehensive tactical status"""
            if self.tactical_coordinator:
                return self.tactical_coordinator.get_tactical_status()
            else:
                return {"error": "Tactical coordinator not initialized"}
        
        @app.post("/tactical/command")
        async def execute_tactical_command(command_data: dict):
            """Execute tactical command"""
            if not self.tactical_coordinator:
                return {"error": "Tactical coordinator not initialized"}
            
            command = command_data.get("command")
            params = command_data.get("params", {})
            
            if not command:
                return {"error": "Command not specified"}
            
            result = await self.tactical_coordinator.execute_tactical_command(command, params)
            return result
        
        @app.get("/tactical/health")
        async def get_tactical_health():
            """Get tactical health check"""
            if self.tactical_coordinator:
                result = await self.tactical_coordinator.execute_tactical_command("health_check")
                return result
            else:
                return {"error": "Tactical coordinator not initialized"}
        
        @app.get("/tactical/metrics")
        async def get_tactical_metrics():
            """Get detailed tactical metrics"""
            if self.tactical_coordinator:
                status = self.tactical_coordinator.get_tactical_status()
                return {
                    "tactical_mode": status["coordinator"]["mode"],
                    "operational_status": status["coordinator"]["status"],
                    "service_metrics": status["metrics"],
                    "incident_count": status["incidents"],
                    "last_incident": status["last_incident"]
                }
            else:
                return {"error": "Tactical coordinator not initialized"}
        
        self.logger.info("FastAPI application created with tactical endpoints")
        return app
    
    def create_mcp_server(self) -> Optional[Server]:
        """MCPサーバーを作成"""
        if not self.config["protocols"]["mcp"]["enabled"]:
            return None
        
        server = Server("tmws-unified")
        
        # Register MCP tools
        @server.list_tools()
        async def handle_list_tools() -> list[Tool]:
            """利用可能なツールをリスト"""
            return [
                Tool(
                    name="store_memory",
                    description="Store a memory item in TMWS",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "content": {"type": "string"},
                            "tags": {"type": "array", "items": {"type": "string"}},
                            "importance": {"type": "number", "minimum": 0, "maximum": 1}
                        },
                        "required": ["content"]
                    }
                ),
                Tool(
                    name="recall_memory",
                    description="Recall memories from TMWS",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "limit": {"type": "integer", "default": 10},
                            "semantic": {"type": "boolean", "default": False}
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="persona_execute",
                    description="Execute task with specific persona",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "persona": {"type": "string", "enum": ["athena", "artemis", "hestia", "bellona", "seshat"]},
                            "task": {"type": "string"}
                        },
                        "required": ["persona", "task"]
                    }
                )
            ]
        
        @server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> list[dict]:
            """ツール実行ハンドラー"""
            try:
                if name == "store_memory":
                    result = await self.memory_service.store_memory(
                        content=arguments["content"],
                        tags=arguments.get("tags", []),
                        importance=arguments.get("importance", 0.5)
                    )
                    return [{"type": "text", "text": f"Memory stored with ID: {result['id']}"}]
                
                elif name == "recall_memory":
                    results = await self.memory_service.recall_memories(
                        query=arguments["query"],
                        limit=arguments.get("limit", 10),
                        semantic=arguments.get("semantic", False)
                    )
                    return [{"type": "text", "text": f"Found {len(results)} memories"}]
                
                elif name == "persona_execute":
                    result = await self.persona_service.execute_with_persona(
                        persona=arguments["persona"],
                        task=arguments["task"]
                    )
                    return [{"type": "text", "text": result}]
                
                else:
                    raise ValueError(f"Unknown tool: {name}")
                    
            except Exception as e:
                self.logger.error(f"Tool execution failed: {e}")
                return [{"type": "text", "text": f"Error: {str(e)}"}]
        
        self.logger.info("MCP server created with tools registered")
        return server
    
    async def start_fastapi(self):
        """FastAPIサーバーを起動"""
        if not self.fastapi_app:
            return
        
        config = self.config["protocols"]["fastapi"]
        
        server_config = uvicorn.Config(
            self.fastapi_app,
            host=config.get("host", "0.0.0.0"),
            port=config.get("port", 8000),
            log_level=self.config["logging"]["level"].lower(),
            access_log=True
        )
        
        server = uvicorn.Server(server_config)
        
        self.logger.info(f"Starting FastAPI server on {config['host']}:{config['port']}")
        await server.serve()
    
    async def start_mcp(self):
        """MCPサーバーを起動"""
        if not self.mcp_server:
            return
        
        self.logger.info("Starting MCP server on stdio")
        
        if self.config["protocols"]["mcp"]["stdio_mode"]:
            # stdio mode for Claude Desktop integration
            await stdio.stdio_server(self.mcp_server)
        else:
            # Network mode (future enhancement)
            self.logger.warning("Network MCP mode not implemented yet")
    
    def setup_signal_handlers(self):
        """シグナルハンドラーを設定"""
        def signal_handler(sig, frame):
            self.logger.info(f"Received signal {sig}, shutting down gracefully...")
            asyncio.create_task(self.shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def start(self):
        """統合サーバーを起動 - Bellona's Tactical Coordination"""
        try:
            self.logger.info("[TACTICAL] Commencing TMWS unified server deployment...")
            
            # Initialize shared services
            await self.initialize_services()
            
            # Create applications
            self.fastapi_app = self.create_fastapi_app()
            self.mcp_server = self.create_mcp_server()
            
            # Initialize Tactical Coordinator - Bellona's Command Center
            tactical_config = self.config.get("tactical", {})
            tactical_success = await self.tactical_coordinator.initialize(
                fastapi_app=self.fastapi_app,
                mcp_server=self.mcp_server,
                config=tactical_config
            )
            
            if not tactical_success:
                self.logger.error("[TACTICAL] Failed to initialize tactical coordination")
                return False
            
            # Setup signal handling
            self.setup_signal_handlers()
            
            # Deploy services under tactical coordination
            deployment_success = await self.tactical_coordinator.deploy()
            
            if not deployment_success:
                self.logger.error("[TACTICAL] Service deployment failed")
                return False
            
            self.is_running = True
            
            self.logger.info("[TACTICAL] TMWS Unified Server deployment successful - All systems operational")
            
            # Keep the server running under tactical coordination
            try:
                while self.is_running:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                self.logger.info("[TACTICAL] Shutdown signal received")
                await self.shutdown()
            
        except Exception as e:
            self.logger.error(f"Failed to start unified server: {e}")
            await self.shutdown()
            raise
    
    async def shutdown(self):
        """Tactical Shutdown - Bellona's Coordinated Termination"""
        if not self.is_running:
            return
        
        self.logger.info("[TACTICAL] Initiating coordinated shutdown sequence...")
        self.is_running = False
        
        # Execute tactical shutdown through coordinator
        if self.tactical_coordinator:
            await self.tactical_coordinator.shutdown()
        
        # Legacy task cleanup (for any remaining tasks)
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        # Wait for task completion
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        # Cleanup services
        if self.memory_service:
            await self.memory_service.cleanup()
        
        # Shutdown unified database
        await shutdown_unified_database()
        
        # Cleanup Redis connection
        if self.redis_client:
            try:
                self.redis_client.close()
                self.logger.info("Redis connection closed")
            except Exception as e:
                self.logger.warning(f"Error closing Redis connection: {e}")
        
        self.logger.info("TMWS Unified Server shutdown complete")


async def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="TMWS Unified Server")
    parser.add_argument("--config", type=str, help="Configuration file path")
    parser.add_argument("--port", type=int, help="FastAPI port override")
    parser.add_argument("--dev", action="store_true", help="Development mode")
    parser.add_argument("--mcp-only", action="store_true", help="MCP protocol only")
    parser.add_argument("--api-only", action="store_true", help="FastAPI only")
    
    args = parser.parse_args()
    
    # Create server instance
    server = TMWSUnifiedServer(config_path=args.config)
    
    # Override configuration based on arguments
    if args.port:
        server.config["protocols"]["fastapi"]["port"] = args.port
    
    if args.dev:
        server.config["logging"]["level"] = "DEBUG"
        server.config["protocols"]["fastapi"]["auto_reload"] = True
    
    if args.mcp_only:
        server.config["protocols"]["fastapi"]["enabled"] = False
    
    if args.api_only:
        server.config["protocols"]["mcp"]["enabled"] = False
    
    # Start server
    try:
        await server.start()
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Server failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())