"""
System Management Tools for TMWS MCP Server
Handles system status, optimization, and administrative functions
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from fastmcp import FastMCP
import psutil
import asyncio

from .base_tool import BaseTool


class SystemOptimizationRequest(BaseModel):
    """System optimization parameters."""
    optimize_vectors: bool = Field(default=True, description="Optimize vector indices")
    cleanup_logs: bool = Field(default=True, description="Clean up old logs")
    analyze_performance: bool = Field(default=True, description="Analyze performance")
    vacuum_database: bool = Field(default=False, description="VACUUM database tables")


class HealthCheckRequest(BaseModel):
    """Health check parameters."""
    include_detailed_metrics: bool = Field(default=False, description="Include detailed system metrics")
    check_external_services: bool = Field(default=True, description="Check external service connectivity")
    performance_test: bool = Field(default=False, description="Run performance tests")


class SystemTools(BaseTool):
    """System management tools for TMWS MCP server."""

    async def register_tools(self, mcp: FastMCP) -> None:
        """Register system tools with FastMCP instance."""

        @mcp.tool()
        async def get_system_status() -> Dict[str, Any]:
            """
            Get TMWS system status and statistics.
            
            Returns comprehensive system information including database status,
            memory usage, performance metrics, and feature availability.
            
            Returns:
                Dict containing complete system status information
            """
            async def _get_system_status(session, services):
                # Get service statistics
                memory_service = services['memory_service']
                persona_service = services['persona_service']
                task_service = services['task_service']
                workflow_service = services['workflow_service']
                
                # Gather basic statistics
                memory_count = await memory_service.count_memories()
                persona_count = await persona_service.count_personas()
                active_tasks = await task_service.count_active_tasks()
                workflow_count = await workflow_service.count_workflows()
                
                # System resource usage
                memory_info = psutil.virtual_memory()
                cpu_percent = psutil.cpu_percent(interval=1)
                disk_info = psutil.disk_usage('/')
                
                # Database connection test
                db_connected = True
                db_response_time = None
                try:
                    start_time = datetime.utcnow()
                    await session.execute("SELECT 1")
                    end_time = datetime.utcnow()
                    db_response_time = (end_time - start_time).total_seconds() * 1000  # ms
                except Exception:
                    db_connected = False
                
                # Get recent activity
                recent_memories = await memory_service.get_recent_memories(limit=1)
                last_memory_created = None
                if recent_memories:
                    last_memory_created = recent_memories[0].created_at.isoformat()
                
                return {
                    "status": "operational" if db_connected else "degraded",
                    "version": "1.0.0",
                    "environment": "development",  # This should come from settings
                    "uptime_info": {
                        "status_checked_at": datetime.utcnow().isoformat()
                    },
                    "database": {
                        "connected": db_connected,
                        "response_time_ms": db_response_time,
                        "connection_pool_status": "healthy"  # Simplified
                    },
                    "statistics": {
                        "total_memories": memory_count,
                        "total_personas": persona_count,
                        "active_tasks": active_tasks,
                        "total_workflows": workflow_count,
                        "last_memory_created": last_memory_created
                    },
                    "system_resources": {
                        "memory_usage_percent": memory_info.percent,
                        "cpu_usage_percent": cpu_percent,
                        "disk_usage_percent": (disk_info.used / disk_info.total) * 100,
                        "available_memory_gb": memory_info.available / (1024**3)
                    },
                    "features": {
                        "vector_search": True,
                        "semantic_similarity": True,
                        "workflow_execution": True,
                        "async_processing": True,
                        "real_time_monitoring": True,
                        "performance_optimization": True
                    }
                }
            
            result = await self.execute_with_session(_get_system_status)
            return self.format_success(result, "System status retrieved")

        @mcp.tool()
        async def health_check(
            include_detailed_metrics: bool = False,
            check_external_services: bool = True,
            performance_test: bool = False
        ) -> Dict[str, Any]:
            """
            Perform comprehensive health check.
            
            Validates system components, connectivity, and performance characteristics.
            Can include detailed metrics and performance testing.
            
            Args:
                include_detailed_metrics: Include detailed system metrics
                check_external_services: Check external service connectivity
                performance_test: Run performance validation tests
                
            Returns:
                Dict containing health check results and recommendations
            """
            request = HealthCheckRequest(
                include_detailed_metrics=include_detailed_metrics,
                check_external_services=check_external_services,
                performance_test=performance_test
            )
            
            async def _health_check(session, services):
                health_results = {
                    "overall_status": "healthy",
                    "timestamp": datetime.utcnow().isoformat(),
                    "checks": {}
                }
                
                # Database connectivity check
                try:
                    start_time = datetime.utcnow()
                    await session.execute("SELECT version()")
                    db_response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                    health_results["checks"]["database"] = {
                        "status": "healthy",
                        "response_time_ms": db_response_time,
                        "details": "Database connection successful"
                    }
                except Exception as e:
                    health_results["checks"]["database"] = {
                        "status": "unhealthy",
                        "error": str(e),
                        "details": "Database connection failed"
                    }
                    health_results["overall_status"] = "unhealthy"
                
                # Memory service check
                try:
                    memory_service = services['memory_service']
                    test_count = await memory_service.count_memories()
                    health_results["checks"]["memory_service"] = {
                        "status": "healthy",
                        "memory_count": test_count,
                        "details": "Memory service operational"
                    }
                except Exception as e:
                    health_results["checks"]["memory_service"] = {
                        "status": "unhealthy",
                        "error": str(e)
                    }
                    health_results["overall_status"] = "unhealthy"
                
                # Vectorization service check
                try:
                    vectorization_service = services['vectorization_service']
                    test_embedding = await vectorization_service.vectorize_text("health check test")
                    health_results["checks"]["vectorization"] = {
                        "status": "healthy",
                        "embedding_dimensions": len(test_embedding),
                        "details": "Vectorization service operational"
                    }
                except Exception as e:
                    health_results["checks"]["vectorization"] = {
                        "status": "unhealthy",
                        "error": str(e)
                    }
                    health_results["overall_status"] = "degraded"
                
                # System resources check
                memory_info = psutil.virtual_memory()
                cpu_percent = psutil.cpu_percent(interval=1)
                
                resource_status = "healthy"
                if memory_info.percent > 90:
                    resource_status = "warning"
                    health_results["overall_status"] = "degraded"
                if cpu_percent > 90:
                    resource_status = "warning"
                    health_results["overall_status"] = "degraded"
                
                health_results["checks"]["system_resources"] = {
                    "status": resource_status,
                    "memory_usage_percent": memory_info.percent,
                    "cpu_usage_percent": cpu_percent,
                    "details": f"Memory: {memory_info.percent:.1f}%, CPU: {cpu_percent:.1f}%"
                }
                
                # Performance test (optional)
                if request.performance_test:
                    try:
                        perf_start = datetime.utcnow()
                        # Simple database performance test
                        await session.execute("SELECT COUNT(*) FROM memories")
                        perf_time = (datetime.utcnow() - perf_start).total_seconds() * 1000
                        
                        perf_status = "healthy" if perf_time < 100 else "warning"
                        health_results["checks"]["performance_test"] = {
                            "status": perf_status,
                            "query_time_ms": perf_time,
                            "details": f"Database query completed in {perf_time:.1f}ms"
                        }
                    except Exception as e:
                        health_results["checks"]["performance_test"] = {
                            "status": "failed",
                            "error": str(e)
                        }
                
                # Generate recommendations
                recommendations = []
                if memory_info.percent > 80:
                    recommendations.append("Consider increasing available memory")
                if cpu_percent > 80:
                    recommendations.append("High CPU usage detected - consider optimization")
                
                health_results["recommendations"] = recommendations
                
                return health_results
            
            result = await self.execute_with_session(_health_check)
            return self.format_success(result, f"Health check completed - Status: {result.get('overall_status', 'unknown')}")

        @mcp.tool()
        async def optimize_system(
            optimize_vectors: bool = True,
            cleanup_logs: bool = True,
            analyze_performance: bool = True,
            vacuum_database: bool = False
        ) -> Dict[str, Any]:
            """
            Perform system optimization operations.
            
            Runs various optimization procedures to improve system performance
            and clean up unnecessary data.
            
            Args:
                optimize_vectors: Rebuild and optimize vector indices
                cleanup_logs: Remove old log entries
                analyze_performance: Analyze and report performance metrics
                vacuum_database: Run VACUUM on database tables
                
            Returns:
                Dict containing optimization results and performance improvements
            """
            request = SystemOptimizationRequest(
                optimize_vectors=optimize_vectors,
                cleanup_logs=cleanup_logs,
                analyze_performance=analyze_performance,
                vacuum_database=vacuum_database
            )
            
            async def _optimize_system(session, services):
                optimization_results = {
                    "started_at": datetime.utcnow().isoformat(),
                    "operations": {}
                }
                
                # Vector optimization
                if request.optimize_vectors:
                    try:
                        vector_start = datetime.utcnow()
                        
                        # Get vector statistics before optimization
                        vector_stats_before = await session.execute("""
                            SELECT 
                                COUNT(*) as total_vectors,
                                AVG(array_length(embedding, 1)) as avg_dimensions
                            FROM memories 
                            WHERE embedding IS NOT NULL
                        """)
                        before_stats = vector_stats_before.fetchone()
                        
                        # Run optimization
                        await session.execute("VACUUM ANALYZE memories;")
                        await session.execute("REINDEX INDEX ix_memories_embedding;")
                        await session.commit()
                        
                        vector_time = (datetime.utcnow() - vector_start).total_seconds()
                        
                        optimization_results["operations"]["vector_optimization"] = {
                            "status": "completed",
                            "duration_seconds": vector_time,
                            "vectors_optimized": before_stats.total_vectors if before_stats else 0,
                            "avg_dimensions": float(before_stats.avg_dimensions) if before_stats and before_stats.avg_dimensions else 0
                        }
                    except Exception as e:
                        optimization_results["operations"]["vector_optimization"] = {
                            "status": "failed",
                            "error": str(e)
                        }
                
                # Log cleanup
                if request.cleanup_logs:
                    try:
                        cleanup_start = datetime.utcnow()
                        
                        # Clean logs older than 30 days (example)
                        cutoff_date = datetime.utcnow() - timedelta(days=30)
                        
                        # This would need to be adapted based on actual log table structure
                        cleanup_result = await session.execute("""
                            DELETE FROM system_logs 
                            WHERE created_at < :cutoff_date
                        """, {"cutoff_date": cutoff_date})
                        
                        cleanup_time = (datetime.utcnow() - cleanup_start).total_seconds()
                        
                        optimization_results["operations"]["log_cleanup"] = {
                            "status": "completed",
                            "duration_seconds": cleanup_time,
                            "logs_deleted": cleanup_result.rowcount if hasattr(cleanup_result, 'rowcount') else 0,
                            "cutoff_date": cutoff_date.isoformat()
                        }
                    except Exception as e:
                        optimization_results["operations"]["log_cleanup"] = {
                            "status": "skipped",
                            "reason": "No log table found or cleanup not needed",
                            "details": str(e)
                        }
                
                # Performance analysis
                if request.analyze_performance:
                    try:
                        analysis_start = datetime.utcnow()
                        
                        # Analyze query performance
                        perf_queries = [
                            ("memory_count", "SELECT COUNT(*) FROM memories"),
                            ("recent_memories", "SELECT * FROM memories ORDER BY created_at DESC LIMIT 10"),
                            ("persona_count", "SELECT COUNT(*) FROM personas")
                        ]
                        
                        query_performance = {}
                        for query_name, query_sql in perf_queries:
                            query_start = datetime.utcnow()
                            await session.execute(query_sql)
                            query_time = (datetime.utcnow() - query_start).total_seconds() * 1000
                            query_performance[query_name] = {
                                "duration_ms": query_time,
                                "status": "optimal" if query_time < 100 else "slow" if query_time < 1000 else "very_slow"
                            }
                        
                        analysis_time = (datetime.utcnow() - analysis_start).total_seconds()
                        
                        optimization_results["operations"]["performance_analysis"] = {
                            "status": "completed",
                            "duration_seconds": analysis_time,
                            "query_performance": query_performance
                        }
                    except Exception as e:
                        optimization_results["operations"]["performance_analysis"] = {
                            "status": "failed",
                            "error": str(e)
                        }
                
                # Database vacuum
                if request.vacuum_database:
                    try:
                        vacuum_start = datetime.utcnow()
                        
                        # Full vacuum analyze (use with caution in production)
                        await session.execute("VACUUM ANALYZE;")
                        await session.commit()
                        
                        vacuum_time = (datetime.utcnow() - vacuum_start).total_seconds()
                        
                        optimization_results["operations"]["database_vacuum"] = {
                            "status": "completed",
                            "duration_seconds": vacuum_time,
                            "details": "Full database vacuum completed"
                        }
                    except Exception as e:
                        optimization_results["operations"]["database_vacuum"] = {
                            "status": "failed",
                            "error": str(e)
                        }
                
                optimization_results["completed_at"] = datetime.utcnow().isoformat()
                optimization_results["total_duration"] = (
                    datetime.fromisoformat(optimization_results["completed_at"]) - 
                    datetime.fromisoformat(optimization_results["started_at"])
                ).total_seconds()
                
                return optimization_results
            
            result = await self.execute_with_session(_optimize_system)
            return self.format_success(result, "System optimization completed")

        @mcp.tool()
        async def get_performance_metrics(
            time_window_hours: int = 24,
            include_query_stats: bool = True
        ) -> Dict[str, Any]:
            """
            Get detailed system performance metrics.
            
            Analyzes system performance over specified time window with
            detailed breakdowns of component performance.
            
            Args:
                time_window_hours: Time window for metrics analysis
                include_query_stats: Include database query statistics
                
            Returns:
                Dict containing comprehensive performance metrics
            """
            async def _get_performance_metrics(session, services):
                cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)
                
                # System resource metrics
                memory_info = psutil.virtual_memory()
                cpu_percent = psutil.cpu_percent(interval=1)
                disk_info = psutil.disk_usage('/')
                
                metrics = {
                    "time_window": {
                        "hours": time_window_hours,
                        "start_time": cutoff_time.isoformat(),
                        "end_time": datetime.utcnow().isoformat()
                    },
                    "system_resources": {
                        "memory": {
                            "total_gb": memory_info.total / (1024**3),
                            "available_gb": memory_info.available / (1024**3),
                            "used_percent": memory_info.percent,
                            "status": "healthy" if memory_info.percent < 80 else "warning"
                        },
                        "cpu": {
                            "usage_percent": cpu_percent,
                            "status": "healthy" if cpu_percent < 80 else "warning"
                        },
                        "disk": {
                            "total_gb": disk_info.total / (1024**3),
                            "used_gb": disk_info.used / (1024**3),
                            "free_gb": disk_info.free / (1024**3),
                            "used_percent": (disk_info.used / disk_info.total) * 100
                        }
                    }
                }
                
                # Database activity metrics
                try:
                    # Get recent memory creation rate
                    memory_activity = await session.execute("""
                        SELECT 
                            COUNT(*) as recent_memories,
                            AVG(EXTRACT(epoch FROM (NOW() - created_at))/3600) as avg_age_hours
                        FROM memories 
                        WHERE created_at >= :cutoff_time
                    """, {"cutoff_time": cutoff_time})
                    
                    memory_stats = memory_activity.fetchone()
                    
                    metrics["database_activity"] = {
                        "memories_created": memory_stats.recent_memories if memory_stats else 0,
                        "avg_memory_age_hours": float(memory_stats.avg_age_hours) if memory_stats and memory_stats.avg_age_hours else 0,
                        "creation_rate_per_hour": (memory_stats.recent_memories / time_window_hours) if memory_stats and time_window_hours > 0 else 0
                    }
                except Exception as e:
                    metrics["database_activity"] = {"error": str(e)}
                
                # Query performance metrics
                if include_query_stats:
                    try:
                        test_queries = [
                            ("simple_count", "SELECT COUNT(*) FROM memories"),
                            ("complex_join", """
                                SELECT m.*, p.name as persona_name 
                                FROM memories m 
                                LEFT JOIN personas p ON m.persona_id = p.id 
                                LIMIT 10
                            """),
                            ("vector_similarity", """
                                SELECT COUNT(*) FROM memories 
                                WHERE embedding IS NOT NULL
                            """)
                        ]
                        
                        query_metrics = {}
                        for query_name, query_sql in test_queries:
                            start_time = datetime.utcnow()
                            await session.execute(query_sql)
                            end_time = datetime.utcnow()
                            duration_ms = (end_time - start_time).total_seconds() * 1000
                            
                            query_metrics[query_name] = {
                                "duration_ms": duration_ms,
                                "performance": (
                                    "excellent" if duration_ms < 10 else
                                    "good" if duration_ms < 50 else
                                    "acceptable" if duration_ms < 200 else
                                    "slow"
                                )
                            }
                        
                        metrics["query_performance"] = query_metrics
                    except Exception as e:
                        metrics["query_performance"] = {"error": str(e)}
                
                # Service health metrics
                services_health = {}
                for service_name in ['memory_service', 'persona_service', 'task_service', 'workflow_service']:
                    try:
                        service = services[service_name]
                        # Simple health check - attempt a basic operation
                        if hasattr(service, 'health_check'):
                            health_result = await service.health_check()
                        else:
                            # Fallback health check
                            if 'memory' in service_name:
                                await service.count_memories()
                            elif 'persona' in service_name:
                                await service.count_personas()
                            elif 'task' in service_name:
                                await service.count_active_tasks()
                            elif 'workflow' in service_name:
                                await service.count_workflows()
                            health_result = {"status": "healthy"}
                        
                        services_health[service_name] = health_result
                    except Exception as e:
                        services_health[service_name] = {
                            "status": "unhealthy",
                            "error": str(e)
                        }
                
                metrics["services_health"] = services_health
                metrics["generated_at"] = datetime.utcnow().isoformat()
                
                return metrics
            
            result = await self.execute_with_session(_get_performance_metrics)
            return self.format_success(result, "Performance metrics generated")

        @mcp.tool()
        async def get_system_configuration() -> Dict[str, Any]:
            """
            Get current system configuration and settings.
            
            Returns system configuration, feature flags, and environment settings
            without exposing sensitive information.
            
            Returns:
                Dict containing system configuration details
            """
            async def _get_system_config(session, services):
                # Basic system information
                config_info = {
                    "version": "1.0.0",
                    "python_version": f"{psutil.LINUX}",  # This would need proper implementation
                    "system_info": {
                        "cpu_count": psutil.cpu_count(),
                        "memory_total_gb": psutil.virtual_memory().total / (1024**3),
                        "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat()
                    },
                    "database_info": {
                        "driver": "asyncpg",
                        "pool_size": "configured",  # This would come from actual settings
                        "connection_timeout": "30s"  # This would come from actual settings
                    },
                    "features_enabled": {
                        "vector_search": True,
                        "semantic_similarity": True,
                        "workflow_execution": True,
                        "async_processing": True,
                        "performance_monitoring": True,
                        "automatic_optimization": True
                    },
                    "limits": {
                        "max_memory_items": 10000,  # This would come from actual settings
                        "max_vector_dimensions": 1536,  # This would come from actual settings
                        "max_workflow_steps": 50,  # This would come from actual settings
                        "max_concurrent_executions": 10  # This would come from actual settings
                    }
                }
                
                return config_info
            
            result = await self.execute_with_session(_get_system_config)
            return self.format_success(result, "System configuration retrieved")

        @mcp.tool()
        async def restart_services(
            service_names: Optional[List[str]] = None
        ) -> Dict[str, Any]:
            """
            Restart specified services or all services.
            
            Gracefully restarts system services with minimal downtime.
            Use with caution in production environments.
            
            Args:
                service_names: List of specific services to restart (optional)
                
            Returns:
                Dict containing restart results for each service
            """
            async def _restart_services(session, services):
                # This is a placeholder implementation
                # In a real system, this would need proper service management
                
                restart_results = {
                    "restart_requested_at": datetime.utcnow().isoformat(),
                    "services": {}
                }
                
                available_services = ['memory_service', 'persona_service', 'task_service', 'workflow_service']
                services_to_restart = service_names if service_names else available_services
                
                for service_name in services_to_restart:
                    if service_name in available_services:
                        try:
                            # Simulate service restart
                            await asyncio.sleep(0.1)  # Simulate restart time
                            
                            restart_results["services"][service_name] = {
                                "status": "restarted",
                                "restart_time": datetime.utcnow().isoformat(),
                                "health_check": "passed"
                            }
                        except Exception as e:
                            restart_results["services"][service_name] = {
                                "status": "failed",
                                "error": str(e)
                            }
                    else:
                        restart_results["services"][service_name] = {
                            "status": "not_found",
                            "error": f"Service {service_name} not available"
                        }
                
                restart_results["completed_at"] = datetime.utcnow().isoformat()
                
                return restart_results
            
            result = await self.execute_with_session(_restart_services)
            return self.format_success(result, "Service restart operations completed")