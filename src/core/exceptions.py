"""
Custom exceptions for TMWS.
"""

from typing import Any, Dict, Optional


class TMWSException(Exception):
    """Base exception for TMWS."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class DatabaseException(TMWSException):
    """Database-related errors."""

    pass


class MemoryException(TMWSException):
    """Memory operation errors."""

    pass


class WorkflowException(TMWSException):
    """Workflow operation errors."""

    pass


class ValidationException(TMWSException):
    """Input validation errors."""

    pass


class ValidationError(ValidationException):
    """Alias for ValidationException for backward compatibility."""
    pass


class AuthenticationException(TMWSException):
    """Authentication errors."""

    pass


class AuthorizationException(TMWSException):
    """Authorization errors."""

    pass


class RateLimitException(TMWSException):
    """Rate limit exceeded errors."""

    pass


class VectorizationException(TMWSException):
    """Vector embedding errors."""

    pass


class NotFoundError(TMWSException):
    """Resource not found errors."""

    def __init__(self, resource_type: str, resource_id: str):
        message = f"{resource_type} with id '{resource_id}' not found"
        super().__init__(message, {"resource_type": resource_type, "resource_id": resource_id})