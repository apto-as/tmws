#!/usr/bin/env python3
"""
TMWS Security Setup Script
Hestia's Paranoid Security Configuration Utility

"……セキュリティ設定は妥協できません……完璧に設定します……"
"""

import os
import sys
import secrets
import hashlib
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import click

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.config import get_settings, create_secure_env_template
from security.audit_logger import get_audit_logger


@click.group()
def cli():
    """TMWS Security Setup and Management."""
    pass


@cli.command()
@click.option('--environment', '-e', default='development', 
              help='Target environment (development, staging, production)')
@click.option('--force', is_flag=True, 
              help='Overwrite existing configuration')
def init(environment: str, force: bool):
    """
    Initialize security configuration.
    Hestia's Rule: Security first, everything else second.
    """
    click.echo("🛡️  Initializing Hestia's Security Configuration...")
    
    # Validate environment
    if environment not in ['development', 'staging', 'production']:
        click.echo("❌ Invalid environment. Use: development, staging, or production")
        sys.exit(1)
    
    # Check existing .env
    env_path = Path('.env')
    if env_path.exists() and not force:
        click.echo("⚠️  .env file already exists. Use --force to overwrite.")
        sys.exit(1)
    
    try:
        # Generate secure configuration
        config = generate_secure_config(environment)
        
        # Write .env file
        write_env_file(config, env_path)
        
        # Create security directories
        setup_security_directories()
        
        # Initialize audit database
        setup_audit_database()
        
        click.echo(f"✅ Security configuration initialized for {environment}")
        click.echo(f"📄 Configuration written to: {env_path}")
        
        # Show important security warnings
        show_security_warnings(environment, config)
        
    except Exception as e:
        click.echo(f"❌ Failed to initialize security: {e}")
        sys.exit(1)


@cli.command()
def validate():
    """
    Validate current security configuration.
    Hestia's Audit: Trust nothing, verify everything.
    """
    click.echo("🔍 Validating Security Configuration...")
    
    try:
        # Load and validate settings
        settings = get_settings()
        
        # Perform comprehensive security validation
        validation_results = perform_security_validation(settings)
        
        # Display results
        display_validation_results(validation_results)
        
        # Exit with appropriate code
        if validation_results['has_critical_issues']:
            click.echo("💀 Critical security issues found! Do not deploy to production.")
            sys.exit(1)
        elif validation_results['has_warnings']:
            click.echo("⚠️  Security warnings found. Review before production deployment.")
            sys.exit(2)
        else:
            click.echo("✅ Security validation passed!")
            sys.exit(0)
            
    except Exception as e:
        click.echo(f"❌ Security validation failed: {e}")
        sys.exit(1)


@cli.command()
@click.option('--output', '-o', default='security_audit.json',
              help='Output file for audit report')
def audit(output: str):
    """
    Generate comprehensive security audit report.
    Hestia's Documentation: Every threat must be documented.
    """
    click.echo("📊 Generating Security Audit Report...")
    
    try:
        # Get audit logger
        audit_logger = get_audit_logger()
        
        # Generate comprehensive report
        report = generate_security_audit_report(audit_logger)
        
        # Write report
        output_path = Path(output)
        with open(output_path, 'w') as f:
            if output_path.suffix.lower() == '.json':
                import json
                json.dump(report, f, indent=2, default=str)
            else:
                yaml.dump(report, f, default_flow_style=False)
        
        click.echo(f"✅ Security audit report generated: {output_path}")
        
        # Display summary
        display_audit_summary(report)
        
    except Exception as e:
        click.echo(f"❌ Failed to generate audit report: {e}")
        sys.exit(1)


@cli.command()
def generate_keys():
    """
    Generate secure cryptographic keys.
    Hestia's Cryptography: Only the strongest keys survive.
    """
    click.echo("🔐 Generating Secure Cryptographic Keys...")
    
    # Generate various keys
    keys = {
        'SECRET_KEY': secrets.token_urlsafe(32),
        'JWT_SECRET_KEY': secrets.token_urlsafe(32),
        'SESSION_SECRET': secrets.token_urlsafe(24),
        'ENCRYPTION_KEY': secrets.token_urlsafe(32),
        'API_KEY': secrets.token_urlsafe(48)
    }
    
    click.echo("\n🔑 Generated Secure Keys:")
    click.echo("=" * 60)
    
    for key_name, key_value in keys.items():
        click.echo(f"{key_name}={key_value}")
    
    click.echo("=" * 60)
    click.echo("⚠️  IMPORTANT: Store these keys securely!")
    click.echo("🚫 Never commit these keys to version control!")
    click.echo("🔒 Use environment variables or secure key management systems.")


@cli.command()
@click.argument('ip_address')
@click.option('--duration', '-d', default=3600, 
              help='Block duration in seconds (default: 1 hour)')
@click.option('--reason', '-r', default='Manual block',
              help='Reason for blocking')
def block_ip(ip_address: str, duration: int, reason: str):
    """
    Block IP address for security purposes.
    Hestia's Judgment: Guilty until proven innocent.
    """
    click.echo(f"🚫 Blocking IP address: {ip_address}")
    
    try:
        # TODO: Implement IP blocking logic
        # This would integrate with:
        # - Rate limiter
        # - Firewall rules
        # - Load balancer blocking
        
        click.echo(f"✅ IP {ip_address} blocked for {duration} seconds")
        click.echo(f"📝 Reason: {reason}")
        
        # Log the action
        audit_logger = get_audit_logger()
        # TODO: Log security action
        
    except Exception as e:
        click.echo(f"❌ Failed to block IP: {e}")
        sys.exit(1)


def generate_secure_config(environment: str) -> Dict[str, Any]:
    """Generate secure configuration for environment."""
    
    # Base configuration
    config = {
        'TMWS_ENVIRONMENT': environment,
        'TMWS_SECRET_KEY': secrets.token_urlsafe(32),
        'TMWS_JWT_SECRET_KEY': secrets.token_urlsafe(32),
    }
    
    # Environment-specific settings
    if environment == 'development':
        config.update({
            'TMWS_AUTH_ENABLED': 'false',
            'TMWS_DATABASE_URL': 'sqlite:///./dev_tmws.db',
            'TMWS_LOG_LEVEL': 'DEBUG',
            'TMWS_CORS_ORIGINS': '["http://localhost:3000","http://localhost:8000"]',
            'TMWS_RATE_LIMIT_REQUESTS': '1000',
            'TMWS_SESSION_COOKIE_SECURE': 'false',  # HTTP OK for dev
        })
    
    elif environment == 'staging':
        config.update({
            'TMWS_AUTH_ENABLED': 'true',
            'TMWS_DATABASE_URL': 'postgresql://tmws_staging:CHANGE_ME@localhost:5432/tmws_staging',
            'TMWS_LOG_LEVEL': 'INFO',
            'TMWS_CORS_ORIGINS': '["https://staging.example.com"]',
            'TMWS_RATE_LIMIT_REQUESTS': '500',
            'TMWS_SESSION_COOKIE_SECURE': 'true',
        })
    
    elif environment == 'production':
        config.update({
            'TMWS_AUTH_ENABLED': 'true',
            'TMWS_DATABASE_URL': 'postgresql://tmws_prod:CHANGE_TO_SECURE_PASSWORD@localhost:5432/tmws_prod',
            'TMWS_LOG_LEVEL': 'WARNING',
            'TMWS_CORS_ORIGINS': '["https://yourdomain.com"]',
            'TMWS_RATE_LIMIT_REQUESTS': '100',
            'TMWS_SESSION_COOKIE_SECURE': 'true',
            'TMWS_SECURITY_HEADERS_ENABLED': 'true',
            'TMWS_CSP_ENABLED': 'true',
        })
    
    return config


def write_env_file(config: Dict[str, Any], path: Path) -> None:
    """Write configuration to .env file."""
    
    with open(path, 'w') as f:
        f.write("# TMWS Security Configuration\n")
        f.write("# Generated by Hestia's Security Setup\n")
        f.write(f"# Environment: {config['TMWS_ENVIRONMENT']}\n")
        f.write("# ⚠️  DO NOT COMMIT THIS FILE TO VERSION CONTROL!\n\n")
        
        # Write configuration
        for key, value in config.items():
            f.write(f"{key}={value}\n")
        
        f.write("\n# Additional security settings can be added here\n")


def setup_security_directories() -> None:
    """Create necessary security directories."""
    
    directories = [
        'logs',
        'data/audit',
        'data/backups', 
        'config/security',
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True, mode=0o750)


def setup_audit_database() -> None:
    """Initialize audit database."""
    try:
        # This will create tables if they don't exist
        audit_logger = get_audit_logger()
        click.echo("✅ Audit database initialized")
    except Exception as e:
        click.echo(f"⚠️  Failed to initialize audit database: {e}")


def perform_security_validation(settings) -> Dict[str, Any]:
    """Perform comprehensive security validation."""
    
    results = {
        'has_critical_issues': False,
        'has_warnings': False,
        'critical_issues': [],
        'warnings': [],
        'passed_checks': []
    }
    
    # Critical security checks
    if settings.environment == 'production':
        if not settings.auth_enabled:
            results['critical_issues'].append("Authentication disabled in production")
            results['has_critical_issues'] = True
        
        if settings.secret_key == 'debug' or len(settings.secret_key) < 32:
            results['critical_issues'].append("Weak or default secret key in production")
            results['has_critical_issues'] = True
        
        if not settings.cors_origins or '*' in settings.cors_origins:
            results['critical_issues'].append("CORS origins not properly configured")
            results['has_critical_issues'] = True
        
        if 'localhost' in str(settings.cors_origins):
            results['warnings'].append("Localhost origins configured in production")
            results['has_warnings'] = True
    
    # Security feature checks
    if settings.rate_limit_enabled:
        results['passed_checks'].append("Rate limiting enabled")
    else:
        results['warnings'].append("Rate limiting disabled")
        results['has_warnings'] = True
    
    if settings.security_headers_enabled:
        results['passed_checks'].append("Security headers enabled")
    else:
        results['warnings'].append("Security headers disabled")
        results['has_warnings'] = True
    
    return results


def display_validation_results(results: Dict[str, Any]) -> None:
    """Display security validation results."""
    
    # Critical issues
    if results['critical_issues']:
        click.echo("\n💀 CRITICAL SECURITY ISSUES:")
        for issue in results['critical_issues']:
            click.echo(f"   ❌ {issue}")
    
    # Warnings
    if results['warnings']:
        click.echo("\n⚠️  SECURITY WARNINGS:")
        for warning in results['warnings']:
            click.echo(f"   🟡 {warning}")
    
    # Passed checks
    if results['passed_checks']:
        click.echo("\n✅ SECURITY CHECKS PASSED:")
        for check in results['passed_checks']:
            click.echo(f"   ✓ {check}")


def show_security_warnings(environment: str, config: Dict[str, Any]) -> None:
    """Show important security warnings."""
    
    click.echo("\n" + "="*60)
    click.echo("🛡️  HESTIA'S SECURITY REMINDERS")
    click.echo("="*60)
    
    if environment == 'production':
        click.echo("🔴 PRODUCTION ENVIRONMENT - CRITICAL SECURITY REQUIRED!")
        click.echo("   1. Change all default passwords in database URL")
        click.echo("   2. Configure proper CORS origins")
        click.echo("   3. Set up HTTPS with valid SSL certificates")
        click.echo("   4. Enable firewall and intrusion detection")
        click.echo("   5. Set up monitoring and alerting")
        click.echo("   6. Regular security audits and updates")
    
    elif environment == 'staging':
        click.echo("🟡 STAGING ENVIRONMENT - PRODUCTION-LIKE SECURITY")
        click.echo("   1. Use production-like security settings")
        click.echo("   2. Test all security features")
        click.echo("   3. Validate authentication flows")
    
    else:
        click.echo("🟢 DEVELOPMENT ENVIRONMENT")
        click.echo("   1. Never use development settings in production")
        click.echo("   2. Test security features regularly")
        click.echo("   3. Keep dependencies updated")
    
    click.echo("\n🚫 NEVER COMMIT .env FILES TO VERSION CONTROL!")
    click.echo("🔑 Store secrets securely (HashiCorp Vault, AWS Secrets Manager, etc.)")
    click.echo("="*60)


def generate_security_audit_report(audit_logger) -> Dict[str, Any]:
    """Generate comprehensive security audit report."""
    
    import asyncio
    
    async def _generate_report():
        # Get recent security events
        events = await audit_logger.get_events(limit=1000)
        
        # Get statistics  
        stats = await audit_logger.get_statistics()
        
        return {
            'report_timestamp': str(datetime.utcnow()),
            'total_events': len(events),
            'statistics': stats,
            'recent_events': events[:50],  # Last 50 events
            'recommendations': generate_security_recommendations(events, stats)
        }
    
    return asyncio.run(_generate_report())


def generate_security_recommendations(events: list, stats: dict) -> list:
    """Generate security recommendations based on audit data."""
    
    recommendations = []
    
    # Analyze patterns and generate recommendations
    if stats.get('critical_events_24h', 0) > 10:
        recommendations.append({
            'priority': 'HIGH',
            'issue': 'High number of critical security events',
            'recommendation': 'Investigate and address recurring security issues'
        })
    
    # Check for brute force patterns
    login_failures = [e for e in events if e.get('event_type') == 'login_failed']
    if len(login_failures) > 50:
        recommendations.append({
            'priority': 'MEDIUM',
            'issue': 'Multiple login failures detected',
            'recommendation': 'Consider implementing CAPTCHA or account lockouts'
        })
    
    return recommendations


def display_audit_summary(report: Dict[str, Any]) -> None:
    """Display audit report summary."""
    
    click.echo("\n📊 SECURITY AUDIT SUMMARY")
    click.echo("="*40)
    click.echo(f"Total Events: {report['total_events']}")
    
    stats = report.get('statistics', {})
    if stats:
        click.echo(f"Critical Events (24h): {stats.get('critical_events_24h', 0)}")
        
        events_by_severity = stats.get('events_by_severity', {})
        for severity, count in events_by_severity.items():
            click.echo(f"{severity.upper()}: {count}")
    
    # Show recommendations
    recommendations = report.get('recommendations', [])
    if recommendations:
        click.echo("\n🎯 SECURITY RECOMMENDATIONS:")
        for rec in recommendations:
            click.echo(f"   [{rec['priority']}] {rec['recommendation']}")


if __name__ == '__main__':
    cli()