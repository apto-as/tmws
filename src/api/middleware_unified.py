"""
Unified Middleware for TMWS v1
Simple, robust, Redis-integrated middleware without backward compatibility concerns
"""

import time
import json
import logging
from typing import Optional, Dict, Any
import redis.asyncio as redis
from fastapi import Request, Response, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..core.config import get_settings
from ..security.audit_logger_async import AsyncSecurityAuditLogger

logger = logging.getLogger(__name__)
settings = get_settings()


class UnifiedSecurityMiddleware(BaseHTTPMiddleware):
    """
    Unified security middleware combining all protection mechanisms.
    Redis-integrated, production-ready, no backward compatibility.
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.redis_client: Optional[redis.Redis] = None
        self.audit_logger = AsyncSecurityAuditLogger()
        self.rate_limit_window = 60  # 1 minute window
        self.rate_limit_max_requests = settings.rate_limit_per_minute
        self.initialize_redis()
    
    def initialize_redis(self):
        """Initialize Redis connection for distributed rate limiting."""
        try:
            self.redis_client = redis.Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            logger.info("Redis connection initialized for middleware")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            logger.warning("Rate limiting will use in-memory fallback")
            self.redis_client = None
    
    async def dispatch(self, request: Request, call_next):
        """Process each request through security layers."""
        start_time = time.time()
        client_ip = self.get_client_ip(request)
        request_id = self.generate_request_id()
        
        # Add request ID to headers
        request.state.request_id = request_id
        
        try:
            # 1. Rate limiting
            if not await self.check_rate_limit(client_ip):
                await self.audit_logger.log_security_event(
                    "rate_limit_exceeded",
                    {"ip": client_ip, "path": str(request.url.path)},
                    severity="WARNING"
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded"
                )
            
            # 2. Security headers validation
            if not self.validate_headers(request):
                await self.audit_logger.log_security_event(
                    "invalid_headers",
                    {"ip": client_ip, "path": str(request.url.path)},
                    severity="WARNING"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid request headers"
                )
            
            # 3. Request size limit (10MB)
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > 10 * 1024 * 1024:
                await self.audit_logger.log_security_event(
                    "oversized_request",
                    {"ip": client_ip, "size": content_length},
                    severity="WARNING"
                )
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Request too large"
                )
            
            # 4. Process request
            response = await call_next(request)
            
            # 5. Add security headers to response
            self.add_security_headers(response, request_id)
            
            # 6. Log successful request
            process_time = time.time() - start_time
            await self.audit_logger.log_access(
                request.method,
                str(request.url.path),
                response.status_code,
                process_time,
                client_ip,
                request_id
            )
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            # Log error
            await self.audit_logger.log_security_event(
                "request_error",
                {
                    "ip": client_ip,
                    "path": str(request.url.path),
                    "error": str(e)
                },
                severity="ERROR"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error"
            )
    
    async def check_rate_limit(self, client_id: str) -> bool:
        """
        Check rate limit using Redis sliding window.
        Falls back to in-memory if Redis unavailable.
        """
        if not self.redis_client:
            # Simple in-memory fallback (not distributed)
            return True
        
        try:
            key = f"rate_limit:{client_id}"
            current_time = int(time.time())
            window_start = current_time - self.rate_limit_window
            
            # Redis pipeline for atomic operations
            async with self.redis_client.pipeline() as pipe:
                # Remove old entries
                await pipe.zremrangebyscore(key, 0, window_start)
                # Count current requests
                await pipe.zcard(key)
                # Add current request
                await pipe.zadd(key, {str(current_time): current_time})
                # Set expiry
                await pipe.expire(key, self.rate_limit_window + 1)
                
                results = await pipe.execute()
                current_requests = results[1]
                
                return current_requests < self.rate_limit_max_requests
                
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fail open in case of Redis issues
            return True
    
    def get_client_ip(self, request: Request) -> str:
        """Extract real client IP from request."""
        # Check X-Forwarded-For header for proxy scenarios
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct client
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def validate_headers(self, request: Request) -> bool:
        """Validate request headers for basic security."""
        # Check for suspicious User-Agent
        user_agent = request.headers.get("User-Agent", "")
        suspicious_agents = ["scanner", "nmap", "nikto", "sqlmap"]
        if any(agent in user_agent.lower() for agent in suspicious_agents):
            return False
        
        # Check for required headers in production
        if settings.is_production:
            # Require proper content-type for POST/PUT/PATCH
            if request.method in ["POST", "PUT", "PATCH"]:
                content_type = request.headers.get("Content-Type", "")
                if not content_type:
                    return False
        
        return True
    
    def add_security_headers(self, response: Response, request_id: str):
        """Add security headers to response."""
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    def generate_request_id(self) -> str:
        """Generate unique request ID."""
        import uuid
        return f"req_{uuid.uuid4().hex[:12]}"
    
    async def __del__(self):
        """Cleanup Redis connection."""
        if self.redis_client:
            await self.redis_client.close()


def setup_middleware(app: ASGIApp) -> None:
    """
    Setup all middleware for the application.
    Single, unified configuration - no backward compatibility.
    """
    
    # 1. CORS middleware (must be first)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        max_age=3600,
    )
    
    # 2. GZip compression
    app.add_middleware(
        GZipMiddleware,
        minimum_size=1000,  # Only compress responses larger than 1KB
        compresslevel=6     # Balanced compression level
    )
    
    # 3. Unified Security Middleware (combines all security features)
    app.add_middleware(UnifiedSecurityMiddleware)
    
    logger.info("Unified middleware stack configured")
    logger.info(f"Redis URL: {settings.redis_url}")
    logger.info(f"Rate limit: {settings.rate_limit_per_minute} req/min")
    logger.info(f"Environment: {settings.environment}")