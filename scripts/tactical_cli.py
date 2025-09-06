#!/usr/bin/env python3
"""
TMWS Tactical CLI - Bellona's Command Line Interface
Command-line interface for tactical coordination and monitoring

Usage:
    python -m tmws.scripts.tactical_cli status
    python -m tmws.scripts.tactical_cli health
    python -m tmws.scripts.tactical_cli restart fastmcp
    python -m tmws.scripts.tactical_cli monitor --interval 30
"""

import asyncio
import aiohttp
import argparse
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional
import sys


class TacticalCLI:
    """Command-line interface for tactical operations"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_status(self) -> Dict[str, Any]:
        """Get tactical status"""
        async with self.session.get(f"{self.base_url}/tactical/status") as response:
            if response.status == 200:
                return await response.json()
            else:
                return {"error": f"HTTP {response.status}"}
    
    async def get_health(self) -> Dict[str, Any]:
        """Get health check"""
        async with self.session.get(f"{self.base_url}/tactical/health") as response:
            if response.status == 200:
                return await response.json()
            else:
                return {"error": f"HTTP {response.status}"}
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get detailed metrics"""
        async with self.session.get(f"{self.base_url}/tactical/metrics") as response:
            if response.status == 200:
                return await response.json()
            else:
                return {"error": f"HTTP {response.status}"}
    
    async def execute_command(self, command: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute tactical command"""
        payload = {"command": command}
        if params:
            payload["params"] = params
        
        async with self.session.post(
            f"{self.base_url}/tactical/command",
            json=payload
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                return {"error": f"HTTP {response.status}"}
    
    def print_status(self, status: Dict[str, Any]):
        """Print formatted status"""
        print("╔══════════════════════════════════════════════════════════════════╗")
        print("║                    TACTICAL STATUS REPORT                       ║")
        print("╠══════════════════════════════════════════════════════════════════╣")
        
        if "error" in status:
            print(f"║ ERROR: {status['error']:<55} ║")
            print("╚══════════════════════════════════════════════════════════════════╝")
            return
        
        coordinator = status.get("coordinator", {})
        metrics = status.get("metrics", {})
        services = status.get("services", {}).get("services", {})
        
        # Coordinator status
        mode = coordinator.get("mode", "unknown").upper()
        operational_status = coordinator.get("status", "unknown").upper()
        active = "ACTIVE" if coordinator.get("active") else "INACTIVE"
        
        print(f"║ Tactical Mode: {mode:<15} Status: {operational_status:<15} ║")
        print(f"║ Coordinator: {active:<51} ║")
        print("╠══════════════════════════════════════════════════════════════════╣")
        
        # Service metrics
        total = metrics.get("total_services", 0)
        healthy = metrics.get("healthy_services", 0)
        degraded = metrics.get("degraded_services", 0)
        failed = metrics.get("failed_services", 0)
        uptime = metrics.get("uptime_percentage", 0.0)
        
        print(f"║ Services: {total} total, {healthy} healthy, {degraded} degraded, {failed} failed      ║")
        print(f"║ Uptime: {uptime:.1f}%{' ' * 49} ║")
        print("╠══════════════════════════════════════════════════════════════════╣")
        
        # Individual service status
        if services:
            print("║ Individual Service Status:                                       ║")
            for service_name, service_info in services.items():
                state = service_info.get("state", "unknown").upper()
                restart_count = service_info.get("restart_count", 0)
                cpu = service_info.get("metrics", {}).get("cpu_percent", 0.0)
                memory = service_info.get("metrics", {}).get("memory_mb", 0.0)
                
                print(f"║ {service_name:<10} | {state:<10} | CPU: {cpu:5.1f}% | MEM: {memory:6.1f}MB ║")
        
        # Incidents
        incident_count = status.get("incidents", 0)
        last_incident = status.get("last_incident")
        
        if incident_count > 0:
            print("╠══════════════════════════════════════════════════════════════════╣")
            print(f"║ Incidents: {incident_count:<51} ║")
            if last_incident:
                print(f"║ Last Incident: {last_incident[:45]:<45} ║")
        
        print("╚══════════════════════════════════════════════════════════════════╝")
    
    def print_health(self, health: Dict[str, Any]):
        """Print formatted health check"""
        print("╔═══════════════════════════════╗")
        print("║       HEALTH CHECK REPORT     ║")
        print("╠═══════════════════════════════╣")
        
        if "error" in health:
            print(f"║ ERROR: {health['error']:<21} ║")
        elif health.get("success"):
            health_data = health.get("health", {})
            healthy = health_data.get("healthy", 0)
            total = health_data.get("total", 0)
            status = health_data.get("status", "unknown")
            
            print(f"║ Status: {status.upper():<21} ║")
            print(f"║ Services: {healthy}/{total} healthy{' ' * 10} ║")
        else:
            print("║ Health check failed           ║")
        
        print("╚═══════════════════════════════╝")
    
    def print_metrics(self, metrics: Dict[str, Any]):
        """Print formatted metrics"""
        print("╔══════════════════════════════════════════════════════════╗")
        print("║                    TACTICAL METRICS                     ║")
        print("╠══════════════════════════════════════════════════════════╣")
        
        if "error" in metrics:
            print(f"║ ERROR: {metrics['error']:<47} ║")
            print("╚══════════════════════════════════════════════════════════╝")
            return
        
        mode = metrics.get("tactical_mode", "unknown").upper()
        status = metrics.get("operational_status", "unknown").upper()
        
        print(f"║ Mode: {mode:<15} Status: {status:<15} ║")
        
        service_metrics = metrics.get("service_metrics", {})
        if service_metrics:
            total = service_metrics.get("total_services", 0)
            healthy = service_metrics.get("healthy_services", 0)
            degraded = service_metrics.get("degraded_services", 0)
            failed = service_metrics.get("failed_services", 0)
            
            print("╠══════════════════════════════════════════════════════════╣")
            print(f"║ Total Services: {total:<41} ║")
            print(f"║ Healthy: {healthy:<46} ║")
            print(f"║ Degraded: {degraded:<45} ║")
            print(f"║ Failed: {failed:<47} ║")
        
        incident_count = metrics.get("incident_count", 0)
        if incident_count > 0:
            print("╠══════════════════════════════════════════════════════════╣")
            print(f"║ Incidents: {incident_count:<44} ║")
        
        print("╚══════════════════════════════════════════════════════════╝")
    
    async def monitor(self, interval: int = 30):
        """Monitor tactical status continuously"""
        print(f"[TACTICAL] Starting continuous monitoring (interval: {interval}s)")
        print("Press Ctrl+C to stop monitoring\n")
        
        try:
            while True:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"\n=== TACTICAL MONITOR - {timestamp} ===")
                
                status = await self.get_status()
                self.print_status(status)
                
                print(f"\nNext update in {interval} seconds...")
                await asyncio.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n[TACTICAL] Monitoring stopped by user")
        except Exception as e:
            print(f"\n[TACTICAL] Monitoring error: {e}")


async def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="TMWS Tactical CLI - Bellona's Command Interface")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of TMWS server")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Get tactical status")
    
    # Health command
    health_parser = subparsers.add_parser("health", help="Get health check")
    
    # Metrics command
    metrics_parser = subparsers.add_parser("metrics", help="Get detailed metrics")
    
    # Restart command
    restart_parser = subparsers.add_parser("restart", help="Restart a service")
    restart_parser.add_argument("service", help="Service name to restart")
    
    # Optimize command
    optimize_parser = subparsers.add_parser("optimize", help="Run performance optimization")
    
    # Set mode command
    mode_parser = subparsers.add_parser("mode", help="Set tactical mode")
    mode_parser.add_argument("mode", choices=["peacetime", "alert", "critical", "maintenance"], 
                            help="Tactical mode to set")
    
    # Monitor command
    monitor_parser = subparsers.add_parser("monitor", help="Continuous monitoring")
    monitor_parser.add_argument("--interval", type=int, default=30, 
                               help="Monitoring interval in seconds")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    async with TacticalCLI(args.url) as cli:
        try:
            if args.command == "status":
                status = await cli.get_status()
                cli.print_status(status)
                
            elif args.command == "health":
                health = await cli.get_health()
                cli.print_health(health)
                
            elif args.command == "metrics":
                metrics = await cli.get_metrics()
                cli.print_metrics(metrics)
                
            elif args.command == "restart":
                result = await cli.execute_command("restart_service", {"service": args.service})
                if result.get("success"):
                    print(f"✅ {result['message']}")
                else:
                    print(f"❌ {result.get('message', 'Command failed')}")
                
            elif args.command == "optimize":
                result = await cli.execute_command("optimize")
                if result.get("success"):
                    print(f"✅ {result['message']}")
                else:
                    print(f"❌ {result.get('message', 'Command failed')}")
                
            elif args.command == "mode":
                result = await cli.execute_command("set_mode", {"mode": args.mode})
                if result.get("success"):
                    print(f"✅ {result['message']}")
                else:
                    print(f"❌ {result.get('message', 'Command failed')}")
                
            elif args.command == "monitor":
                await cli.monitor(args.interval)
                
        except aiohttp.ClientConnectorError:
            print(f"❌ Cannot connect to TMWS server at {args.url}")
            print("   Make sure the server is running and accessible.")
            sys.exit(1)
        except Exception as e:
            print(f"❌ CLI Error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())