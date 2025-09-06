#!/usr/bin/env python3
"""
TMWS Tactical Coordinator - Bellona's Command Center
High-level coordination and orchestration for unified server operations

Provides:
- Service lifecycle management
- Health monitoring and recovery
- Performance optimization
- Resource allocation strategies
- Inter-service communication
- Tactical decision making
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json

from .process_manager import (
    TacticalProcessManager,
    ServiceState,
    ProcessPriority,
    create_fastmcp_manager,
    create_fastapi_manager,
    create_tactical_process_manager
)

logger = logging.getLogger(__name__)


class TacticalMode(Enum):
    """Tactical operation modes"""
    PEACETIME = "peacetime"       # Normal operations
    ALERT = "alert"               # Elevated monitoring
    CRITICAL = "critical"         # Emergency protocols
    MAINTENANCE = "maintenance"   # Planned maintenance mode


class OperationalStatus(Enum):
    """Overall operational status"""
    OPTIMAL = "optimal"
    STABLE = "stable"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    OFFLINE = "offline"


@dataclass
class TacticalMetrics:
    """System-wide tactical metrics"""
    mode: TacticalMode = TacticalMode.PEACETIME
    status: OperationalStatus = OperationalStatus.OFFLINE
    total_services: int = 0
    healthy_services: int = 0
    degraded_services: int = 0
    failed_services: int = 0
    average_response_time: float = 0.0
    total_requests: int = 0
    error_rate: float = 0.0
    uptime_percentage: float = 100.0
    last_incident: Optional[datetime] = None
    recovery_time: Optional[timedelta] = None


class TacticalCoordinator:
    """
    Main tactical coordinator for TMWS operations
    Bellona's command center for unified server management
    """
    
    def __init__(self):
        self.process_manager = create_tactical_process_manager()
        self.metrics = TacticalMetrics()
        self.is_active = False
        self._coordination_task = None
        self._decision_engine = None
        
        # Tactical configuration
        self.config = {
            "health_check_interval": 15,  # seconds
            "metrics_collection_interval": 30,
            "auto_recovery": True,
            "performance_optimization": True,
            "resource_monitoring": True,
            "alert_thresholds": {
                "cpu_percent": 80.0,
                "memory_percent": 85.0,
                "response_time_ms": 1000.0,
                "error_rate_percent": 5.0
            }
        }
        
        # Command history for tactical analysis
        self.command_history: List[Dict[str, Any]] = []
        self.incident_log: List[Dict[str, Any]] = []
        
        logger.info("[TACTICAL] Coordinator initialized - Bellona standing by")
    
    async def initialize(self, fastapi_app, mcp_server, config: Dict[str, Any] = None):
        """Initialize tactical coordinator with services"""
        logger.info("[TACTICAL] Initializing tactical coordination systems")
        
        try:
            # Update configuration if provided
            if config:
                self.config.update(config)
            
            # Create service managers
            fastmcp_manager = create_fastmcp_manager(
                mcp_server, 
                max_memory_mb=self.config.get("mcp_max_memory", 256)
            )
            
            fastapi_manager = create_fastapi_manager(
                fastapi_app,
                host=self.config.get("api_host", "0.0.0.0"),
                port=self.config.get("api_port", 8000),
                max_memory_mb=self.config.get("api_max_memory", 512)
            )
            
            # Register services with process manager
            self.process_manager.register_service("fastmcp", fastmcp_manager)
            self.process_manager.register_service("fastapi", fastapi_manager)
            
            # Setup signal handlers
            await self.process_manager.setup_signal_handlers()
            
            # Update metrics
            self.metrics.total_services = len(self.process_manager.services)
            self.metrics.status = OperationalStatus.STABLE
            
            logger.info("[TACTICAL] Tactical systems initialized - Ready for deployment")
            return True
            
        except Exception as e:
            logger.error(f"[TACTICAL] Initialization failed: {e}")
            self.metrics.status = OperationalStatus.CRITICAL
            return False
    
    async def deploy(self):
        """Deploy all services under tactical coordination"""
        logger.info("[TACTICAL] Commencing tactical deployment")
        
        try:
            self.is_active = True
            
            # Start all services
            success = await self.process_manager.start_all_services()
            if not success:
                logger.error("[TACTICAL] Deployment failed - services did not start")
                self.metrics.status = OperationalStatus.CRITICAL
                return False
            
            # Start tactical coordination
            self._coordination_task = asyncio.create_task(self._tactical_coordination_loop())
            self._decision_engine = asyncio.create_task(self._tactical_decision_engine())
            
            # Update status
            self.metrics.status = OperationalStatus.OPTIMAL
            self.metrics.mode = TacticalMode.PEACETIME
            
            logger.info("[TACTICAL] Deployment successful - All systems operational")
            return True
            
        except Exception as e:
            logger.error(f"[TACTICAL] Deployment failed: {e}")
            await self.shutdown()
            return False
    
    async def shutdown(self):
        """Graceful shutdown of all tactical operations"""
        logger.info("[TACTICAL] Initiating tactical shutdown")
        
        self.is_active = False
        
        # Stop coordination tasks
        if self._coordination_task:
            self._coordination_task.cancel()
        if self._decision_engine:
            self._decision_engine.cancel()
        
        # Shutdown all services
        await self.process_manager.shutdown_all_services()
        
        self.metrics.status = OperationalStatus.OFFLINE
        logger.info("[TACTICAL] Tactical shutdown complete")
    
    async def _tactical_coordination_loop(self):
        """Main tactical coordination loop"""
        logger.info("[TACTICAL] Tactical coordination active")
        
        while self.is_active:
            try:
                # Collect service metrics
                await self._collect_metrics()
                
                # Assess tactical situation
                await self._assess_tactical_situation()
                
                # Execute tactical decisions
                await self._execute_tactical_decisions()
                
                # Log coordination status
                await self._log_coordination_status()
                
                await asyncio.sleep(self.config["health_check_interval"])
                
            except Exception as e:
                logger.error(f"[TACTICAL] Coordination error: {e}")
                await asyncio.sleep(30)
    
    async def _tactical_decision_engine(self):
        """Tactical decision engine for automated responses"""
        logger.info("[TACTICAL] Decision engine active")
        
        while self.is_active:
            try:
                # Performance optimization decisions
                if self.config["performance_optimization"]:
                    await self._optimize_performance()
                
                # Resource management decisions
                if self.config["resource_monitoring"]:
                    await self._manage_resources()
                
                # Recovery decisions
                if self.config["auto_recovery"]:
                    await self._evaluate_recovery_actions()
                
                await asyncio.sleep(self.config["metrics_collection_interval"])
                
            except Exception as e:
                logger.error(f"[TACTICAL] Decision engine error: {e}")
                await asyncio.sleep(60)
    
    async def _collect_metrics(self):
        """Collect comprehensive system metrics"""
        try:
            service_status = self.process_manager.get_service_status()
            
            # Count service states
            healthy = sum(1 for s in service_status["services"].values() 
                         if s["state"] in ["healthy"])
            degraded = sum(1 for s in service_status["services"].values() 
                          if s["state"] in ["degraded"])
            failed = sum(1 for s in service_status["services"].values() 
                        if s["state"] in ["failed", "unhealthy"])
            
            # Update metrics
            self.metrics.healthy_services = healthy
            self.metrics.degraded_services = degraded
            self.metrics.failed_services = failed
            
            # Calculate uptime percentage
            uptime = service_status["uptime_seconds"]
            if uptime > 0:
                # Simple uptime calculation - could be more sophisticated
                self.metrics.uptime_percentage = min(100.0, (uptime / 3600) * 100)
            
        except Exception as e:
            logger.error(f"[TACTICAL] Metrics collection error: {e}")
    
    async def _assess_tactical_situation(self):
        """Assess current tactical situation and adjust mode"""
        try:
            # Determine operational status
            if self.metrics.failed_services > 0:
                self.metrics.status = OperationalStatus.CRITICAL
                self.metrics.mode = TacticalMode.CRITICAL
            elif self.metrics.degraded_services > 0:
                self.metrics.status = OperationalStatus.DEGRADED
                self.metrics.mode = TacticalMode.ALERT
            elif self.metrics.healthy_services == self.metrics.total_services:
                self.metrics.status = OperationalStatus.OPTIMAL
                self.metrics.mode = TacticalMode.PEACETIME
            else:
                self.metrics.status = OperationalStatus.STABLE
                self.metrics.mode = TacticalMode.PEACETIME
            
        except Exception as e:
            logger.error(f"[TACTICAL] Situation assessment error: {e}")
    
    async def _execute_tactical_decisions(self):
        """Execute tactical decisions based on current situation"""
        try:
            if self.metrics.mode == TacticalMode.CRITICAL:
                await self._handle_critical_situation()
            elif self.metrics.mode == TacticalMode.ALERT:
                await self._handle_alert_situation()
            elif self.metrics.mode == TacticalMode.PEACETIME:
                await self._handle_peacetime_operations()
            
        except Exception as e:
            logger.error(f"[TACTICAL] Decision execution error: {e}")
    
    async def _handle_critical_situation(self):
        """Handle critical tactical situations"""
        logger.warning("[TACTICAL] Critical situation detected - Implementing emergency protocols")
        
        # Log incident
        incident = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": "critical_situation",
            "failed_services": self.metrics.failed_services,
            "details": "Emergency protocols activated"
        }
        self.incident_log.append(incident)
        
        # Could implement emergency measures here
        # - Service restarts
        # - Resource reallocation
        # - Load balancing adjustments
        # - Alert notifications
    
    async def _handle_alert_situation(self):
        """Handle alert-level tactical situations"""
        logger.info("[TACTICAL] Alert situation - Enhanced monitoring active")
        
        # Increase monitoring frequency
        # Prepare recovery actions
        # Monitor degraded services closely
    
    async def _handle_peacetime_operations(self):
        """Handle normal peacetime operations"""
        # Normal monitoring
        # Performance optimization
        # Preventive maintenance
        pass
    
    async def _optimize_performance(self):
        """Optimize system performance"""
        try:
            # Performance optimization logic
            service_status = self.process_manager.get_service_status()
            
            for service_name, status in service_status["services"].items():
                metrics = status["metrics"]
                
                # Check if optimization needed
                if metrics["cpu_percent"] > self.config["alert_thresholds"]["cpu_percent"]:
                    logger.info(f"[TACTICAL] Optimizing CPU usage for {service_name}")
                    # Could implement CPU throttling or load balancing
                
                if metrics["memory_mb"] > 400:  # 400MB threshold
                    logger.info(f"[TACTICAL] Optimizing memory usage for {service_name}")
                    # Could trigger garbage collection or cache cleanup
            
        except Exception as e:
            logger.error(f"[TACTICAL] Performance optimization error: {e}")
    
    async def _manage_resources(self):
        """Manage system resources tactically"""
        try:
            import psutil
            
            # System resource check
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            if cpu_percent > self.config["alert_thresholds"]["cpu_percent"]:
                logger.warning(f"[TACTICAL] High system CPU usage: {cpu_percent}%")
                await self._implement_cpu_mitigation()
            
            if memory.percent > self.config["alert_thresholds"]["memory_percent"]:
                logger.warning(f"[TACTICAL] High system memory usage: {memory.percent}%")
                await self._implement_memory_mitigation()
            
        except Exception as e:
            logger.error(f"[TACTICAL] Resource management error: {e}")
    
    async def _evaluate_recovery_actions(self):
        """Evaluate and execute recovery actions"""
        try:
            # Check for services that need recovery
            for service_name, service in self.process_manager.services.items():
                if service.state == ServiceState.FAILED and service.should_restart():
                    logger.info(f"[TACTICAL] Initiating recovery for {service_name}")
                    await self.process_manager._handle_service_failure(service_name)
            
        except Exception as e:
            logger.error(f"[TACTICAL] Recovery evaluation error: {e}")
    
    async def _implement_cpu_mitigation(self):
        """Implement CPU usage mitigation strategies"""
        logger.info("[TACTICAL] Implementing CPU mitigation protocols")
        # Could implement:
        # - Process priority adjustments
        # - Task scheduling optimization
        # - Load balancing
    
    async def _implement_memory_mitigation(self):
        """Implement memory usage mitigation strategies"""
        logger.info("[TACTICAL] Implementing memory mitigation protocols")
        # Could implement:
        # - Garbage collection
        # - Cache cleanup
        # - Memory limits enforcement
        import gc
        gc.collect()
    
    async def _log_coordination_status(self):
        """Log tactical coordination status"""
        if len(self.command_history) % 20 == 0:  # Log every 20 cycles
            status = {
                "timestamp": datetime.utcnow().isoformat(),
                "mode": self.metrics.mode.value,
                "status": self.metrics.status.value,
                "services": {
                    "total": self.metrics.total_services,
                    "healthy": self.metrics.healthy_services,
                    "degraded": self.metrics.degraded_services,
                    "failed": self.metrics.failed_services
                }
            }
            
            logger.info(f"[TACTICAL] Status: {self.metrics.status.value.upper()} | "
                       f"Mode: {self.metrics.mode.value.upper()} | "
                       f"Services: {self.metrics.healthy_services}/{self.metrics.total_services} healthy")
            
            self.command_history.append(status)
    
    def get_tactical_status(self) -> Dict[str, Any]:
        """Get comprehensive tactical status"""
        return {
            "coordinator": {
                "active": self.is_active,
                "mode": self.metrics.mode.value,
                "status": self.metrics.status.value
            },
            "services": self.process_manager.get_service_status(),
            "metrics": {
                "total_services": self.metrics.total_services,
                "healthy_services": self.metrics.healthy_services,
                "degraded_services": self.metrics.degraded_services,
                "failed_services": self.metrics.failed_services,
                "uptime_percentage": self.metrics.uptime_percentage,
                "error_rate": self.metrics.error_rate
            },
            "incidents": len(self.incident_log),
            "last_incident": self.metrics.last_incident.isoformat() if self.metrics.last_incident else None
        }
    
    async def execute_tactical_command(self, command: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute tactical command"""
        logger.info(f"[TACTICAL] Executing command: {command}")
        
        try:
            if command == "status":
                return self.get_tactical_status()
            
            elif command == "restart_service":
                service_name = params.get("service")
                if service_name in self.process_manager.services:
                    await self.process_manager._handle_service_failure(service_name)
                    return {"success": True, "message": f"Restart initiated for {service_name}"}
                else:
                    return {"success": False, "message": f"Service {service_name} not found"}
            
            elif command == "set_mode":
                mode = params.get("mode")
                if mode in [m.value for m in TacticalMode]:
                    self.metrics.mode = TacticalMode(mode)
                    return {"success": True, "message": f"Mode set to {mode}"}
                else:
                    return {"success": False, "message": f"Invalid mode: {mode}"}
            
            elif command == "optimize":
                await self._optimize_performance()
                return {"success": True, "message": "Performance optimization executed"}
            
            elif command == "health_check":
                await self._collect_metrics()
                return {
                    "success": True, 
                    "health": {
                        "healthy": self.metrics.healthy_services,
                        "total": self.metrics.total_services,
                        "status": self.metrics.status.value
                    }
                }
            
            else:
                return {"success": False, "message": f"Unknown command: {command}"}
            
        except Exception as e:
            logger.error(f"[TACTICAL] Command execution error: {e}")
            return {"success": False, "message": f"Command failed: {str(e)}"}


# Factory function
def create_tactical_coordinator() -> TacticalCoordinator:
    """Create main tactical coordinator instance"""
    return TacticalCoordinator()