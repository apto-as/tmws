"""
Security Audit Integration Module
Bridges async audit logger with existing API audit log
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import Request

from ..core.database import get_db_session_dependency
from ..models.api_audit_log import APIAuditLog
from .audit_logger_async import AsyncSecurityAuditLogger, SecurityEventType, SecurityEventSeverity
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Global instance
_audit_logger: Optional[AsyncSecurityAuditLogger] = None


async def initialize_audit_logger():
    """Initialize the async security audit logger."""
    global _audit_logger
    if _audit_logger is None:
        from ..core.config import get_settings
        settings = get_settings()
        _audit_logger = AsyncSecurityAuditLogger(
            log_dir="logs/security",
            max_file_size_mb=100,
            backup_count=10,
            enable_encryption=settings.is_production
        )
        await _audit_logger.initialize()
        logger.info("Security audit logger initialized")
    return _audit_logger


async def log_security_event(
    event_type: SecurityEventType,
    request: Request,
    severity: SecurityEventSeverity = SecurityEventSeverity.MEDIUM,
    details: Optional[Dict[str, Any]] = None,
    db_session: Optional[AsyncSession] = None
):
    """
    Log a security event to both async logger and database.
    
    Args:
        event_type: Type of security event
        request: FastAPI request object
        severity: Event severity level
        details: Additional event details
        db_session: Optional database session
    """
    try:
        # Get client info from request
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")
        request_id = getattr(request.state, 'request_id', None)
        
        # Log to async security logger
        audit_logger = await initialize_audit_logger()
        if audit_logger:
            await audit_logger.log_event(
                event_type=event_type,
                severity=severity,
                client_ip=client_ip,
                user_id=details.get("user_id") if details else None,
                session_id=request_id,
                endpoint=str(request.url.path),
                method=request.method,
                user_agent=user_agent,
                details=details,
                request=request
            )
        
        # Also log to database if session provided
        if db_session and event_type in [
            SecurityEventType.LOGIN_FAILED,
            SecurityEventType.UNAUTHORIZED_ACCESS,
            SecurityEventType.SQL_INJECTION_ATTEMPT,
            SecurityEventType.RATE_LIMIT_EXCEEDED
        ]:
            audit_log = APIAuditLog(
                endpoint=str(request.url.path),
                method=request.method[:10],  # Limit to 10 chars as per schema
                request_body=details,
                response_status=429 if event_type == SecurityEventType.RATE_LIMIT_EXCEEDED else 401,
                user_id=details.get("user_id") if details else None,
                ip_address=client_ip
            )
            db_session.add(audit_log)
            await db_session.commit()
            
    except Exception as e:
        logger.error(f"Failed to log security event: {e}")


async def cleanup_audit_logger():
    """Cleanup audit logger resources."""
    global _audit_logger
    if _audit_logger:
        await _audit_logger.cleanup()
        _audit_logger = None