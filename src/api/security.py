"""
Security utilities for TMWS API.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from jose import jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext

from ..core.config import get_settings

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Bearer token authentication
security = HTTPBearer(auto_error=False)  # Make authentication optional

settings = get_settings()


class SecurityConfig:
    """Security configuration and utilities."""
    
    # JWT settings
    ALGORITHM = settings.jwt_algorithm
    SECRET_KEY = settings.secret_key
    ACCESS_TOKEN_EXPIRE_MINUTES = settings.jwt_expire_minutes
    
    # Password validation
    MIN_PASSWORD_LENGTH = 12
    REQUIRE_SPECIAL_CHARS = True
    REQUIRE_NUMBERS = True
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def get_password_hash(password: str) -> str:
    """Generate password hash."""
    return pwd_context.hash(password)


def validate_password_strength(password: str) -> tuple[bool, list[str]]:
    """
    Validate password strength.
    
    Returns:
        (is_valid, list_of_issues)
    """
    issues = []
    
    if len(password) < SecurityConfig.MIN_PASSWORD_LENGTH:
        issues.append(f"Password must be at least {SecurityConfig.MIN_PASSWORD_LENGTH} characters long")
    
    if SecurityConfig.REQUIRE_LOWERCASE and not any(c.islower() for c in password):
        issues.append("Password must contain at least one lowercase letter")
    
    if SecurityConfig.REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
        issues.append("Password must contain at least one uppercase letter")
    
    if SecurityConfig.REQUIRE_NUMBERS and not any(c.isdigit() for c in password):
        issues.append("Password must contain at least one number")
    
    if SecurityConfig.REQUIRE_SPECIAL_CHARS and not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        issues.append("Password must contain at least one special character")
    
    # Check for common weak patterns
    weak_patterns = ["password", "123456", "qwerty", "admin", "user"]
    if any(pattern in password.lower() for pattern in weak_patterns):
        issues.append("Password contains common weak patterns")
    
    return len(issues) == 0, issues


def create_access_token(
    data: Dict[str, Any], 
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create JWT access token.
    
    Args:
        data: Payload data to encode
        expires_delta: Token expiration time
        
    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=SecurityConfig.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access_token"
    })
    
    try:
        encoded_jwt = jwt.encode(
            to_encode, 
            SecurityConfig.SECRET_KEY, 
            algorithm=SecurityConfig.ALGORITHM
        )
        return encoded_jwt
    except Exception as e:
        logger.error(f"Token creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create access token"
        )


def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode JWT token.
    
    Args:
        token: JWT token to verify
        
    Returns:
        Decoded token payload
        
    Raises:
        HTTPException: If token is invalid
    """
    try:
        payload = jwt.decode(
            token, 
            SecurityConfig.SECRET_KEY, 
            algorithms=[SecurityConfig.ALGORITHM]
        )
        
        # Validate token type
        if payload.get("type") != "access_token":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check expiration
        exp = payload.get("exp")
        if exp is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing expiration",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if datetime.fromtimestamp(exp) < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return payload
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Dict[str, Any]:
    """
    Get current user from JWT token.
    
    Authentication Mode (404 Security Standard):
    - Default: Development mode (no authentication required)
    - Production: Explicit authentication required (auth_enabled=True)
    - This ensures development ease while forcing production security
    
    Args:
        credentials: HTTP authorization credentials
        
    Returns:
        Current user data
        
    Raises:
        HTTPException: If authentication fails in production mode
    """
    # 404 Security Rule: Development mode is DEFAULT unless explicitly enabled
    # This reverses the logic - auth must be explicitly enabled for production
    if not settings.auth_enabled:
        # Development/testing mode - return mock user
        return {
            "user_id": "dev_user",
            "username": "developer", 
            "role": "admin",
            "roles": ["admin", "developer"],
            "permissions": ["*"],  # All permissions in dev mode
            "is_active": True,
            "auth_mode": "development"
        }
    
    # Production authentication enabled - require valid credentials
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required - missing credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify token
    payload = verify_token(credentials.credentials)
    
    # Extract user information
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token - missing user identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {
        "id": user_id,
        "username": payload.get("username"),
        "roles": payload.get("roles", []),
        "permissions": payload.get("permissions", []),
        "token_data": payload,
        "auth_mode": "production"
    }


def require_permission(permission: str):
    """
    Dependency to require specific permission.
    
    Args:
        permission: Required permission
        
    Returns:
        Dependency function
    """
    async def permission_checker(
        current_user: Dict[str, Any] = Depends(get_current_user)
    ) -> Dict[str, Any]:
        # Development mode grants all permissions
        if current_user.get("auth_mode") == "development":
            return current_user
            
        user_permissions = current_user.get("permissions", [])
        
        # Check for wildcard permission (development mode)
        if "*" in user_permissions:
            return current_user
        
        # Standard permission check
        if permission not in user_permissions and "admin" not in current_user.get("roles", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission}"
            )
        
        return current_user
    
    return permission_checker


def require_role(role: str):
    """
    Dependency to require specific role.
    
    Args:
        role: Required role
        
    Returns:
        Dependency function
    """
    async def role_checker(
        current_user: Dict[str, Any] = Depends(get_current_user)
    ) -> Dict[str, Any]:
        # Development mode grants all roles
        if current_user.get("auth_mode") == "development":
            return current_user
            
        user_roles = current_user.get("roles", [])
        
        if role not in user_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role required: {role}"
            )
        
        return current_user
    
    return role_checker


class SecurityHeaders:
    """Security headers for HTTP responses."""
    
    @staticmethod
    def get_security_headers() -> Dict[str, str]:
        """Get recommended security headers."""
        return {
            # Prevent MIME type sniffing
            "X-Content-Type-Options": "nosniff",
            
            # Prevent clickjacking
            "X-Frame-Options": "DENY",
            
            # XSS protection
            "X-XSS-Protection": "1; mode=block",
            
            # HSTS (HTTPS only)
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            
            # Content Security Policy
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'none';"
            ),
            
            # Referrer policy
            "Referrer-Policy": "strict-origin-when-cross-origin",
            
            # Feature policy
            "Permissions-Policy": (
                "geolocation=(), "
                "microphone=(), "
                "camera=(), "
                "payment=(), "
                "usb=(), "
                "magnetometer=(), "
                "gyroscope=(), "
                "speaker=()"
            ),
        }


def get_auth_status() -> Dict[str, Any]:
    """
    Get current authentication status and configuration.
    
    Returns:
        Dict containing authentication status information
    """
    return {
        "auth_enabled": settings.auth_enabled,
        "environment": settings.environment,
        "auth_mode": "production" if settings.auth_enabled else "development",
        "security_level": "high" if settings.auth_enabled else "development",
        "jwt_algorithm": SecurityConfig.ALGORITHM,
        "token_expire_minutes": SecurityConfig.ACCESS_TOKEN_EXPIRE_MINUTES,
        "description": (
            "Production authentication enabled - JWT tokens required"
            if settings.auth_enabled
            else "Development mode - no authentication required"
        )
    }


def sanitize_input(input_string: str, max_length: int = 1000) -> str:
    """
    Sanitize user input.
    
    Args:
        input_string: Input to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized input string
        
    Raises:
        HTTPException: If input is invalid
    """
    if not input_string:
        return ""
    
    # Check length
    if len(input_string) > max_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Input too long. Maximum {max_length} characters allowed."
        )
    
    # Remove potential XSS attempts
    dangerous_patterns = ["<script", "javascript:", "onload=", "onerror=", "eval("]
    input_lower = input_string.lower()
    
    for pattern in dangerous_patterns:
        if pattern in input_lower:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Input contains potentially dangerous content"
            )
    
    # Basic sanitization - remove control characters
    sanitized = "".join(char for char in input_string if ord(char) >= 32 or char in "\n\r\t")
    
    return sanitized.strip()


# Export public interface
__all__ = [
    "SecurityConfig",
    "verify_password",
    "get_password_hash", 
    "validate_password_strength",
    "create_access_token",
    "verify_token",
    "get_current_user",
    "require_permission",
    "require_role",
    "SecurityHeaders",
    "get_auth_status",
    "sanitize_input",
    "security"  # HTTPBearer instance
]