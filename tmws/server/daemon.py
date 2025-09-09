"""
TMWS Daemon Server
Handles background server operations and multiple client connections.
"""

import asyncio
import signal
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import structlog
from contextlib import asynccontextmanager

from ..core.config import Settings
from ..core.database import Database
from ..services.memory_service import MemoryService
from ..services.task_service import TaskService
from ..services.workflow_service import WorkflowService

logger = structlog.get_logger()


class TMWSDaemon:
    """
    TMWS Daemon Server
    Manages the background server process and client connections.
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize the daemon server."""
        self.settings = settings or Settings()
        self.database: Optional[Database] = None
        self.memory_service: Optional[MemoryService] = None
        self.task_service: Optional[TaskService] = None
        self.workflow_service: Optional[WorkflowService] = None
        self.running = False
        self.clients: Dict[str, Any] = {}
        self._shutdown_event = asyncio.Event()
        
        logger.info("TMWSDaemon initialized", 
                   host=self.settings.api_host,
                   port=self.settings.api_port)
    
    async def initialize_services(self):
        """Initialize all required services."""
        try:
            # Initialize database
            self.database = Database(self.settings.database_url)
            await self.database.initialize()
            logger.info("Database initialized")
            
            # Initialize services
            async with self.database.get_session() as session:
                self.memory_service = MemoryService(session)
                self.task_service = TaskService(session)
                self.workflow_service = WorkflowService(session)
                logger.info("Services initialized")
                
        except Exception as e:
            logger.error("Failed to initialize services", error=str(e))
            raise
    
    async def start(self):
        """Start the daemon server."""
        logger.info("Starting TMWS daemon server...")
        
        # Initialize services
        await self.initialize_services()
        
        # Set up signal handlers
        self._setup_signal_handlers()
        
        self.running = True
        logger.info("TMWS daemon server started successfully")
        
        # Keep the server running
        try:
            await self._shutdown_event.wait()
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Gracefully shutdown the daemon."""
        if not self.running:
            return
            
        logger.info("Shutting down TMWS daemon server...")
        self.running = False
        
        # Close all client connections
        for client_id in list(self.clients.keys()):
            await self.disconnect_client(client_id)
        
        # Close database connections
        if self.database:
            await self.database.close()
        
        logger.info("TMWS daemon server shutdown complete")
    
    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}")
            self._shutdown_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def register_client(self, client_id: str, client_info: Dict[str, Any]):
        """Register a new client connection."""
        if client_id in self.clients:
            logger.warning("Client already registered", client_id=client_id)
            return False
        
        self.clients[client_id] = client_info
        logger.info("Client registered", client_id=client_id, agent=client_info.get('agent_id'))
        return True
    
    async def disconnect_client(self, client_id: str):
        """Disconnect and unregister a client."""
        if client_id not in self.clients:
            return
        
        client_info = self.clients.pop(client_id)
        logger.info("Client disconnected", client_id=client_id, agent=client_info.get('agent_id'))
    
    def get_status(self) -> Dict[str, Any]:
        """Get current daemon status."""
        return {
            "running": self.running,
            "clients": len(self.clients),
            "database": "connected" if self.database else "disconnected",
            "services": {
                "memory": self.memory_service is not None,
                "task": self.task_service is not None,
                "workflow": self.workflow_service is not None
            }
        }


@asynccontextmanager
async def create_daemon(settings: Optional[Settings] = None):
    """Create and manage a daemon instance."""
    daemon = TMWSDaemon(settings)
    try:
        await daemon.initialize_services()
        yield daemon
    finally:
        await daemon.shutdown()