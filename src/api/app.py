"""
Main FastAPI application for TMWS.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from ..core.config import get_settings
from ..core.database import create_tables, close_db_connections, DatabaseHealthCheck
from .middleware_unified import setup_middleware
from .routers import health, memory, persona, task, workflow

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("TMWS starting up...")
    
    try:
        # Initialize database
        await create_tables()
        logger.info("Database tables created/verified")
        
        # Verify database connection
        if not await DatabaseHealthCheck.check_connection():
            logger.error("Database health check failed during startup")
            raise Exception("Database connection failed")
        
        logger.info("TMWS startup completed successfully")
        
        # Application is ready
        yield
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    
    # Shutdown
    logger.info("TMWS shutting down...")
    
    try:
        # Close database connections
        await close_db_connections()
        logger.info("Database connections closed")
        
        logger.info("TMWS shutdown completed successfully")
        
    except Exception as e:
        logger.error(f"Shutdown error: {e}")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.
    
    Returns:
        Configured FastAPI application
    """
    
    # Create FastAPI app with security-focused configuration
    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        description=settings.api_description,
        lifespan=lifespan,
        
        # Security configurations
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        
        # Additional security settings
        swagger_ui_parameters={
            "persistAuthorization": False,
            "displayRequestDuration": True,
            "tryItOutEnabled": not settings.is_production,
        } if not settings.is_production else None,
    )
    
    # Setup unified middleware
    setup_middleware(app)
    
    # Include routers
    app.include_router(
        health.router,
        prefix="/health",
        tags=["health"]
    )
    
    app.include_router(
        memory.router,
        prefix="/api/v1/memory",
        tags=["memory"]
    )
    
    app.include_router(
        persona.router,
        prefix="/api/v1/personas",
        tags=["personas"]
    )
    
    app.include_router(
        task.router,
        prefix="/api/v1/tasks",
        tags=["tasks"]
    )
    
    app.include_router(
        workflow.router,
        prefix="/api/v1/workflows",
        tags=["workflows"]
    )
    
    # Root endpoint
    @app.get("/")
    async def root() -> Dict[str, Any]:
        """Root endpoint with basic API information."""
        return {
            "message": "TMWS - Trinitas Memory & Workflow Service",
            "version": settings.api_version,
            "environment": settings.environment,
            "status": "running",
            "docs_url": "/docs" if not settings.is_production else None,
        }
    
    # Global exception handlers
    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: HTTPException):
        """Handle 404 errors."""
        return JSONResponse(
            status_code=404,
            content={
                "error": "Not Found",
                "message": "The requested resource was not found",
                "path": str(request.url.path),
                "request_id": getattr(request.state, 'request_id', None)
            }
        )
    
    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc: Exception):
        """Handle 500 errors."""
        request_id = getattr(request.state, 'request_id', None)
        logger.error(f"Internal server error {request_id}: {str(exc)}", exc_info=True)
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred" if settings.is_production else str(exc),
                "request_id": request_id
            }
        )
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "status_code": exc.status_code,
                "request_id": getattr(request.state, 'request_id', None)
            }
        )
    
    # Validation error handler
    from fastapi.exceptions import RequestValidationError
    from pydantic import ValidationError
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle request validation errors."""
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "Validation Error",
                "message": "Request validation failed",
                "details": exc.errors(),
                "request_id": getattr(request.state, 'request_id', None)
            }
        )
    
    @app.exception_handler(ValidationError)
    async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
        """Handle Pydantic validation errors."""
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "Data Validation Error",
                "message": "Data validation failed",
                "details": exc.errors(),
                "request_id": getattr(request.state, 'request_id', None)
            }
        )
    
    # Add custom headers
    @app.middleware("http")
    async def add_api_headers(request: Request, call_next):
        """Add custom API headers."""
        response = await call_next(request)
        
        # API version header
        response.headers["X-API-Version"] = settings.api_version
        
        # Environment header (only in development)
        if settings.is_development:
            response.headers["X-Environment"] = settings.environment
        
        return response
    
    logger.info(f"FastAPI application created for {settings.environment} environment")
    
    return app


# Create application instance
app = create_app()


# Additional configuration for production
if settings.is_production:
    # Disable server header
    @app.middleware("http")
    async def remove_server_header(request: Request, call_next):
        response = await call_next(request)
        if "server" in response.headers:
            del response.headers["server"]
        return response
    
    logger.info("Production security configurations applied")


def get_app_info() -> Dict[str, Any]:
    """Get application information."""
    return {
        "name": settings.api_title,
        "version": settings.api_version,
        "environment": settings.environment,
        "debug": settings.is_development,
        "docs_enabled": not settings.is_production,
        "security_headers": True,
        "rate_limiting": settings.rate_limit_enabled,
        "cors_enabled": bool(settings.cors_origins),
        "database_url": settings.database_url_async.split('@')[0] + "@[REDACTED]",  # Hide credentials
    }
# Create default app instance for uvicorn
app = create_app()
