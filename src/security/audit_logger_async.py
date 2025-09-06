"""
Security Audit Logging Module - Async Version
Hestia's Comprehensive Security Event Tracking with Full Async Support

"……すべてのセキュリティイベントを記録します……証拠を残さない攻撃者はいません……"
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from dataclasses import dataclass, asdict
from pathlib import Path
import asyncio
import hashlib
import geoip2.database
import geoip2.errors
from fastapi import Request
from sqlalchemy import Column, String, DateTime, JSON, Integer, Boolean
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import select

from ..core.config import get_settings

logger = logging.getLogger(__name__)

Base = declarative_base()


class SecurityEventType(Enum):
    """Types of security events to track."""
    
    # Authentication Events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGIN_BLOCKED = "login_blocked"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    ACCOUNT_LOCKED = "account_locked"
    
    # Authorization Events
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    PERMISSION_DENIED = "permission_denied"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    
    # Input Validation Events
    INPUT_VALIDATION_FAILED = "input_validation_failed"
    SQL_INJECTION_ATTEMPT = "sql_injection_attempt"
    XSS_ATTEMPT = "xss_attempt"
    PATH_TRAVERSAL_ATTEMPT = "path_traversal_attempt"
    COMMAND_INJECTION_ATTEMPT = "command_injection_attempt"
    
    # Rate Limiting Events
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    DDOS_DETECTED = "ddos_detected"
    SUSPICIOUS_TRAFFIC = "suspicious_traffic"
    IP_BLOCKED = "ip_blocked"
    
    # Data Security Events
    SENSITIVE_DATA_ACCESS = "sensitive_data_access"
    DATA_EXPORT = "data_export"
    BULK_OPERATION = "bulk_operation"
    
    # System Security Events
    CONFIGURATION_CHANGE = "configuration_change"
    ADMIN_ACTION = "admin_action"
    SYSTEM_COMPROMISE = "system_compromise"
    MALWARE_DETECTED = "malware_detected"
    
    # API Security Events
    API_ABUSE = "api_abuse"
    UNUSUAL_API_PATTERN = "unusual_api_pattern"
    BOT_DETECTED = "bot_detected"
    
    # Vector Security Events
    VECTOR_INJECTION_ATTEMPT = "vector_injection_attempt"
    EMBEDDING_ABUSE = "embedding_abuse"
    UNUSUAL_VECTOR_PATTERN = "unusual_vector_pattern"


class SecurityEventSeverity(Enum):
    """Security event severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityEvent:
    """Security event data structure."""
    event_type: SecurityEventType
    severity: SecurityEventSeverity
    timestamp: datetime
    client_ip: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    user_agent: Optional[str] = None
    referer: Optional[str] = None
    message: Optional[str] = None
    details: Dict[str, Any] = None
    location: Optional[Dict[str, str]] = None
    risk_score: int = 0
    blocked: bool = False


class SecurityAuditLog(Base):
    """Database model for security audit logs."""
    __tablename__ = 'security_audit_logs'
    
    id = Column(Integer, primary_key=True)
    event_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    client_ip = Column(String(45), nullable=False, index=True)
    user_id = Column(String(100), index=True)
    session_id = Column(String(100), index=True)
    endpoint = Column(String(255))
    method = Column(String(10))
    user_agent = Column(String(500))
    referer = Column(String(500))
    message = Column(String(1000))
    details = Column(JSON)
    location = Column(JSON)
    risk_score = Column(Integer, default=0, index=True)
    blocked = Column(Boolean, default=False)
    event_hash = Column(String(16), index=True)


class AsyncSecurityAuditLogger:
    """
    Comprehensive async security audit logging system.
    Hestia's Rule: Every security event must be tracked and analyzed - now without blocking.
    """
    
    def __init__(self):
        """Initialize async audit logger."""
        self.settings = get_settings()
        self.engine = None
        self.async_session_maker = None
        self.geoip_reader = None
        
        # Risk scoring patterns
        self.risk_patterns = {
            'high_risk_ips': set(),  # Known bad IPs
            'suspicious_user_agents': [
                'sqlmap', 'nikto', 'burp', 'nessus', 'openvas'
            ],
            'attack_endpoints': [
                'admin', 'wp-admin', 'phpmyadmin', '.env', 'config'
            ]
        }
    
    async def initialize(self) -> None:
        """Initialize async components."""
        # Initialize database
        await self._init_database()
        
        # Initialize GeoIP (optional)
        await self._init_geoip()
    
    async def _init_database(self) -> None:
        """Initialize async database connection."""
        try:
            # Convert database URL for async
            db_url = self.settings.database_url
            if db_url.startswith("postgresql://"):
                db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
            
            self.engine = create_async_engine(db_url, echo=False)
            self.async_session_maker = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Create tables if they don't exist
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            logger.info("Async security audit database initialized")
        except Exception as e:
            logger.error(f"Failed to initialize async audit database: {e}")
    
    async def _init_geoip(self) -> None:
        """Initialize GeoIP database (optional)."""
        try:
            # Try to load GeoLite2 database
            geoip_path = Path("/usr/local/share/GeoIP/GeoLite2-City.mmdb")
            if geoip_path.exists():
                self.geoip_reader = geoip2.database.Reader(str(geoip_path))
                logger.info("GeoIP database loaded")
            else:
                logger.info("GeoIP database not found - location tracking disabled")
        except Exception as e:
            logger.warning(f"Failed to load GeoIP database: {e}")
    
    async def log_event(
        self,
        event_type: SecurityEventType,
        severity: SecurityEventSeverity,
        client_ip: str,
        message: str = None,
        request: Optional[Request] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        blocked: bool = False
    ) -> SecurityEvent:
        """
        Log a security event asynchronously.
        
        Args:
            event_type: Type of security event
            severity: Event severity level
            client_ip: Client IP address
            message: Event message
            request: FastAPI request object (optional)
            user_id: User ID (optional)
            session_id: Session ID (optional)  
            details: Additional event details
            blocked: Whether the action was blocked
            
        Returns:
            Created SecurityEvent object
        """
        now = datetime.utcnow()
        
        # Create security event
        event = SecurityEvent(
            event_type=event_type,
            severity=severity,
            timestamp=now,
            client_ip=client_ip,
            user_id=user_id,
            session_id=session_id,
            message=message,
            details=details or {},
            blocked=blocked
        )
        
        # Extract request information
        if request:
            event.endpoint = str(request.url.path)
            event.method = request.method
            event.user_agent = request.headers.get('User-Agent')
            event.referer = request.headers.get('Referer')
        
        # Add location information
        event.location = await self._get_location_info(client_ip)
        
        # Calculate risk score
        event.risk_score = self._calculate_risk_score(event)
        
        # Store in database (async)
        await self._store_event(event)
        
        # Log to file/console (non-blocking)
        asyncio.create_task(self._async_log_to_file(event))
        
        # Check for alert conditions (non-blocking)
        asyncio.create_task(self._check_alert_conditions(event))
        
        return event
    
    async def _store_event(self, event: SecurityEvent) -> None:
        """Store event in database asynchronously."""
        if not self.async_session_maker:
            return
        
        try:
            # Generate event hash for deduplication
            event_hash = self._generate_event_hash(event)
            
            async with self.async_session_maker() as session:
                # Check if similar event already exists recently
                stmt = select(SecurityAuditLog).filter_by(event_hash=event_hash)
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()
                
                if existing:
                    # Update existing event (increment counter in details)
                    details = existing.details or {}
                    details['count'] = details.get('count', 1) + 1
                    details['last_occurrence'] = event.timestamp.isoformat()
                    existing.details = details
                else:
                    # Create new event
                    audit_log = SecurityAuditLog(
                        event_type=event.event_type.value,
                        severity=event.severity.value,
                        timestamp=event.timestamp,
                        client_ip=event.client_ip,
                        user_id=event.user_id,
                        session_id=event.session_id,
                        endpoint=event.endpoint,
                        method=event.method,
                        user_agent=event.user_agent,
                        referer=event.referer,
                        message=event.message,
                        details=event.details,
                        location=event.location,
                        risk_score=event.risk_score,
                        blocked=event.blocked,
                        event_hash=event_hash
                    )
                    session.add(audit_log)
                
                await session.commit()
                
        except Exception as e:
            logger.error(f"Failed to store security event: {e}")
    
    def _generate_event_hash(self, event: SecurityEvent) -> str:
        """Generate hash for event deduplication."""
        # Create hash based on key fields
        hash_data = f"{event.event_type.value}:{event.client_ip}:{event.endpoint}:{event.user_id}"
        return hashlib.sha256(hash_data.encode()).hexdigest()[:16]
    
    async def _get_location_info(self, ip_address: str) -> Optional[Dict[str, str]]:
        """Get location information for IP address."""
        if not self.geoip_reader:
            return None
        
        try:
            # Run GeoIP lookup in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, self.geoip_reader.city, ip_address)
            return {
                'country': response.country.name or 'Unknown',
                'country_code': response.country.iso_code or 'XX',
                'city': response.city.name or 'Unknown',
                'region': response.subdivisions.most_specific.name or 'Unknown',
                'latitude': str(response.location.latitude) if response.location.latitude else None,
                'longitude': str(response.location.longitude) if response.location.longitude else None
            }
        except (geoip2.errors.AddressNotFoundError, ValueError):
            return {'country': 'Unknown', 'country_code': 'XX'}
        except Exception as e:
            logger.warning(f"GeoIP lookup failed for {ip_address}: {e}")
            return None
    
    def _calculate_risk_score(self, event: SecurityEvent) -> int:
        """Calculate risk score for event."""
        score = 0
        
        # Severity-based scoring
        severity_scores = {
            SecurityEventSeverity.LOW: 10,
            SecurityEventSeverity.MEDIUM: 30,
            SecurityEventSeverity.HIGH: 60,
            SecurityEventSeverity.CRITICAL: 100
        }
        score += severity_scores.get(event.severity, 0)
        
        # Check for high-risk IP
        if event.client_ip in self.risk_patterns['high_risk_ips']:
            score += 50
        
        # Check for suspicious user agent
        if event.user_agent:
            ua_lower = event.user_agent.lower()
            for pattern in self.risk_patterns['suspicious_user_agents']:
                if pattern in ua_lower:
                    score += 30
                    break
        
        # Check for attack endpoints
        if event.endpoint:
            endpoint_lower = event.endpoint.lower()
            for pattern in self.risk_patterns['attack_endpoints']:
                if pattern in endpoint_lower:
                    score += 20
                    break
        
        # Check for specific attack types
        attack_events = {
            SecurityEventType.SQL_INJECTION_ATTEMPT,
            SecurityEventType.XSS_ATTEMPT,
            SecurityEventType.PATH_TRAVERSAL_ATTEMPT,
            SecurityEventType.COMMAND_INJECTION_ATTEMPT,
            SecurityEventType.VECTOR_INJECTION_ATTEMPT
        }
        
        if event.event_type in attack_events:
            score += 40
        
        return min(score, 100)  # Cap at 100
    
    async def _async_log_to_file(self, event: SecurityEvent) -> None:
        """Log event to file asynchronously."""
        try:
            log_entry = {
                'timestamp': event.timestamp.isoformat(),
                'event_type': event.event_type.value,
                'severity': event.severity.value,
                'client_ip': event.client_ip,
                'user_id': event.user_id,
                'endpoint': event.endpoint,
                'message': event.message,
                'risk_score': event.risk_score,
                'blocked': event.blocked
            }
            
            # Use appropriate log level based on severity
            if event.severity == SecurityEventSeverity.CRITICAL:
                logger.critical(f"SECURITY: {json.dumps(log_entry)}")
            elif event.severity == SecurityEventSeverity.HIGH:
                logger.error(f"SECURITY: {json.dumps(log_entry)}")
            elif event.severity == SecurityEventSeverity.MEDIUM:
                logger.warning(f"SECURITY: {json.dumps(log_entry)}")
            else:
                logger.info(f"SECURITY: {json.dumps(log_entry)}")
                
        except Exception as e:
            logger.error(f"Failed to log security event: {e}")
    
    async def _check_alert_conditions(self, event: SecurityEvent) -> None:
        """Check if event should trigger alerts."""
        # High-severity events
        if event.severity == SecurityEventSeverity.CRITICAL:
            await self._send_alert(event, "CRITICAL SECURITY EVENT")
        
        # High risk score
        elif event.risk_score >= 80:
            await self._send_alert(event, "HIGH RISK EVENT DETECTED")
        
        # Multiple failed login attempts
        elif event.event_type == SecurityEventType.LOGIN_FAILED:
            # Check for brute force pattern
            await self._check_brute_force(event)
    
    async def _send_alert(self, event: SecurityEvent, alert_type: str) -> None:
        """Send security alert (placeholder for actual alert mechanism)."""
        alert_message = f"""
        {alert_type}
        Time: {event.timestamp}
        Type: {event.event_type.value}
        IP: {event.client_ip}
        User: {event.user_id or 'Unknown'}
        Endpoint: {event.endpoint or 'Unknown'}
        Risk Score: {event.risk_score}
        Blocked: {event.blocked}
        Message: {event.message or 'No message'}
        """
        
        logger.critical(f"SECURITY ALERT: {alert_message}")
        
        # TODO: Implement actual alerting mechanism
        # - Email notifications
        # - Slack/Discord webhooks
        # - SMS for critical events
        # - Integration with SIEM systems
    
    async def _check_brute_force(self, event: SecurityEvent) -> None:
        """Check for brute force attack patterns."""
        if not self.async_session_maker:
            return
        
        try:
            # Check recent failed login attempts
            async with self.async_session_maker() as session:
                # Count failed logins in last 5 minutes
                five_minutes_ago = datetime.utcnow().replace(second=0, microsecond=0)
                five_minutes_ago = five_minutes_ago.replace(minute=five_minutes_ago.minute - 5)
                
                stmt = select(SecurityAuditLog).filter(
                    SecurityAuditLog.event_type == SecurityEventType.LOGIN_FAILED.value,
                    SecurityAuditLog.client_ip == event.client_ip,
                    SecurityAuditLog.timestamp >= five_minutes_ago
                )
                
                result = await session.execute(stmt)
                failed_attempts = result.scalars().all()
                
                # Alert if more than 5 failed attempts
                if len(failed_attempts) >= 5:
                    await self._send_alert(event, "POSSIBLE BRUTE FORCE ATTACK")
                    
                    # Add IP to high-risk list
                    self.risk_patterns['high_risk_ips'].add(event.client_ip)
                    
        except Exception as e:
            logger.error(f"Failed to check brute force pattern: {e}")
    
    async def get_recent_events(
        self,
        minutes: int = 60,
        event_type: Optional[SecurityEventType] = None,
        severity: Optional[SecurityEventSeverity] = None
    ) -> List[Dict[str, Any]]:
        """Get recent security events."""
        if not self.async_session_maker:
            return []
        
        try:
            async with self.async_session_maker() as session:
                cutoff_time = datetime.utcnow().replace(second=0, microsecond=0)
                cutoff_time = cutoff_time.replace(minute=cutoff_time.minute - minutes)
                
                stmt = select(SecurityAuditLog).filter(
                    SecurityAuditLog.timestamp >= cutoff_time
                )
                
                if event_type:
                    stmt = stmt.filter(SecurityAuditLog.event_type == event_type.value)
                
                if severity:
                    stmt = stmt.filter(SecurityAuditLog.severity == severity.value)
                
                stmt = stmt.order_by(SecurityAuditLog.timestamp.desc())
                
                result = await session.execute(stmt)
                events = result.scalars().all()
                
                return [
                    {
                        'id': e.id,
                        'event_type': e.event_type,
                        'severity': e.severity,
                        'timestamp': e.timestamp.isoformat(),
                        'client_ip': e.client_ip,
                        'user_id': e.user_id,
                        'endpoint': e.endpoint,
                        'message': e.message,
                        'risk_score': e.risk_score,
                        'blocked': e.blocked
                    }
                    for e in events
                ]
                
        except Exception as e:
            logger.error(f"Failed to get recent events: {e}")
            return []
    
    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self.engine:
            await self.engine.dispose()
        
        if self.geoip_reader:
            self.geoip_reader.close()


# Global instance (initialized on first use)
_audit_logger: Optional[AsyncSecurityAuditLogger] = None


async def get_audit_logger() -> AsyncSecurityAuditLogger:
    """Get or create async audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AsyncSecurityAuditLogger()
        await _audit_logger.initialize()
    return _audit_logger