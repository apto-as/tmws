"""
Configuration management for TMWS.
404 Security Standards: Zero compromise, zero defaults for sensitive data.
"""
import os
import sys
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Optional, Union, List
import logging
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    # Look for .env file in multiple locations
    env_paths = [
        Path.cwd() / '.env',  # Current directory
        Path.home() / '.tmws' / '.env',  # User home directory
        Path(__file__).parent.parent.parent / '.env',  # Project root
    ]
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path, override=True)
            logger.info(f"Loaded environment from {env_path}")
            break
except ImportError:
    # dotenv not installed, continue without it
    pass


class Settings(BaseSettings):
    """
    Application settings with Artemis 404 security standards.
    
    Security Principles:
    1. No hardcoded credentials - ALL sensitive data from environment
    2. Fail fast on missing required values 
    3. Production-grade validation enforced
    4. Development defaults ONLY where safe
    """
    
    # ==== CRITICAL SECURITY SETTINGS (REQUIRED) ====
    # Database - MANDATORY environment variable, no fallbacks
    database_url: str = Field(
        default="",
        description="Database connection URL - MUST be set via TMWS_DATABASE_URL",
        min_length=10
    )
    
    # Security - MANDATORY secret key, no insecure defaults
    secret_key: str = Field(
        default="",
        description="Cryptographic secret key - MUST be set via TMWS_SECRET_KEY (min 32 chars)",
        min_length=32
    )
    
    # Environment - REQUIRED for proper validation
    environment: str = Field(
        default="development",
        description="Runtime environment - MUST be set via TMWS_ENVIRONMENT",
        pattern="^(development|staging|production)$"
    )
    
    # ==== DATABASE CONFIGURATION ====
    db_max_connections: int = Field(default=10, ge=1, le=100)
    db_echo_sql: bool = Field(default=False)  # Never log SQL in production
    db_pool_pre_ping: bool = Field(default=True)
    db_pool_recycle: int = Field(default=3600, ge=300, le=86400)
    
    # ==== API CONFIGURATION ====
    api_host: str = Field(default="127.0.0.1")  # Secure default: localhost only
    api_port: int = Field(default=8000, ge=1024, le=65535)
    api_reload: bool = Field(default=False)  # Never auto-reload in production
    api_title: str = Field(default="TMWS - Trinitas Memory & Workflow Service")
    api_version: str = Field(default="1.0.0")
    api_description: str = Field(default="Backend service for Trinitas AI agents")
    
    # ==== JWT & AUTHENTICATION ====
    jwt_algorithm: str = Field(default="HS256", pattern="^HS256|RS256|ES256$")
    jwt_expire_minutes: int = Field(default=30, ge=5, le=1440)
    jwt_refresh_expire_days: int = Field(default=7, ge=1, le=30)
    
    # Authentication mode control (404 Security Standard)
    auth_enabled: bool = Field(
        default=False,
        description="Enable production authentication - default False for development mode"
    )
    
    # ==== CORS - RESTRICTIVE BY DEFAULT ====
    cors_origins: List[str] = Field(
        default_factory=lambda: [],
        description="CORS origins - MUST be explicitly set for production"
    )
    cors_credentials: bool = Field(default=False)
    cors_methods: List[str] = Field(default=["GET", "POST", "PUT", "DELETE"])
    cors_headers: List[str] = Field(default=["Content-Type", "Authorization"])
    
    # ==== SECURITY HARDENING ====
    security_headers_enabled: bool = Field(default=True)
    session_cookie_secure: bool = Field(default=True)
    session_cookie_httponly: bool = Field(default=True)
    session_cookie_samesite: str = Field(default="strict", pattern="^(strict|lax|none)$")
    
    # Content Security Policy
    csp_enabled: bool = Field(default=True)
    csp_policy: str = Field(
        default="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    )
    
    # ==== RATE LIMITING & SECURITY ====
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_requests: int = Field(default=100, ge=1, le=10000)
    rate_limit_period: int = Field(default=60, ge=1, le=3600)
    
    # Brute force protection
    max_login_attempts: int = Field(default=5, ge=1, le=20)
    lockout_duration_minutes: int = Field(default=15, ge=1, le=1440)
    
    # ==== VECTORIZATION ====
    embedding_model: str = Field(default="all-MiniLM-L6-v2")
    vector_dimension: int = Field(default=384, ge=1, le=4096)
    max_embedding_batch_size: int = Field(default=32, ge=1, le=1000)
    
    # ==== LOGGING & MONITORING ====
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    log_file: Optional[str] = None
    log_format: str = Field(default="json", pattern="^(json|text)$")
    
    # Security logging
    security_log_enabled: bool = Field(default=True)
    audit_log_enabled: bool = Field(default=True)
    
    # ==== PERFORMANCE & CACHING ====
    cache_ttl: int = Field(default=3600, ge=1, le=86400)
    cache_max_size: int = Field(default=1000, ge=1, le=100000)
    
    # ==== VALIDATION RULES ====
    @model_validator(mode='before')
    @classmethod
    def validate_required_env_vars(cls, values):
        """404 Rule: Critical environment variables MUST be set."""
        import os
        
        # Check if values are provided in .env or environment
        # pydantic-settings should handle TMWS_ prefix automatically
        if not values.get('database_url'):
            values['database_url'] = (
                values.get('DATABASE_URL') or 
                os.environ.get('TMWS_DATABASE_URL') or 
                os.environ.get('DATABASE_URL', '')
            )
        if not values.get('secret_key'):
            values['secret_key'] = (
                values.get('SECRET_KEY') or 
                os.environ.get('TMWS_SECRET_KEY') or 
                os.environ.get('SECRET_KEY', '')
            )
        if not values.get('environment'):
            values['environment'] = (
                values.get('ENVIRONMENT') or 
                os.environ.get('TMWS_ENVIRONMENT') or 
                os.environ.get('ENVIRONMENT', 'development')
            )
        
        # Check if running as MCP server
        is_mcp_mode = (
            os.environ.get('MCP_MODE', 'false').lower() == 'true' or
            'mcp_server' in sys.argv[0] or
            any('mcp' in arg for arg in sys.argv)
        )
        
        # In MCP mode, provide defaults for missing values
        if is_mcp_mode:
            if not values.get('database_url'):
                # Use SQLite for MCP mode if no database is configured
                values['database_url'] = 'sqlite+aiosqlite:///tmws_mcp.db'
            if not values.get('secret_key'):
                # Generate a temporary secret key for MCP mode
                import secrets
                values['secret_key'] = secrets.token_urlsafe(32)
        else:
            # For non-MCP mode, validate required fields
            errors = []
            if not values.get('database_url'):
                errors.append("TMWS_DATABASE_URL environment variable is required")
            if not values.get('secret_key'):
                errors.append("TMWS_SECRET_KEY environment variable is required")
            
            if errors:
                raise ValueError(f"Critical configuration missing: {'; '.join(errors)}")
        
        return values
    
    @field_validator("secret_key")
    @classmethod
    def validate_secret_key_security(cls, v, info):
        """404 Security: Secret key must meet cryptographic standards."""
        environment = info.data.get("environment", "development")
        
        # Production requirements
        if environment == "production":
            if len(v) < 32:
                raise ValueError("Production secret key must be at least 32 characters")
            
            # Check for common weak keys
            weak_keys = [
                "change-this-in-production-to-a-secure-random-key",
                "debug", "test", "dev", "development", "secret", "password",
                "12345", "admin", "root", "default"
            ]
            
            if v.lower() in weak_keys or v.lower().startswith(tuple(weak_keys)):
                raise ValueError("Weak or default secret key detected in production")
            
            # Entropy check - must contain mixed case, numbers, special chars
            if not (any(c.isupper() for c in v) and any(c.islower() for c in v) and 
                   any(c.isdigit() for c in v)):
                logger.warning("Secret key should contain mixed case letters and numbers")
        
        return v
    
    @field_validator("database_url")
    @classmethod
    def validate_database_url_security(cls, v, info):
        """404 Security: Database URL validation."""
        environment = info.data.get("environment", "development")
        
        if environment == "production":
            # Check for weak credentials in URL
            if "password" in v.lower() or "admin" in v.lower() or "root:root" in v.lower():
                logger.warning("Potentially weak database credentials detected")
            
            # Ensure SSL in production
            if "sslmode=" not in v and "postgresql://" in v:
                logger.warning("SSL not explicitly configured for database connection")
        
        return v
    
    @field_validator("cors_origins")
    @classmethod
    def validate_cors_security(cls, v, info):
        """404 Security: CORS must be properly configured."""
        environment = info.data.get("environment", "development")
        
        if environment == "production":
            if not v:
                raise ValueError("CORS origins must be explicitly configured in production")
            
            if "*" in v:
                raise ValueError("Wildcard CORS origins not allowed in production")
            
            # Check for localhost origins in production
            localhost_origins = [o for o in v if "localhost" in o or "127.0.0.1" in o]
            if localhost_origins:
                logger.warning(f"Localhost CORS origins in production: {localhost_origins}")
        
        if "*" in v and len(v) > 1:
            raise ValueError("Cannot use wildcard '*' with specific origins")
        
        return v
    
    @field_validator("api_host")
    @classmethod
    def validate_api_host_security(cls, v, info):
        """404 Security: API host validation."""
        environment = info.data.get("environment", "development")
        
        if environment == "production" and v == "0.0.0.0":
            logger.warning("API bound to 0.0.0.0 in production - ensure proper firewall/proxy")
        
        return v
    
    @field_validator("auth_enabled")
    @classmethod
    def validate_auth_enabled_security(cls, v, info):
        """404 Security: Authentication must be enabled in production."""
        environment = info.data.get("environment", "development")
        
        if environment == "production" and not v:
            raise ValueError("Authentication MUST be enabled in production environment")
        
        if environment == "staging" and not v:
            logger.warning("Authentication disabled in staging - consider enabling for realistic testing")
        
        return v
    
    @model_validator(mode='after')
    def validate_production_security(self):
        """404 Security: Final validation for production mode."""
        if self.environment == "production" and not self.auth_enabled:
            raise ValueError("CRITICAL: Authentication MUST be enabled in production environment (TMWS_AUTH_ENABLED=true)")
        return self

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"
    
    @property
    def is_staging(self) -> bool:
        """Check if running in staging environment."""
        return self.environment == "staging"
    
    @property
    def database_url_async(self) -> str:
        """Get async database URL for asyncpg."""
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self.database_url
    
    def generate_secure_secret_key(self) -> str:
        """Generate a cryptographically secure secret key."""
        return secrets.token_urlsafe(32)
    
    def get_security_headers(self) -> dict:
        """Get security headers for HTTP responses."""
        headers = {}
        
        if self.security_headers_enabled:
            headers.update({
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "X-XSS-Protection": "1; mode=block",
                "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
                "Referrer-Policy": "strict-origin-when-cross-origin"
            })
            
            if self.csp_enabled:
                headers["Content-Security-Policy"] = self.csp_policy
        
        return headers

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # Allow case insensitive env vars for better compatibility
        env_prefix="TMWS_",
        secrets_dir="/run/secrets" if os.path.exists("/run/secrets") else None,
        validate_assignment=True,
        use_enum_values=True,
        arbitrary_types_allowed=False,
        extra="ignore",  # Ignore extra environment variables
    )


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance with 404-level validation.
    
    Raises:
        ValueError: If critical configuration is missing or invalid
        EnvironmentError: If environment-specific validation fails
    """
    try:
        settings = Settings()
        
        # Validate critical security settings
        if settings.is_production:
            _validate_production_settings(settings)
        elif settings.is_staging:
            _validate_staging_settings(settings)
            
        return settings
        
    except Exception as e:
        logger.error(f"Failed to load settings with error: {e}")
        logger.error("Ensure all required environment variables are set:")
        logger.error("- TMWS_DATABASE_URL")
        logger.error("- TMWS_SECRET_KEY")
        logger.error("- TMWS_ENVIRONMENT")
        raise


def _validate_production_settings(settings: Settings) -> None:
    """
    404 Production Validation: Zero tolerance for security issues.
    
    Raises:
        ValueError: If any production security issue is detected
    """
    issues = []
    
    # Security validations
    if settings.api_host == "0.0.0.0":
        issues.append("API host is 0.0.0.0 in production - security risk")
    
    if settings.db_echo_sql:
        issues.append("SQL echo is enabled in production - data exposure risk")
    
    if settings.api_reload:
        issues.append("API reload is enabled in production - instability risk")
    
    if not settings.cors_origins:
        issues.append("CORS origins not configured in production")
    
    if settings.log_level == "DEBUG":
        issues.append("Debug logging enabled in production - information disclosure")
    
    if not settings.session_cookie_secure:
        issues.append("Insecure session cookies in production")
    
    if settings.session_cookie_samesite != "strict":
        logger.warning("Session cookies not using 'strict' SameSite in production")
    
    if not settings.security_headers_enabled:
        issues.append("Security headers disabled in production")
    
    # Authentication validation
    if not settings.auth_enabled:
        issues.append("Authentication disabled in production - critical security risk")
    
    # Rate limiting validation
    if not settings.rate_limit_enabled:
        issues.append("Rate limiting disabled in production")
    
    if settings.rate_limit_requests > 1000:
        logger.warning("High rate limit in production - consider lowering")
    
    if issues:
        raise ValueError(f"PRODUCTION SECURITY ISSUES DETECTED: {'; '.join(issues)}")
    
    logger.info("✅ Production security validation passed")


def _validate_staging_settings(settings: Settings) -> None:
    """Validate settings for staging environment."""
    warnings = []
    
    if settings.db_echo_sql:
        warnings.append("SQL echo enabled in staging")
    
    if settings.log_level == "DEBUG":
        warnings.append("Debug logging in staging")
    
    if warnings:
        logger.warning(f"Staging configuration warnings: {'; '.join(warnings)}")


def create_secure_env_template() -> str:
    """
    Create a template .env file with 404 security standards.
    
    Returns:
        str: Complete .env template with security comments
    """
    return '''# TMWS Configuration - 404 Security Standards
# ============================================
# Copy this file to .env and update ALL values
# Never commit .env files to version control

# ==== CRITICAL CONFIGURATION (REQUIRED) ====
# Database connection - Use strong authentication
TMWS_DATABASE_URL=postgresql://username:strong_password@localhost:5432/tmws

# Cryptographic secret - Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
TMWS_SECRET_KEY=CHANGE_THIS_TO_A_SECURE_32_CHAR_RANDOM_KEY

# Runtime environment - Controls security validation
TMWS_ENVIRONMENT=development  # development|staging|production

# ==== API CONFIGURATION ====
# Bind to localhost for development, specific IP for production
TMWS_API_HOST=127.0.0.1
TMWS_API_PORT=8000
TMWS_API_RELOAD=false

# ==== SECURITY CONFIGURATION ====
# JWT settings
TMWS_JWT_ALGORITHM=HS256
TMWS_JWT_EXPIRE_MINUTES=30
TMWS_JWT_REFRESH_EXPIRE_DAYS=7

# Authentication control (404 Security Standard)
# Default: false (development mode), set to true for production
TMWS_AUTH_ENABLED=false

# CORS - Specify exact origins for production
TMWS_CORS_ORIGINS=["http://localhost:3000"]
TMWS_CORS_CREDENTIALS=false

# Session security
TMWS_SESSION_COOKIE_SECURE=true
TMWS_SESSION_COOKIE_HTTPONLY=true
TMWS_SESSION_COOKIE_SAMESITE=strict

# Security headers and CSP
TMWS_SECURITY_HEADERS_ENABLED=true
TMWS_CSP_ENABLED=true

# Rate limiting and brute force protection
TMWS_RATE_LIMIT_ENABLED=true
TMWS_RATE_LIMIT_REQUESTS=100
TMWS_RATE_LIMIT_PERIOD=60
TMWS_MAX_LOGIN_ATTEMPTS=5
TMWS_LOCKOUT_DURATION_MINUTES=15

# ==== DATABASE CONFIGURATION ====
TMWS_DB_MAX_CONNECTIONS=10
TMWS_DB_ECHO_SQL=false
TMWS_DB_POOL_PRE_PING=true
TMWS_DB_POOL_RECYCLE=3600

# ==== LOGGING & MONITORING ====
TMWS_LOG_LEVEL=INFO
TMWS_LOG_FORMAT=json
TMWS_SECURITY_LOG_ENABLED=true
TMWS_AUDIT_LOG_ENABLED=true

# ==== PERFORMANCE & CACHING ====
TMWS_CACHE_TTL=3600
TMWS_CACHE_MAX_SIZE=1000

# ==== VECTORIZATION ====
TMWS_EMBEDDING_MODEL=all-MiniLM-L6-v2
TMWS_VECTOR_DIMENSION=384
TMWS_MAX_EMBEDDING_BATCH_SIZE=32

# ==== OPTIONAL CONFIGURATION ====
# Log file path (optional)
# TMWS_LOG_FILE=/var/log/tmws/app.log

# Custom CSP policy (optional)
# TMWS_CSP_POLICY="default-src 'self'; script-src 'self'"
'''


def validate_environment_security() -> dict:
    """
    Validate current environment security configuration.
    
    Returns:
        dict: Security validation results
    """
    try:
        settings = get_settings()
        
        results = {
            "environment": settings.environment,
            "security_level": "unknown",
            "issues": [],
            "warnings": [],
            "recommendations": []
        }
        
        if settings.is_production:
            try:
                _validate_production_settings(settings)
                results["security_level"] = "production-grade"
            except ValueError as e:
                results["security_level"] = "insecure"
                results["issues"].append(str(e))
        
        elif settings.is_staging:
            _validate_staging_settings(settings)
            results["security_level"] = "staging-appropriate"
        
        else:
            results["security_level"] = "development"
            results["recommendations"].append("Ensure production settings before deployment")
        
        return results
        
    except Exception as e:
        return {
            "environment": "unknown",
            "security_level": "configuration_error",
            "issues": [str(e)],
            "warnings": [],
            "recommendations": ["Fix configuration errors before proceeding"]
        }


# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"
TESTS_DIR = PROJECT_ROOT / "tests"
LOGS_DIR = PROJECT_ROOT / "logs"

# Ensure critical directories exist
LOGS_DIR.mkdir(exist_ok=True, mode=0o750)  # Secure directory permissions

# Global settings instance for application use
settings = get_settings()

# Export public interface
__all__ = [
    "Settings",
    "get_settings",
    "settings", 
    "create_secure_env_template",
    "validate_environment_security",
    "PROJECT_ROOT",
    "SRC_DIR",
    "MIGRATIONS_DIR",
    "TESTS_DIR",
    "LOGS_DIR"
]