#!/usr/bin/env python3
"""
TMWS Process Manager - Tactical Coordination Layer
Bellona の戦術的調整システム

Manages:
- FastMCP and FastAPI service coordination
- Health monitoring and recovery
- Resource allocation and optimization
- Inter-process communication
- Graceful startup/shutdown sequences
"""

import asyncio
import logging
import signal
import time
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Set
from datetime import datetime, timedelta
from pathlib import Path
import psutil
import json

logger = logging.getLogger(__name__)


class ServiceState(Enum):
    """Service operational states"""
    INITIALIZING = "initializing"
    STARTING = "starting"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class ProcessPriority(Enum):
    """Process priority levels for resource allocation"""
    CRITICAL = 0  # MCP Server - core functionality
    HIGH = 1      # FastAPI - user interface
    MEDIUM = 2    # Background services
    LOW = 3       # Monitoring and cleanup


@dataclass
class ServiceMetrics:
    """Real-time service performance metrics"""
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    requests_per_second: float = 0.0
    response_time_ms: float = 0.0
    error_rate: float = 0.0
    uptime_seconds: int = 0
    last_health_check: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ServiceConfig:
    """Service configuration and constraints"""
    name: str
    priority: ProcessPriority
    max_memory_mb: int = 512
    max_cpu_percent: float = 50.0
    health_check_interval: int = 30
    restart_threshold: int = 3
    startup_timeout: int = 60
    shutdown_timeout: int = 30
    dependencies: List[str] = field(default_factory=list)


class ServiceManager(ABC):
    """Abstract base for service management"""
    
    def __init__(self, config: ServiceConfig):
        self.config = config
        self.state = ServiceState.INITIALIZING
        self.metrics = ServiceMetrics()
        self.restart_count = 0
        self.last_restart = None
        self._process = None
        self._health_task = None
        
    @abstractmethod
    async def start(self) -> bool:
        """Start the service"""
        pass
    
    @abstractmethod
    async def stop(self) -> bool:
        """Stop the service gracefully"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check service health"""
        pass
    
    @abstractmethod
    async def get_metrics(self) -> ServiceMetrics:
        """Get current service metrics"""
        pass
    
    def should_restart(self) -> bool:
        """Determine if service should be restarted"""
        if self.restart_count >= self.config.restart_threshold:
            return False
        
        if self.last_restart:
            time_since_restart = datetime.utcnow() - self.last_restart
            if time_since_restart < timedelta(minutes=5):
                return False
                
        return self.state in [ServiceState.FAILED, ServiceState.UNHEALTHY]


class FastMCPManager(ServiceManager):
    """FastMCP service manager"""
    
    def __init__(self, mcp_server, config: ServiceConfig):
        super().__init__(config)
        self.mcp_server = mcp_server
        self._server_task = None
        
    async def start(self) -> bool:
        """Start FastMCP server"""
        try:
            logger.info(f"[TACTICAL] Starting FastMCP service...")
            self.state = ServiceState.STARTING
            
            # Start MCP server in background task
            self._server_task = asyncio.create_task(self._run_mcp_server())
            
            # Wait for startup with timeout
            start_time = time.time()
            while time.time() - start_time < self.config.startup_timeout:
                if await self.health_check():
                    self.state = ServiceState.HEALTHY
                    logger.info(f"[TACTICAL] FastMCP service operational")
                    return True
                await asyncio.sleep(1)
            
            self.state = ServiceState.FAILED
            logger.error(f"[TACTICAL] FastMCP startup timeout")
            return False
            
        except Exception as e:
            self.state = ServiceState.FAILED
            logger.error(f"[TACTICAL] FastMCP startup failed: {e}")
            return False
    
    async def _run_mcp_server(self):
        """Run MCP server in background"""
        try:
            import mcp.server.stdio
            from mcp.types import Tool
            
            # Configure and run MCP server
            async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
                await self.mcp_server.run(
                    read_stream,
                    write_stream,
                    mcp.server.stdio.init_kwargs
                )
        except Exception as e:
            logger.error(f"[TACTICAL] MCP server error: {e}")
            self.state = ServiceState.FAILED
    
    async def stop(self) -> bool:
        """Stop FastMCP server gracefully"""
        try:
            logger.info(f"[TACTICAL] Stopping FastMCP service...")
            self.state = ServiceState.STOPPING
            
            if self._server_task:
                self._server_task.cancel()
                try:
                    await asyncio.wait_for(self._server_task, timeout=self.config.shutdown_timeout)
                except asyncio.TimeoutError:
                    logger.warning(f"[TACTICAL] FastMCP shutdown timeout")
            
            self.state = ServiceState.STOPPED
            logger.info(f"[TACTICAL] FastMCP service stopped")
            return True
            
        except Exception as e:
            logger.error(f"[TACTICAL] FastMCP shutdown error: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check FastMCP health"""
        try:
            # Check if server task is running
            if not self._server_task or self._server_task.done():
                return False
            
            # Update metrics
            self.metrics.last_health_check = datetime.utcnow()
            return True
            
        except Exception:
            return False
    
    async def get_metrics(self) -> ServiceMetrics:
        """Get FastMCP metrics"""
        try:
            if self._process:
                process = psutil.Process(self._process.pid)
                self.metrics.cpu_percent = process.cpu_percent()
                self.metrics.memory_mb = process.memory_info().rss / 1024 / 1024
            
            return self.metrics
        except:
            return self.metrics


class FastAPIManager(ServiceManager):
    """FastAPI service manager"""
    
    def __init__(self, app, config: ServiceConfig, host: str = "0.0.0.0", port: int = 8000):
        super().__init__(config)
        self.app = app
        self.host = host
        self.port = port
        self._server = None
        self._server_task = None
        
    async def start(self) -> bool:
        """Start FastAPI server"""
        try:
            logger.info(f"[TACTICAL] Starting FastAPI service on {self.host}:{self.port}...")
            self.state = ServiceState.STARTING
            
            # Configure Uvicorn server
            config = uvicorn.Config(
                app=self.app,
                host=self.host,
                port=self.port,
                log_level="info",
                access_log=True,
                loop="asyncio"
            )
            
            self._server = uvicorn.Server(config)
            self._server_task = asyncio.create_task(self._server.serve())
            
            # Wait for startup
            start_time = time.time()
            while time.time() - start_time < self.config.startup_timeout:
                if await self.health_check():
                    self.state = ServiceState.HEALTHY
                    logger.info(f"[TACTICAL] FastAPI service operational")
                    return True
                await asyncio.sleep(1)
            
            self.state = ServiceState.FAILED
            logger.error(f"[TACTICAL] FastAPI startup timeout")
            return False
            
        except Exception as e:
            self.state = ServiceState.FAILED
            logger.error(f"[TACTICAL] FastAPI startup failed: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop FastAPI server gracefully"""
        try:
            logger.info(f"[TACTICAL] Stopping FastAPI service...")
            self.state = ServiceState.STOPPING
            
            if self._server:
                self._server.should_exit = True
                
            if self._server_task:
                self._server_task.cancel()
                try:
                    await asyncio.wait_for(self._server_task, timeout=self.config.shutdown_timeout)
                except asyncio.TimeoutError:
                    logger.warning(f"[TACTICAL] FastAPI shutdown timeout")
            
            self.state = ServiceState.STOPPED
            logger.info(f"[TACTICAL] FastAPI service stopped")
            return True
            
        except Exception as e:
            logger.error(f"[TACTICAL] FastAPI shutdown error: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check FastAPI health"""
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{self.host}:{self.port}/health",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    healthy = response.status == 200
                    
            self.metrics.last_health_check = datetime.utcnow()
            return healthy
            
        except Exception:
            return False
    
    async def get_metrics(self) -> ServiceMetrics:
        """Get FastAPI metrics"""
        try:
            if self._process:
                process = psutil.Process(self._process.pid)
                self.metrics.cpu_percent = process.cpu_percent()
                self.metrics.memory_mb = process.memory_info().rss / 1024 / 1024
            
            return self.metrics
        except:
            return self.metrics


class TacticalProcessManager:
    """
    Main tactical coordination system for TMWS
    Manages all services with military precision
    """
    
    def __init__(self):
        self.services: Dict[str, ServiceManager] = {}
        self.is_running = False
        self._monitoring_task = None
        self._shutdown_event = asyncio.Event()
        self._resource_monitor = None
        
        # Service dependency graph
        self.dependency_graph = {}
        
        # Communication channels
        self._ipc_channels: Dict[str, asyncio.Queue] = {}
        
        # Metrics collection
        self.system_metrics = {
            "start_time": datetime.utcnow(),
            "total_requests": 0,
            "failed_requests": 0,
            "services_restarted": 0,
        }
        
        logger.info("[TACTICAL] Process Manager initialized")
    
    def register_service(self, name: str, service_manager: ServiceManager):
        """Register a service for management"""
        self.services[name] = service_manager
        self._ipc_channels[name] = asyncio.Queue()
        
        # Build dependency graph
        self.dependency_graph[name] = service_manager.config.dependencies
        
        logger.info(f"[TACTICAL] Service '{name}' registered")
    
    async def start_all_services(self):
        """Start all services in dependency order"""
        logger.info("[TACTICAL] Initiating coordinated service startup")
        
        try:
            self.is_running = True
            
            # Calculate startup order based on dependencies
            startup_order = self._calculate_startup_order()
            
            for service_name in startup_order:
                service = self.services[service_name]
                logger.info(f"[TACTICAL] Starting {service_name} (Priority: {service.config.priority.name})")
                
                success = await service.start()
                if not success:
                    logger.error(f"[TACTICAL] Failed to start {service_name}")
                    await self._handle_startup_failure(service_name)
                    return False
            
            # Start monitoring systems
            self._monitoring_task = asyncio.create_task(self._monitor_services())
            self._resource_monitor = asyncio.create_task(self._monitor_resources())
            
            logger.info("[TACTICAL] All services operational. Tactical coordination active.")
            return True
            
        except Exception as e:
            logger.error(f"[TACTICAL] Service startup failed: {e}")
            await self.shutdown_all_services()
            return False
    
    async def shutdown_all_services(self):
        """Graceful shutdown of all services"""
        logger.info("[TACTICAL] Initiating coordinated shutdown sequence")
        
        self.is_running = False
        self._shutdown_event.set()
        
        # Stop monitoring
        if self._monitoring_task:
            self._monitoring_task.cancel()
        if self._resource_monitor:
            self._resource_monitor.cancel()
        
        # Calculate shutdown order (reverse of startup)
        shutdown_order = list(reversed(self._calculate_startup_order()))
        
        for service_name in shutdown_order:
            service = self.services[service_name]
            logger.info(f"[TACTICAL] Stopping {service_name}")
            
            try:
                await asyncio.wait_for(
                    service.stop(),
                    timeout=service.config.shutdown_timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"[TACTICAL] {service_name} shutdown timeout - forcing stop")
            except Exception as e:
                logger.error(f"[TACTICAL] Error stopping {service_name}: {e}")
        
        logger.info("[TACTICAL] All services terminated. Tactical coordination complete.")
    
    def _calculate_startup_order(self) -> List[str]:
        """Calculate optimal service startup order based on dependencies"""
        ordered = []
        visited = set()
        temp_visited = set()
        
        def visit(service_name: str):
            if service_name in temp_visited:
                raise ValueError(f"Circular dependency detected involving {service_name}")
            
            if service_name in visited:
                return
            
            temp_visited.add(service_name)
            
            # Visit dependencies first
            for dep in self.dependency_graph.get(service_name, []):
                if dep in self.services:
                    visit(dep)
            
            temp_visited.remove(service_name)
            visited.add(service_name)
            ordered.append(service_name)
        
        # Visit all services
        for service_name in self.services.keys():
            if service_name not in visited:
                visit(service_name)
        
        # Sort by priority within dependency order
        def priority_key(name: str):
            return self.services[name].config.priority.value
        
        return sorted(ordered, key=priority_key)
    
    async def _monitor_services(self):
        """Continuous service health monitoring"""
        logger.info("[TACTICAL] Service monitoring active")
        
        while self.is_running:
            try:
                for service_name, service in self.services.items():
                    # Perform health check
                    healthy = await service.health_check()
                    
                    if not healthy:
                        logger.warning(f"[TACTICAL] {service_name} health check failed")
                        await self._handle_service_failure(service_name)
                    
                    # Update service state based on health
                    if service.state == ServiceState.HEALTHY and not healthy:
                        service.state = ServiceState.DEGRADED
                    elif service.state == ServiceState.DEGRADED and healthy:
                        service.state = ServiceState.HEALTHY
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"[TACTICAL] Monitoring error: {e}")
                await asyncio.sleep(30)
    
    async def _monitor_resources(self):
        """Monitor system resource usage"""
        logger.info("[TACTICAL] Resource monitoring active")
        
        while self.is_running:
            try:
                # Monitor system resources
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                
                if cpu_percent > 80:
                    logger.warning(f"[TACTICAL] High CPU usage: {cpu_percent}%")
                    await self._optimize_resource_allocation()
                
                if memory.percent > 85:
                    logger.warning(f"[TACTICAL] High memory usage: {memory.percent}%")
                    await self._optimize_memory_usage()
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"[TACTICAL] Resource monitoring error: {e}")
                await asyncio.sleep(60)
    
    async def _handle_service_failure(self, service_name: str):
        """Handle individual service failures"""
        service = self.services[service_name]
        
        if service.should_restart():
            logger.info(f"[TACTICAL] Attempting restart of {service_name}")
            
            # Stop failed service
            await service.stop()
            
            # Wait before restart
            await asyncio.sleep(5)
            
            # Attempt restart
            success = await service.start()
            if success:
                service.restart_count += 1
                service.last_restart = datetime.utcnow()
                self.system_metrics["services_restarted"] += 1
                logger.info(f"[TACTICAL] {service_name} successfully restarted")
            else:
                logger.error(f"[TACTICAL] Failed to restart {service_name}")
                service.state = ServiceState.FAILED
        else:
            logger.error(f"[TACTICAL] {service_name} marked as failed - restart threshold exceeded")
            service.state = ServiceState.FAILED
    
    async def _handle_startup_failure(self, service_name: str):
        """Handle startup failures"""
        logger.error(f"[TACTICAL] Critical startup failure: {service_name}")
        # Could implement fallback strategies here
    
    async def _optimize_resource_allocation(self):
        """Optimize resource allocation under high load"""
        logger.info("[TACTICAL] Implementing resource optimization protocols")
        
        # Lower priority services could be throttled
        for service_name, service in self.services.items():
            if service.config.priority in [ProcessPriority.LOW, ProcessPriority.MEDIUM]:
                # Could implement CPU/memory limits here
                pass
    
    async def _optimize_memory_usage(self):
        """Optimize memory usage under pressure"""
        logger.info("[TACTICAL] Implementing memory optimization protocols")
        
        # Could trigger garbage collection, cache clearing, etc.
        import gc
        gc.collect()
    
    async def send_ipc_message(self, from_service: str, to_service: str, message: Dict[str, Any]):
        """Send inter-process communication message"""
        if to_service in self._ipc_channels:
            await self._ipc_channels[to_service].put({
                "from": from_service,
                "timestamp": datetime.utcnow().isoformat(),
                "data": message
            })
    
    async def receive_ipc_message(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Receive IPC message for a service"""
        if service_name in self._ipc_channels:
            try:
                return await asyncio.wait_for(
                    self._ipc_channels[service_name].get(),
                    timeout=0.1
                )
            except asyncio.TimeoutError:
                return None
        return None
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get comprehensive service status"""
        status = {
            "manager_running": self.is_running,
            "start_time": self.system_metrics["start_time"].isoformat(),
            "uptime_seconds": (datetime.utcnow() - self.system_metrics["start_time"]).total_seconds(),
            "services": {}
        }
        
        for service_name, service in self.services.items():
            status["services"][service_name] = {
                "state": service.state.value,
                "restart_count": service.restart_count,
                "last_health_check": service.metrics.last_health_check.isoformat() if service.metrics.last_health_check else None,
                "metrics": {
                    "cpu_percent": service.metrics.cpu_percent,
                    "memory_mb": service.metrics.memory_mb,
                    "uptime_seconds": service.metrics.uptime_seconds
                }
            }
        
        return status
    
    async def setup_signal_handlers(self):
        """Setup graceful shutdown signal handlers"""
        def signal_handler(signum, frame):
            logger.info(f"[TACTICAL] Received signal {signum} - initiating shutdown")
            asyncio.create_task(self.shutdown_all_services())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)


# Tactical coordination factory functions
def create_fastmcp_manager(mcp_server, max_memory_mb: int = 256) -> FastMCPManager:
    """Create FastMCP service manager with tactical configuration"""
    config = ServiceConfig(
        name="fastmcp",
        priority=ProcessPriority.CRITICAL,
        max_memory_mb=max_memory_mb,
        max_cpu_percent=30.0,
        health_check_interval=15,
        restart_threshold=3,
        startup_timeout=45,
        shutdown_timeout=20
    )
    return FastMCPManager(mcp_server, config)


def create_fastapi_manager(app, host: str = "0.0.0.0", port: int = 8000, max_memory_mb: int = 512) -> FastAPIManager:
    """Create FastAPI service manager with tactical configuration"""
    config = ServiceConfig(
        name="fastapi",
        priority=ProcessPriority.HIGH,
        max_memory_mb=max_memory_mb,
        max_cpu_percent=40.0,
        health_check_interval=30,
        restart_threshold=5,
        startup_timeout=30,
        shutdown_timeout=15,
        dependencies=["fastmcp"]  # FastAPI depends on MCP for some operations
    )
    return FastAPIManager(app, config, host, port)


def create_tactical_process_manager() -> TacticalProcessManager:
    """Create main tactical process manager"""
    return TacticalProcessManager()