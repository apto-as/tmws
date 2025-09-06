"""
Input Validation and Sanitization Module
Hestia's Paranoid Validation System

"……どんな入力も信用してはいけません……全てを疑って検証します……"
"""

import re
import html
import logging
import ipaddress
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse
import numpy as np
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom exception for validation failures."""
    
    def __init__(self, message: str, field: str = None, value: Any = None):
        self.message = message
        self.field = field
        self.value = value
        super().__init__(message)


class InputValidator:
    """
    Comprehensive input validation system.
    Hestia's Rule: Trust nothing, validate everything.
    """
    
    # Dangerous patterns that should never be allowed
    DANGEROUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'javascript:',               # JavaScript URLs
        r'vbscript:',                # VBScript URLs
        r'onload\s*=',               # Event handlers
        r'onerror\s*=',
        r'onclick\s*=',
        r'onmouseover\s*=',
        r'eval\s*\(',                # Code execution
        r'exec\s*\(',
        r'system\s*\(',
        r'shell_exec\s*\(',
        r'\.\./',                    # Directory traversal
        r'\.\.\%2f',                 # Encoded directory traversal
        r'\.\.\%5c',                 # Windows directory traversal
        r'%00',                      # Null byte injection
        r'<\s*iframe[^>]*>',         # Iframe injection
        r'<\s*object[^>]*>',         # Object injection
        r'<\s*embed[^>]*>',          # Embed injection
    ]
    
    # SQL keywords that might indicate injection
    SQL_KEYWORDS = [
        'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
        'EXEC', 'EXECUTE', 'UNION', 'JOIN', 'WHERE', 'ORDER BY', 'GROUP BY',
        'HAVING', 'TRUNCATE', 'REPLACE', 'MERGE', 'CALL', 'EXPLAIN', 'ANALYZE'
    ]
    
    # Common weak passwords to reject
    WEAK_PASSWORDS = [
        'password', '123456', 'qwerty', 'admin', 'root', 'user',
        'guest', 'test', 'demo', 'password123', 'admin123', 'root123',
        '12345678', 'password1', 'welcome', 'login', 'pass', '1234567890'
    ]
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize validator with configuration."""
        self.config = config or {}
        self.max_lengths = self.config.get('max_lengths', {
            'username': 64,
            'email': 256,
            'text_field': 1000,
            'content_field': 10000,
            'query_string': 500,
        })
    
    def validate_string(
        self, 
        value: str, 
        field_name: str = "input",
        max_length: int = None,
        allow_html: bool = False,
        required: bool = True
    ) -> str:
        """
        Comprehensive string validation.
        
        Args:
            value: String to validate
            field_name: Name of the field for error reporting
            max_length: Maximum allowed length
            allow_html: Whether to allow HTML content
            required: Whether the field is required
            
        Returns:
            Sanitized and validated string
            
        Raises:
            ValidationError: If validation fails
        """
        # Check if required
        if required and (not value or not value.strip()):
            raise ValidationError(f"{field_name} is required", field_name, value)
        
        if not value:
            return ""
        
        # Check length
        if max_length is None:
            max_length = self.max_lengths.get(field_name, 1000)
            
        if len(value) > max_length:
            raise ValidationError(
                f"{field_name} exceeds maximum length of {max_length} characters",
                field_name, value
            )
        
        # Check for dangerous patterns
        self._check_dangerous_patterns(value, field_name)
        
        # Sanitize based on HTML allowance
        if allow_html:
            return self._sanitize_html(value)
        else:
            return self._sanitize_text(value)
    
    def validate_email(self, email: str, field_name: str = "email") -> str:
        """
        Validate email address.
        
        Args:
            email: Email to validate
            field_name: Field name for error reporting
            
        Returns:
            Validated and normalized email
            
        Raises:
            ValidationError: If email is invalid
        """
        if not email:
            raise ValidationError(f"{field_name} is required", field_name, email)
        
        email = email.strip().lower()
        
        # Length check
        if len(email) > self.max_lengths.get('email', 256):
            raise ValidationError(
                f"{field_name} exceeds maximum length",
                field_name, email
            )
        
        # Basic email pattern
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            raise ValidationError(f"Invalid {field_name} format", field_name, email)
        
        # Check for dangerous patterns
        self._check_dangerous_patterns(email, field_name)
        
        return email
    
    def validate_password(self, password: str, username: str = None) -> str:
        """
        Validate password strength.
        
        Args:
            password: Password to validate
            username: Username to check against
            
        Returns:
            Validated password
            
        Raises:
            ValidationError: If password is weak
        """
        if not password:
            raise ValidationError("Password is required", "password", password)
        
        issues = []
        
        # Length check
        if len(password) < 12:
            issues.append("Password must be at least 12 characters long")
        
        # Character requirements
        if not re.search(r'[a-z]', password):
            issues.append("Password must contain at least one lowercase letter")
        
        if not re.search(r'[A-Z]', password):
            issues.append("Password must contain at least one uppercase letter")
        
        if not re.search(r'\d', password):
            issues.append("Password must contain at least one number")
        
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
            issues.append("Password must contain at least one special character")
        
        # Check for weak passwords
        if password.lower() in self.WEAK_PASSWORDS:
            issues.append("Password is too common")
        
        # Check if password contains username
        if username and username.lower() in password.lower():
            issues.append("Password cannot contain username")
        
        # Check for repeated characters
        if re.search(r'(.)\1{2,}', password):
            issues.append("Password cannot contain 3 or more repeated characters")
        
        if issues:
            raise ValidationError(f"Password validation failed: {'; '.join(issues)}", "password")
        
        return password
    
    def validate_url(self, url: str, field_name: str = "url") -> str:
        """
        Validate URL.
        
        Args:
            url: URL to validate
            field_name: Field name for error reporting
            
        Returns:
            Validated URL
            
        Raises:
            ValidationError: If URL is invalid
        """
        if not url:
            raise ValidationError(f"{field_name} is required", field_name, url)
        
        url = url.strip()
        
        # Check for dangerous protocols
        dangerous_protocols = ['javascript:', 'vbscript:', 'data:', 'file:']
        for protocol in dangerous_protocols:
            if url.lower().startswith(protocol):
                raise ValidationError(
                    f"{field_name} uses dangerous protocol: {protocol}",
                    field_name, url
                )
        
        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise ValidationError(f"Invalid {field_name} format: {e}", field_name, url)
        
        # Check scheme
        if parsed.scheme not in ['http', 'https']:
            raise ValidationError(
                f"{field_name} must use HTTP or HTTPS",
                field_name, url
            )
        
        return url
    
    def validate_ip_address(self, ip: str, field_name: str = "ip_address") -> str:
        """
        Validate IP address.
        
        Args:
            ip: IP address to validate
            field_name: Field name for error reporting
            
        Returns:
            Validated IP address
            
        Raises:
            ValidationError: If IP is invalid
        """
        if not ip:
            raise ValidationError(f"{field_name} is required", field_name, ip)
        
        ip = ip.strip()
        
        try:
            # This validates both IPv4 and IPv6
            ipaddress.ip_address(ip)
        except ValueError as e:
            raise ValidationError(f"Invalid {field_name}: {e}", field_name, ip)
        
        return ip
    
    def validate_json_field(
        self, 
        data: Dict[str, Any], 
        field_name: str,
        required_fields: List[str] = None,
        max_depth: int = 10
    ) -> Dict[str, Any]:
        """
        Validate JSON field data.
        
        Args:
            data: JSON data to validate
            field_name: Field name for error reporting
            required_fields: List of required fields
            max_depth: Maximum nested depth allowed
            
        Returns:
            Validated JSON data
            
        Raises:
            ValidationError: If JSON is invalid
        """
        if not isinstance(data, dict):
            raise ValidationError(f"{field_name} must be an object", field_name, data)
        
        # Check depth
        if self._get_dict_depth(data) > max_depth:
            raise ValidationError(
                f"{field_name} exceeds maximum nesting depth of {max_depth}",
                field_name, data
            )
        
        # Check required fields
        if required_fields:
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                raise ValidationError(
                    f"{field_name} missing required fields: {missing_fields}",
                    field_name, data
                )
        
        # Recursively validate string values
        return self._validate_json_strings(data, field_name)
    
    def _check_dangerous_patterns(self, value: str, field_name: str) -> None:
        """Check for dangerous patterns in input."""
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"Dangerous pattern detected in {field_name}: {pattern}")
                raise ValidationError(
                    f"{field_name} contains potentially dangerous content",
                    field_name, value
                )
    
    def _sanitize_text(self, text: str) -> str:
        """Sanitize plain text input."""
        # HTML escape
        text = html.escape(text)
        
        # Remove control characters except common whitespace
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')
        
        return text.strip()
    
    def _sanitize_html(self, html_content: str) -> str:
        """Sanitize HTML content (basic implementation)."""
        # For now, just escape everything - implement proper HTML sanitizer later
        return html.escape(html_content)
    
    def _get_dict_depth(self, d: Dict[str, Any], depth: int = 0) -> int:
        """Get maximum depth of nested dictionary."""
        if not isinstance(d, dict) or not d:
            return depth
        
        return max(
            self._get_dict_depth(value, depth + 1) 
            if isinstance(value, dict) 
            else depth + 1
            for value in d.values()
        )
    
    def _validate_json_strings(self, data: Dict[str, Any], field_name: str) -> Dict[str, Any]:
        """Recursively validate strings in JSON data."""
        result = {}
        
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.validate_string(value, f"{field_name}.{key}", required=False)
            elif isinstance(value, dict):
                result[key] = self._validate_json_strings(value, f"{field_name}.{key}")
            elif isinstance(value, list):
                result[key] = [
                    self.validate_string(item, f"{field_name}.{key}[{i}]", required=False)
                    if isinstance(item, str)
                    else item
                    for i, item in enumerate(value)
                ]
            else:
                result[key] = value
        
        return result


class SQLInjectionValidator:
    """
    SQL Injection prevention validator.
    "……SQLインジェクションは絶対に通しません……"
    """
    
    # Dangerous SQL patterns
    SQL_INJECTION_PATTERNS = [
        r'\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE)\b',
        r'\b(UNION|JOIN)\b.*\b(SELECT|FROM)\b',
        r'[\'";]\s*(OR|AND)\s*[\'"]?\w*[\'"]?\s*=\s*[\'"]?\w*[\'"]?',
        r'\b(OR|AND)\b\s+[\'"]?\d+[\'"]?\s*=\s*[\'"]?\d+[\'"]?',
        r'[\'"];.*?--',
        r'/\*.*?\*/',
        r'\bxp_cmdshell\b',
        r'\bsp_executesql\b',
        r';.*\b(SELECT|INSERT|UPDATE|DELETE)\b',
    ]
    
    def __init__(self):
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.SQL_INJECTION_PATTERNS]
    
    def validate_query_parameter(self, value: str, parameter_name: str = "parameter") -> str:
        """
        Validate query parameter for SQL injection attempts.
        
        Args:
            value: Parameter value to validate
            parameter_name: Parameter name for error reporting
            
        Returns:
            Validated parameter value
            
        Raises:
            ValidationError: If SQL injection detected
        """
        if not value:
            return value
        
        # Check for SQL injection patterns
        for pattern in self.compiled_patterns:
            if pattern.search(value):
                logger.critical(f"SQL injection attempt detected in {parameter_name}: {value}")
                raise ValidationError(
                    f"{parameter_name} contains potentially dangerous SQL content",
                    parameter_name, value
                )
        
        # Additional checks for common injection techniques
        self._check_sql_comment_injection(value, parameter_name)
        self._check_union_injection(value, parameter_name)
        self._check_boolean_injection(value, parameter_name)
        
        return value
    
    def _check_sql_comment_injection(self, value: str, parameter_name: str) -> None:
        """Check for SQL comment-based injection."""
        if re.search(r'--.*|/\*.*?\*/', value, re.IGNORECASE | re.DOTALL):
            logger.critical(f"SQL comment injection detected in {parameter_name}")
            raise ValidationError(
                f"{parameter_name} contains SQL comments",
                parameter_name, value
            )
    
    def _check_union_injection(self, value: str, parameter_name: str) -> None:
        """Check for UNION-based injection."""
        if re.search(r'\bUNION\b.*\bSELECT\b', value, re.IGNORECASE):
            logger.critical(f"UNION injection detected in {parameter_name}")
            raise ValidationError(
                f"{parameter_name} contains UNION SQL injection",
                parameter_name, value
            )
    
    def _check_boolean_injection(self, value: str, parameter_name: str) -> None:
        """Check for boolean-based injection."""
        boolean_patterns = [
            r"'\s*(OR|AND)\s*'1'\s*=\s*'1",
            r'"\s*(OR|AND)\s*"1"\s*=\s*"1',
            r'\b(OR|AND)\s+1\s*=\s*1\b',
        ]
        
        for pattern in boolean_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                logger.critical(f"Boolean injection detected in {parameter_name}")
                raise ValidationError(
                    f"{parameter_name} contains boolean SQL injection",
                    parameter_name, value
                )


class VectorValidator:
    """
    Vector and embedding validation for pgvector protection.
    "……ベクターインジェクションも見逃しません……"
    """
    
    def __init__(self, max_dimensions: int = 2048):
        self.max_dimensions = max_dimensions
    
    def validate_vector(
        self, 
        vector: Union[List[float], np.ndarray], 
        expected_dimensions: int = None
    ) -> List[float]:
        """
        Validate embedding vector.
        
        Args:
            vector: Vector to validate
            expected_dimensions: Expected vector dimensions
            
        Returns:
            Validated vector as list
            
        Raises:
            ValidationError: If vector is invalid
        """
        if vector is None:
            raise ValidationError("Vector cannot be None", "vector", vector)
        
        # Convert to list if numpy array
        if isinstance(vector, np.ndarray):
            vector = vector.tolist()
        
        if not isinstance(vector, list):
            raise ValidationError("Vector must be a list of numbers", "vector", vector)
        
        # Check dimensions
        if len(vector) > self.max_dimensions:
            raise ValidationError(
                f"Vector dimensions ({len(vector)}) exceed maximum ({self.max_dimensions})",
                "vector", vector
            )
        
        if expected_dimensions and len(vector) != expected_dimensions:
            raise ValidationError(
                f"Vector dimensions ({len(vector)}) don't match expected ({expected_dimensions})",
                "vector", vector
            )
        
        # Validate each component
        validated_vector = []
        for i, component in enumerate(vector):
            validated_component = self._validate_vector_component(component, i)
            validated_vector.append(validated_component)
        
        # Check for suspicious patterns
        self._check_vector_anomalies(validated_vector)
        
        return validated_vector
    
    def validate_text_for_embedding(self, text: str, max_length: int = 8192) -> str:
        """
        Validate text before embedding generation.
        
        Args:
            text: Text to validate
            max_length: Maximum text length
            
        Returns:
            Validated text
            
        Raises:
            ValidationError: If text is invalid
        """
        if not text:
            raise ValidationError("Text for embedding cannot be empty", "text", text)
        
        if len(text) > max_length:
            raise ValidationError(
                f"Text length ({len(text)}) exceeds maximum ({max_length})",
                "text", text
            )
        
        # Use InputValidator for basic sanitization
        validator = InputValidator()
        return validator.validate_string(text, "embedding_text", max_length, required=True)
    
    def _validate_vector_component(self, component: Any, index: int) -> float:
        """Validate individual vector component."""
        try:
            value = float(component)
        except (ValueError, TypeError):
            raise ValidationError(
                f"Vector component at index {index} must be a number",
                f"vector[{index}]", component
            )
        
        # Check for NaN and infinite values
        if np.isnan(value):
            raise ValidationError(
                f"Vector component at index {index} is NaN",
                f"vector[{index}]", value
            )
        
        if np.isinf(value):
            raise ValidationError(
                f"Vector component at index {index} is infinite",
                f"vector[{index}]", value
            )
        
        # Check for reasonable bounds
        if abs(value) > 1e6:
            logger.warning(f"Unusually large vector component: {value}")
        
        return value
    
    def _check_vector_anomalies(self, vector: List[float]) -> None:
        """Check for suspicious vector patterns."""
        # Check for all zeros (might be invalid embedding)
        if all(v == 0.0 for v in vector):
            logger.warning("Vector contains all zeros")
        
        # Check for all same values (suspicious)
        if len(set(vector)) == 1:
            logger.warning("Vector contains all identical values")
        
        # Check vector norm (should be reasonable for most embeddings)
        norm = sum(v * v for v in vector) ** 0.5
        if norm > 100 or norm < 0.01:
            logger.warning(f"Unusual vector norm: {norm}")