"""
TMWS FastAPI Application with WebSocket support
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import json
import uuid
from typing import Dict, Any, Optional
import structlog

from .daemon import TMWSDaemon
from .handlers.websocket_handler import WebSocketHandler
from .handlers.mcp_bridge import MCPBridge
from ..core.config import Settings
from ..core.security import verify_token

logger = structlog.get_logger()

# Global daemon instance
daemon: Optional[TMWSDaemon] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global daemon
    
    # Startup
    logger.info("Starting TMWS server application...")
    settings = Settings()
    daemon = TMWSDaemon(settings)
    await daemon.initialize_services()
    
    # Include existing routers
    from ..api.v1 import tasks, workflows, memory, personas
    app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
    app.include_router(workflows.router, prefix="/api/v1/workflows", tags=["workflows"])
    app.include_router(memory.router, prefix="/api/v1/memory", tags=["memory"])
    app.include_router(personas.router, prefix="/api/v1/personas", tags=["personas"])
    
    logger.info("TMWS server application started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down TMWS server application...")
    if daemon:
        await daemon.shutdown()
    logger.info("TMWS server application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="TMWS Server",
    description="Trinitas Memory & Workflow Service with Multi-Client Support",
    version="2.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "TMWS",
        "version": "2.0.0",
        "status": "running",
        "features": ["rest_api", "websocket", "mcp_bridge"]
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    global daemon
    if not daemon:
        raise HTTPException(status_code=503, detail="Service unavailable")
    
    status = daemon.get_status()
    return {
        "status": "healthy" if status["running"] else "unhealthy",
        "details": status
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for MCP bridge."""
    global daemon
    
    if not daemon:
        await websocket.close(code=1011, reason="Service unavailable")
        return
    
    # Accept connection
    await websocket.accept()
    
    # Generate client ID
    client_id = str(uuid.uuid4())
    
    # Create handlers
    ws_handler = WebSocketHandler(websocket, client_id)
    mcp_bridge = MCPBridge(daemon, ws_handler)
    
    try:
        # Register client
        await daemon.register_client(client_id, {
            "type": "websocket",
            "handler": ws_handler,
            "bridge": mcp_bridge
        })
        
        # Send welcome message
        await ws_handler.send_message({
            "type": "connection",
            "status": "connected",
            "client_id": client_id,
            "message": "Welcome to TMWS WebSocket Service"
        })
        
        # Handle messages
        while True:
            try:
                # Receive message
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Process through MCP bridge
                response = await mcp_bridge.process_message(message)
                
                # Send response
                if response:
                    await ws_handler.send_message(response)
                    
            except json.JSONDecodeError as e:
                await ws_handler.send_error(f"Invalid JSON: {str(e)}")
                
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected", client_id=client_id)
    except Exception as e:
        logger.error("WebSocket error", client_id=client_id, error=str(e))
        await ws_handler.send_error(str(e))
    finally:
        # Unregister client
        await daemon.disconnect_client(client_id)


@app.websocket("/ws/mcp")
async def mcp_websocket_endpoint(websocket: WebSocket):
    """Dedicated MCP WebSocket endpoint."""
    global daemon
    
    if not daemon:
        await websocket.close(code=1011, reason="Service unavailable")
        return
    
    await websocket.accept()
    
    # This endpoint specifically handles MCP protocol over WebSocket
    client_id = str(uuid.uuid4())
    
    try:
        # Create MCP-specific handler
        from .handlers.mcp_websocket import MCPWebSocketHandler
        handler = MCPWebSocketHandler(websocket, daemon, client_id)
        
        # Register as MCP client
        await daemon.register_client(client_id, {
            "type": "mcp_websocket",
            "handler": handler,
            "agent_id": None  # Will be set after initialization
        })
        
        # Run MCP protocol handler
        await handler.run()
        
    except WebSocketDisconnect:
        logger.info("MCP WebSocket disconnected", client_id=client_id)
    except Exception as e:
        logger.error("MCP WebSocket error", client_id=client_id, error=str(e))
    finally:
        await daemon.disconnect_client(client_id)