"""
Enhanced HTML Sanitization Module for TMWS
Robust HTML sanitization using Bleach library
Hestia's Ultimate Defense Against XSS

"……HTMLは危険です……すべてのタグを疑います……"
"""

import re
import logging
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urlparse, urlunparse

try:
    import bleach
    from bleach.css_sanitizer import CSSSanitizer
    BLEACH_AVAILABLE = True
except ImportError:
    BLEACH_AVAILABLE = False
    logging.warning("Bleach library not available. Using basic HTML sanitization.")

logger = logging.getLogger(__name__)


class HTMLSanitizer:
    """
    Production-grade HTML sanitization with Bleach.
    Provides multiple sanitization levels for different use cases.
    """
    
    # Sanitization presets
    PRESETS = {
        "strict": {
            "tags": [],  # No HTML allowed
            "attributes": {},
            "strip": True
        },
        "basic": {
            "tags": ["p", "br", "strong", "em", "u", "s", "a", "ul", "ol", "li"],
            "attributes": {"a": ["href", "title"]},
            "protocols": ["http", "https", "mailto"],
            "strip": True
        },
        "markdown": {
            "tags": [
                "p", "br", "strong", "em", "u", "s", "a", "ul", "ol", "li",
                "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "code", "pre",
                "hr", "table", "thead", "tbody", "tr", "th", "td"
            ],
            "attributes": {
                "a": ["href", "title"],
                "code": ["class"],
                "pre": ["class"]
            },
            "protocols": ["http", "https", "mailto"],
            "strip": True
        },
        "rich": {
            "tags": [
                "p", "br", "strong", "em", "u", "s", "a", "ul", "ol", "li",
                "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "code", "pre",
                "hr", "table", "thead", "tbody", "tr", "th", "td", "img", "figure",
                "figcaption", "span", "div", "section", "article", "header", "footer"
            ],
            "attributes": {
                "a": ["href", "title", "target", "rel"],
                "img": ["src", "alt", "title", "width", "height"],
                "code": ["class"],
                "pre": ["class"],
                "span": ["class", "style"],
                "div": ["class", "id"],
                "section": ["class", "id"],
                "article": ["class", "id"]
            },
            "protocols": ["http", "https", "mailto", "data"],
            "strip": False,
            "css_sanitizer": CSSSanitizer(allowed_css_properties=[
                "color", "background-color", "font-size", "font-weight",
                "text-align", "margin", "padding", "border", "width", "height"
            ]) if BLEACH_AVAILABLE else None
        }
    }
    
    def __init__(self, preset: str = "basic", custom_config: Dict[str, Any] = None):
        """
        Initialize HTML sanitizer with preset or custom configuration.
        
        Args:
            preset: Preset name ("strict", "basic", "markdown", "rich")
            custom_config: Custom configuration to override preset
        """
        
        if not BLEACH_AVAILABLE:
            logger.warning("Bleach not available. HTML sanitization will be limited.")
            self.bleach_available = False
        else:
            self.bleach_available = True
        
        # Load preset
        if preset in self.PRESETS:
            self.config = self.PRESETS[preset].copy()
        else:
            logger.warning(f"Unknown preset '{preset}'. Using 'basic'.")
            self.config = self.PRESETS["basic"].copy()
        
        # Apply custom configuration
        if custom_config:
            self.config.update(custom_config)
        
        # Additional security patterns
        self.dangerous_protocols = {"javascript", "vbscript", "data", "file"}
        self.dangerous_attributes = {"onload", "onerror", "onclick", "onmouseover"}
        
        logger.info(f"HTML Sanitizer initialized with preset: {preset}")
    
    def sanitize(self, html_content: str, context: str = "default") -> str:
        """
        Sanitize HTML content based on configuration.
        
        Args:
            html_content: HTML content to sanitize
            context: Context for sanitization (for logging)
            
        Returns:
            Sanitized HTML content
        """
        
        if not html_content:
            return ""
        
        # Check for suspicious patterns first
        if self._contains_suspicious_patterns(html_content):
            logger.warning(f"Suspicious patterns detected in {context}")
        
        if self.bleach_available:
            # Use Bleach for sanitization
            cleaned = bleach.clean(
                html_content,
                tags=self.config.get("tags", []),
                attributes=self.config.get("attributes", {}),
                protocols=self.config.get("protocols", ["http", "https"]),
                strip=self.config.get("strip", True),
                strip_comments=True
            )
            
            # Apply CSS sanitization if configured
            if "css_sanitizer" in self.config and self.config["css_sanitizer"]:
                cleaned = self._sanitize_css(cleaned)
            
            return cleaned
        else:
            # Fallback to basic sanitization
            return self._basic_sanitize(html_content)
    
    def _contains_suspicious_patterns(self, content: str) -> bool:
        """Check for suspicious patterns that might indicate attack."""
        
        suspicious_patterns = [
            r'<script[^>]*>',
            r'javascript:',
            r'on\w+\s*=',  # Event handlers
            r'expression\s*\(',  # CSS expression
            r'import\s*\(',
            r'@import',
            r'<iframe',
            r'<object',
            r'<embed',
            r'<applet',
            r'<meta[^>]*http-equiv',
            r'<link[^>]*href.*javascript:',
            r'&#x[0-9a-fA-F]+;',  # Hex entities
            r'&#\d+;',  # Decimal entities
        ]
        
        content_lower = content.lower()
        for pattern in suspicious_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                return True
        
        return False
    
    def _basic_sanitize(self, html_content: str) -> str:
        """
        Basic HTML sanitization without Bleach.
        Strips all HTML tags by default.
        """
        
        # Remove script and style elements completely
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove dangerous event handlers
        html_content = re.sub(r'on\w+\s*=\s*["\'].*?["\']', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'on\w+\s*=\s*\S+', '', html_content, flags=re.IGNORECASE)
        
        # Remove javascript: and other dangerous protocols
        for protocol in self.dangerous_protocols:
            html_content = re.sub(f'{protocol}:', '', html_content, flags=re.IGNORECASE)
        
        # If strict mode, remove all HTML
        if not self.config.get("tags"):
            html_content = re.sub(r'<[^>]+>', '', html_content)
        else:
            # Basic tag filtering
            allowed_tags = self.config.get("tags", [])
            if allowed_tags:
                # This is a simplified approach - production should use proper parser
                for match in re.finditer(r'<(/?)(\w+)([^>]*)>', html_content):
                    tag = match.group(2).lower()
                    if tag not in allowed_tags:
                        html_content = html_content.replace(match.group(0), '')
        
        return html_content
    
    def _sanitize_css(self, html_content: str) -> str:
        """
        Sanitize CSS within HTML content.
        Requires Bleach with CSS sanitizer.
        """
        
        if not self.bleach_available or "css_sanitizer" not in self.config:
            return html_content
        
        css_sanitizer = self.config["css_sanitizer"]
        
        # Find and sanitize style attributes
        def sanitize_style_attr(match):
            style_content = match.group(1)
            sanitized = css_sanitizer.sanitize_css(style_content)
            return f'style="{sanitized}"'
        
        html_content = re.sub(
            r'style\s*=\s*["\']([^"\']*)["\']',
            sanitize_style_attr,
            html_content,
            flags=re.IGNORECASE
        )
        
        return html_content
    
    def sanitize_url(self, url: str) -> Optional[str]:
        """
        Sanitize and validate URLs.
        
        Args:
            url: URL to sanitize
            
        Returns:
            Sanitized URL or None if invalid
        """
        
        if not url:
            return None
        
        try:
            parsed = urlparse(url.strip())
            
            # Check protocol
            if parsed.scheme.lower() in self.dangerous_protocols:
                logger.warning(f"Dangerous protocol detected: {parsed.scheme}")
                return None
            
            # Default to https if no scheme
            if not parsed.scheme:
                parsed = parsed._replace(scheme='https')
            
            # Validate allowed protocols
            allowed_protocols = self.config.get("protocols", ["http", "https"])
            if parsed.scheme not in allowed_protocols:
                logger.warning(f"Protocol not allowed: {parsed.scheme}")
                return None
            
            # Reconstruct URL
            clean_url = urlunparse(parsed)
            
            # Additional validation
            if self._contains_suspicious_patterns(clean_url):
                logger.warning(f"Suspicious patterns in URL: {clean_url}")
                return None
            
            return clean_url
            
        except Exception as e:
            logger.error(f"URL sanitization failed: {e}")
            return None
    
    def strip_tags(self, html_content: str) -> str:
        """
        Strip all HTML tags, keeping only text content.
        
        Args:
            html_content: HTML content to strip
            
        Returns:
            Plain text content
        """
        
        if self.bleach_available:
            return bleach.clean(html_content, tags=[], strip=True)
        else:
            # Basic regex stripping
            text = re.sub(r'<[^>]+>', '', html_content)
            # Decode HTML entities
            text = re.sub(r'&amp;', '&', text)
            text = re.sub(r'&lt;', '<', text)
            text = re.sub(r'&gt;', '>', text)
            text = re.sub(r'&quot;', '"', text)
            text = re.sub(r'&#39;', "'", text)
            text = re.sub(r'&nbsp;', ' ', text)
            return text
    
    def escape_html(self, text: str) -> str:
        """
        Escape HTML characters to prevent injection.
        
        Args:
            text: Text to escape
            
        Returns:
            Escaped text safe for HTML display
        """
        
        if self.bleach_available:
            # Use Bleach's escaping
            return bleach.clean(text, tags=[], strip=False)
        else:
            # Manual escaping
            text = text.replace('&', '&amp;')
            text = text.replace('<', '&lt;')
            text = text.replace('>', '&gt;')
            text = text.replace('"', '&quot;')
            text = text.replace("'", '&#39;')
            return text
    
    def validate_html_structure(self, html_content: str) -> tuple[bool, List[str]]:
        """
        Validate HTML structure for common issues.
        
        Args:
            html_content: HTML content to validate
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        
        issues = []
        
        # Check for unclosed tags
        open_tags = re.findall(r'<(\w+)[^>]*>', html_content)
        close_tags = re.findall(r'</(\w+)>', html_content)
        
        # Simple validation - not perfect but catches common issues
        tag_stack = []
        for tag in open_tags:
            if tag.lower() not in ['br', 'hr', 'img', 'input', 'meta', 'link']:
                tag_stack.append(tag)
        
        for tag in close_tags:
            if tag_stack and tag_stack[-1].lower() == tag.lower():
                tag_stack.pop()
            else:
                issues.append(f"Mismatched closing tag: </{tag}>")
        
        if tag_stack:
            issues.append(f"Unclosed tags: {', '.join(tag_stack)}")
        
        # Check for suspicious patterns
        if self._contains_suspicious_patterns(html_content):
            issues.append("Contains suspicious patterns that may indicate XSS attempt")
        
        # Check for nested forms (invalid HTML)
        if re.search(r'<form[^>]*>.*<form[^>]*>', html_content, re.DOTALL | re.IGNORECASE):
            issues.append("Nested forms detected (invalid HTML)")
        
        return len(issues) == 0, issues


# Create default sanitizer instances
strict_sanitizer = HTMLSanitizer(preset="strict")
basic_sanitizer = HTMLSanitizer(preset="basic")
markdown_sanitizer = HTMLSanitizer(preset="markdown")
rich_sanitizer = HTMLSanitizer(preset="rich")


def sanitize_html(
    content: str,
    level: str = "basic",
    custom_config: Dict[str, Any] = None
) -> str:
    """
    Convenience function for HTML sanitization.
    
    Args:
        content: HTML content to sanitize
        level: Sanitization level ("strict", "basic", "markdown", "rich")
        custom_config: Optional custom configuration
        
    Returns:
        Sanitized HTML content
    """
    
    if custom_config:
        sanitizer = HTMLSanitizer(preset=level, custom_config=custom_config)
        return sanitizer.sanitize(content)
    
    # Use pre-created sanitizers for better performance
    sanitizers = {
        "strict": strict_sanitizer,
        "basic": basic_sanitizer,
        "markdown": markdown_sanitizer,
        "rich": rich_sanitizer
    }
    
    sanitizer = sanitizers.get(level, basic_sanitizer)
    return sanitizer.sanitize(content)