"""
Health check endpoints for TMWS.
"""

import logging
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import get_settings
from ...core.database import get_db_session_dependency, DatabaseHealthCheck
# Middleware stats removed - integrated into unified middleware

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


@router.get("/")
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint.
    
    Returns basic service status without database dependency.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "TMWS",
        "version": settings.api_version,
        "environment": settings.environment
    }


@router.get("/detailed")
async def detailed_health_check(
    db: AsyncSession = Depends(get_db_session_dependency)
) -> Dict[str, Any]:
    """
    Detailed health check endpoint with database and service status.
    
    Checks:
    - Database connectivity
    - Application configuration
    - Middleware status
    - System resources
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }
    
    # Database health check
    try:
        db_healthy = await DatabaseHealthCheck.check_connection()
        pool_status = await DatabaseHealthCheck.get_pool_status()
        
        health_status["checks"]["database"] = {
            "status": "healthy" if db_healthy else "unhealthy",
            "connection": db_healthy,
            "pool": pool_status
        }
        
        if not db_healthy:
            health_status["status"] = "degraded"
            
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "unhealthy"
    
    # Application info
    try:
        app_info = {
            "name": settings.api_title,
            "version": settings.api_version,
            "environment": settings.environment,
        }
        health_status["checks"]["application"] = {
            "status": "healthy",
            "info": app_info
        }
    except Exception as e:
        logger.error(f"Application info check failed: {e}")
        health_status["checks"]["application"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "unhealthy"
    
    # Middleware status
    try:
        middleware_stats = {"status": "unified_middleware_active"}
        health_status["checks"]["middleware"] = {
            "status": "healthy",
            "stats": middleware_stats
        }
    except Exception as e:
        logger.error(f"Middleware status check failed: {e}")
        health_status["checks"]["middleware"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Configuration validation
    try:
        config_issues = []
        
        # Check critical configuration
        if settings.is_production:
            if settings.secret_key == "change-this-in-production-to-a-secure-random-key":
                config_issues.append("Insecure secret key in production")
            
            if settings.api_host == "0.0.0.0":
                config_issues.append("API host 0.0.0.0 in production")
            
            if not settings.cors_origins:
                config_issues.append("CORS origins not configured in production")
        
        health_status["checks"]["configuration"] = {
            "status": "healthy" if not config_issues else "degraded",
            "issues": config_issues,
            "environment": settings.environment
        }
        
        if config_issues and settings.is_production:
            health_status["status"] = "degraded"
            
    except Exception as e:
        logger.error(f"Configuration check failed: {e}")
        health_status["checks"]["configuration"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    return health_status


@router.get("/ready")
async def readiness_check(
    db: AsyncSession = Depends(get_db_session_dependency)
) -> Dict[str, Any]:
    """
    Kubernetes/Docker readiness probe endpoint.
    
    Returns 200 if service is ready to accept requests.
    Returns 503 if service is not ready.
    """
    try:
        # Check database connection
        if not await DatabaseHealthCheck.check_connection():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not ready"
            )
        
        # Check critical configuration in production
        if settings.is_production:
            if settings.secret_key == "change-this-in-production-to-a-secure-random-key":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Insecure configuration detected"
                )
        
        return {
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not ready"
        )


@router.get("/live")
async def liveness_check() -> Dict[str, Any]:
    """
    Kubernetes/Docker liveness probe endpoint.
    
    Returns 200 if service is alive and responsive.
    This should be a lightweight check.
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": (datetime.utcnow() - datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )).total_seconds()
    }


@router.get("/metrics")
async def metrics_endpoint(
    db: AsyncSession = Depends(get_db_session_dependency)
) -> Dict[str, Any]:
    """
    Basic metrics endpoint for monitoring.
    
    Returns application and database metrics.
    """
    try:
        # Database metrics
        pool_status = await DatabaseHealthCheck.get_pool_status()
        
        # Application metrics
        app_info = {
            "name": settings.api_title,
            "version": settings.api_version,
            "environment": settings.environment,
        }
        middleware_stats = {"status": "unified_middleware_active"}
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "service": {
                "name": settings.api_title,
                "version": settings.api_version,
                "environment": settings.environment
            },
            "database": {
                "pool_size": pool_status.get("pool_size", 0),
                "connections_in_use": pool_status.get("checked_out", 0),
                "connections_available": pool_status.get("checked_in", 0),
                "connections_overflow": pool_status.get("overflow", 0),
                "connections_invalid": pool_status.get("invalid", 0)
            },
            "middleware": middleware_stats,
            "configuration": {
                "rate_limiting_enabled": settings.rate_limit_enabled,
                "cors_enabled": bool(settings.cors_origins),
                "debug_mode": settings.is_development
            }
        }
        
    except Exception as e:
        logger.error(f"Metrics collection failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Metrics collection failed"
        )


@router.get("/version")
async def version_info() -> Dict[str, Any]:
    """
    Version information endpoint.
    
    Returns detailed version and build information.
    """
    return {
        "service": settings.api_title,
        "version": settings.api_version,
        "environment": settings.environment,
        "api": {
            "docs_enabled": not settings.is_production,
            "openapi_enabled": not settings.is_production
        },
        "build": {
            "timestamp": datetime.utcnow().isoformat(),
            "python_version": "3.11+",
            "framework": "FastAPI"
        }
    }