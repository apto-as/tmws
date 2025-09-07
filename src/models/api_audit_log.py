"""
API audit log models for TMWS - 404 Perfect Implementation.
Implements the exact database schema specification for api_audit_log table.
"""

from datetime import datetime
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Any, Dict, Optional, Union
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import String, Integer, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, validates
from sqlalchemy.sql import func

from .base import TMWSBase


class APIAuditLog(TMWSBase):
    """
    API audit log model implementing the exact TMWS database schema.
    
    Follows the specification:
    - UUID primary key with auto-generation
    - Endpoint and HTTP method tracking
    - Request and response body logging
    - User identification and IP address tracking
    - Response time measurement
    - HTTP method constraints
    """
    
    __tablename__ = "api_audit_log"
    
    # API call identification - matches spec exactly
    endpoint: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="API endpoint path"
    )
    
    method: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="HTTP method (GET, POST, PUT, DELETE, PATCH)"
    )
    
    # Request/Response data - exact spec
    request_body: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Request body in JSON format"
    )
    
    response_status: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="HTTP response status code"
    )
    
    response_body: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Response body in JSON format"
    )
    
    # User tracking - exact spec
    user_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="User identifier who made the request"
    )
    
    ip_address: Mapped[Optional[Union[IPv4Address, IPv6Address]]] = mapped_column(
        INET,
        nullable=True,
        comment="Client IP address"
    )
    
    # Performance tracking - exact spec
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Request processing duration in milliseconds"
    )
    
    # Table constraints - exact spec
    __table_args__ = (
        CheckConstraint(
            "method IN ('GET', 'POST', 'PUT', 'DELETE', 'PATCH')",
            name="chk_method"
        ),
        # Indexes for performance - matching spec exactly
        Index("idx_api_audit_log_endpoint", "endpoint"),
        Index("idx_api_audit_log_created_at", "created_at", postgresql_ops={"created_at": "DESC"}),
        Index("idx_api_audit_log_user_id", "user_id"),
    )
    
    @validates('method')
    def validate_method(self, key: str, method: str) -> str:
        """Validate HTTP method."""
        allowed_methods = {'GET', 'POST', 'PUT', 'DELETE', 'PATCH'}
        method_upper = method.upper()
        if method_upper not in allowed_methods:
            raise ValueError(f"Method must be one of: {allowed_methods}")
        return method_upper
    
    @validates('response_status')
    def validate_response_status(self, key: str, status: Optional[int]) -> Optional[int]:
        """Validate HTTP response status code."""
        if status is not None and not (100 <= status <= 599):
            raise ValueError("Response status must be between 100 and 599")
        return status
    
    @validates('ip_address')
    def validate_ip_address(self, key: str, ip_addr: Optional[str]) -> Optional[Union[IPv4Address, IPv6Address]]:
        """Validate and convert IP address."""
        if ip_addr is None:
            return None
        try:
            if isinstance(ip_addr, str):
                return ip_address(ip_addr)
            return ip_addr
        except ValueError as e:
            raise ValueError(f"Invalid IP address: {e}")
    
    def set_request_data(self, endpoint: str, method: str, body: Optional[Dict[str, Any]] = None) -> None:
        """Set request data with validation."""
        self.endpoint = endpoint
        self.method = method
        if body:
            self.request_body = body
    
    def set_response_data(self, status: int, body: Optional[Dict[str, Any]] = None) -> None:
        """Set response data with validation."""
        self.response_status = status
        if body:
            self.response_body = body
    
    def set_user_info(self, user_id: Optional[str] = None, ip_addr: Optional[str] = None) -> None:
        """Set user identification information."""
        if user_id:
            self.user_id = user_id
        if ip_addr:
            self.ip_address = ip_addr
    
    def set_duration(self, duration_ms: int) -> None:
        """Set request duration in milliseconds."""
        if duration_ms < 0:
            raise ValueError("Duration must be non-negative")
        self.duration_ms = duration_ms
    
    def set_duration_from_seconds(self, duration_seconds: float) -> None:
        """Set request duration from seconds."""
        duration_ms = int(duration_seconds * 1000)
        self.set_duration(duration_ms)
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Get duration in seconds."""
        if self.duration_ms is None:
            return None
        return self.duration_ms / 1000.0
    
    @property
    def is_error(self) -> bool:
        """Check if response indicates an error (status >= 400)."""
        return self.response_status is not None and self.response_status >= 400
    
    @property
    def is_success(self) -> bool:
        """Check if response indicates success (200 <= status < 400)."""
        return self.response_status is not None and 200 <= self.response_status < 400
    
    @property
    def is_slow(self, threshold_ms: int = 1000) -> bool:
        """Check if request was slow (duration > threshold)."""
        return self.duration_ms is not None and self.duration_ms > threshold_ms
    
    @property
    def response_category(self) -> Optional[str]:
        """Get response status category."""
        if self.response_status is None:
            return None
        
        if 100 <= self.response_status < 200:
            return "informational"
        elif 200 <= self.response_status < 300:
            return "success"
        elif 300 <= self.response_status < 400:
            return "redirection"
        elif 400 <= self.response_status < 500:
            return "client_error"
        elif 500 <= self.response_status < 600:
            return "server_error"
        else:
            return "unknown"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with enhanced audit information."""
        result = super().to_dict()
        result.update({
            "duration_seconds": self.duration_seconds,
            "is_error": self.is_error,
            "is_success": self.is_success,
            "response_category": self.response_category,
            "ip_address": str(self.ip_address) if self.ip_address else None,
        })
        return result
    
    def __repr__(self) -> str:
        """Enhanced string representation."""
        status_str = f", status={self.response_status}" if self.response_status else ""
        duration_str = f", duration={self.duration_ms}ms" if self.duration_ms else ""
        return (f"<APIAuditLog(id={self.id}, method={self.method}, "
                f"endpoint='{self.endpoint}'{status_str}{duration_str})>")
    
    @classmethod
    def log_request(cls, endpoint: str, method: str, user_id: Optional[str] = None, 
                   ip_address: Optional[str] = None, request_body: Optional[Dict[str, Any]] = None) -> "APIAuditLog":
        """Create a new audit log entry for a request."""
        log_entry = cls(
            endpoint=endpoint,
            method=method.upper(),
            user_id=user_id,
            ip_address=ip_address,
            request_body=request_body
        )
        return log_entry
    
    @classmethod
    def get_by_endpoint(cls, session, endpoint: str, limit: int = 100) -> list["APIAuditLog"]:
        """Get audit logs for specific endpoint."""
        return (session.query(cls)
                .filter(cls.endpoint == endpoint)
                .order_by(cls.created_at.desc())
                .limit(limit)
                .all())
    
    @classmethod
    def get_by_user(cls, session, user_id: str, limit: int = 100) -> list["APIAuditLog"]:
        """Get audit logs for specific user."""
        return (session.query(cls)
                .filter(cls.user_id == user_id)
                .order_by(cls.created_at.desc())
                .limit(limit)
                .all())
    
    @classmethod
    def get_errors(cls, session, limit: int = 100) -> list["APIAuditLog"]:
        """Get error responses (status >= 400)."""
        return (session.query(cls)
                .filter(cls.response_status >= 400)
                .order_by(cls.created_at.desc())
                .limit(limit)
                .all())
    
    @classmethod
    def get_slow_requests(cls, session, threshold_ms: int = 1000, limit: int = 100) -> list["APIAuditLog"]:
        """Get slow requests above threshold."""
        return (session.query(cls)
                .filter(cls.duration_ms > threshold_ms)
                .order_by(cls.duration_ms.desc())
                .limit(limit)
                .all())