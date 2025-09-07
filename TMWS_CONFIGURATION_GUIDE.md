# TMWS Configuration Guide

## Complete Environment Variables List

TMWS requires various environment variables for proper operation. Below is a comprehensive list of all configuration options that need to be set in your JSON configuration file.

## Required Environment Variables

### 1. Database Configuration (REQUIRED)
```json
{
  "TMWS_DATABASE_URL": "postgresql://user:password@localhost:5432/tmws_db",
  // Alternative: "DATABASE_URL" can also be used
  
  // Or use individual components:
  "TMWS_DB_HOST": "localhost",
  "TMWS_DB_PORT": "5432",
  "TMWS_DB_NAME": "tmws_db",
  "TMWS_DB_USER": "tmws_user",
  "TMWS_DB_PASSWORD": "secure_password"
}
```

### 2. Security Configuration (REQUIRED)
```json
{
  "TMWS_SECRET_KEY": "your-secret-key-minimum-32-characters-long",
  // Used for JWT token signing and encryption
  // MUST be at least 32 characters in production
  // Generate with: openssl rand -base64 32
}
```

### 3. Environment Configuration (REQUIRED)
```json
{
  "TMWS_ENVIRONMENT": "development",  // or "staging" or "production"
  // Controls security validations and logging levels
}
```

## Agent-Specific Configuration

### 4. Agent Identity (REQUIRED for MCP)
```json
{
  "TMWS_AGENT_ID": "your-agent-identifier",
  // Alternative: "MCP_AGENT_ID" can also be used
  // Examples: "claude-assistant", "gpt-4-agent", "custom-bot-01"
  // Pattern: alphanumeric with hyphens, underscores, dots (3-63 chars)
  
  "TMWS_AGENT_NAMESPACE": "default",
  // Namespace for memory isolation (default: "default")
  // Examples: "project-alpha", "team-research", "personal"
  
  "TMWS_AGENT_CAPABILITIES": "{\"language_model\": true, \"code_generation\": true, \"web_search\": false}",
  // JSON string of agent capabilities
  // Used for optimization and feature access control
}
```

### 5. Testing Configuration (OPTIONAL)
```json
{
  "TMWS_ALLOW_DEFAULT_AGENT": "true",
  // Only for development/testing
  // Allows running without explicit agent ID
  // NEVER use in production
}
```

## API Configuration

### 6. FastAPI Settings (OPTIONAL)
```json
{
  "TMWS_API_HOST": "127.0.0.1",     // Default: localhost only
  "TMWS_API_PORT": "8000",          // Default: 8000
  "TMWS_API_RELOAD": "false",       // Auto-reload (dev only)
  
  "TMWS_CORS_ORIGINS": "[\"http://localhost:3000\", \"https://app.example.com\"]",
  // JSON array of allowed CORS origins
  // MUST be set explicitly in production
  
  "TMWS_AUTH_ENABLED": "true",      // Enable authentication
  "TMWS_MCP_ENABLED": "true"        // Enable MCP protocol
}
```

## Advanced Configuration

### 7. Database Pool Settings (OPTIONAL)
```json
{
  "TMWS_DB_MAX_CONNECTIONS": "10",  // Max database connections
  "TMWS_DB_ECHO_SQL": "false",      // Log SQL queries (dev only)
  "TMWS_DB_POOL_PRE_PING": "true",  // Check connection health
  "TMWS_DB_POOL_RECYCLE": "3600"    // Recycle connections (seconds)
}
```

### 8. JWT Authentication (OPTIONAL)
```json
{
  "TMWS_JWT_ALGORITHM": "HS256",    // or "RS256", "ES256"
  "TMWS_JWT_EXPIRE_MINUTES": "30",  // Access token expiry
  "TMWS_JWT_REFRESH_EXPIRE_DAYS": "7" // Refresh token expiry
}
```

### 9. Security Headers (OPTIONAL)
```json
{
  "TMWS_SECURITY_HEADERS_ENABLED": "true",
  "TMWS_SESSION_COOKIE_SECURE": "true",    // HTTPS only
  "TMWS_SESSION_COOKIE_HTTPONLY": "true",  // No JS access
  "TMWS_SESSION_COOKIE_SAMESITE": "strict", // CSRF protection
  
  "TMWS_CSP_ENABLED": "true",
  "TMWS_CSP_POLICY": "default-src 'self'; script-src 'self'"
}
```

### 10. Rate Limiting (OPTIONAL)
```json
{
  "TMWS_RATE_LIMIT_ENABLED": "true",
  "TMWS_RATE_LIMIT_REQUESTS": "100", // Requests per period
  "TMWS_RATE_LIMIT_PERIOD": "60",    // Period in seconds
  
  "TMWS_MAX_LOGIN_ATTEMPTS": "5",
  "TMWS_LOCKOUT_DURATION_MINUTES": "15"
}
```

### 11. Vector Search Configuration (OPTIONAL)
```json
{
  "TMWS_EMBEDDING_MODEL": "all-MiniLM-L6-v2",
  "TMWS_VECTOR_DIMENSION": "384",
  "TMWS_MAX_EMBEDDING_BATCH_SIZE": "32"
}
```

### 12. Logging Configuration (OPTIONAL)
```json
{
  "TMWS_LOG_LEVEL": "INFO",         // DEBUG, INFO, WARNING, ERROR, CRITICAL
  "TMWS_LOG_FILE": "/var/log/tmws/app.log",
  "TMWS_LOG_FORMAT": "json",        // or "text"
  
  "TMWS_SECURITY_LOG_ENABLED": "true",
  "TMWS_AUDIT_LOG_ENABLED": "true"
}
```

### 13. Performance & Caching (OPTIONAL)
```json
{
  "TMWS_CACHE_TTL": "3600",         // Cache time-to-live (seconds)
  "TMWS_CACHE_MAX_SIZE": "1000"     // Max cache entries
}
```

### 14. Tactical Mode (OPTIONAL)
```json
{
  "TMWS_TACTICAL_MODE": "balanced"   // or "aggressive", "defensive"
}
```

## Complete Example Configuration

### Development Environment
```json
{
  "TMWS_DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/tmws_dev",
  "TMWS_SECRET_KEY": "development-secret-key-change-in-production-1234567890",
  "TMWS_ENVIRONMENT": "development",
  "TMWS_AGENT_ID": "test-agent",
  "TMWS_AGENT_NAMESPACE": "development",
  "TMWS_ALLOW_DEFAULT_AGENT": "true",
  "TMWS_AUTH_ENABLED": "false",
  "TMWS_LOG_LEVEL": "DEBUG"
}
```

### Production Environment
```json
{
  "TMWS_DATABASE_URL": "postgresql://tmws_prod:SecurePass123!@db.production.internal:5432/tmws_production?sslmode=require",
  "TMWS_SECRET_KEY": "RaNd0mLy-G3n3rat3d-S3cur3-K3y-W1th-M1n1mum-32-Ch4rs",
  "TMWS_ENVIRONMENT": "production",
  "TMWS_AGENT_ID": "production-claude-assistant",
  "TMWS_AGENT_NAMESPACE": "production",
  "TMWS_AGENT_CAPABILITIES": "{\"language_model\": true, \"code_generation\": true, \"web_search\": true, \"memory_access\": true}",
  "TMWS_AUTH_ENABLED": "true",
  "TMWS_CORS_ORIGINS": "[\"https://app.example.com\", \"https://api.example.com\"]",
  "TMWS_RATE_LIMIT_ENABLED": "true",
  "TMWS_SECURITY_HEADERS_ENABLED": "true",
  "TMWS_LOG_LEVEL": "INFO",
  "TMWS_AUDIT_LOG_ENABLED": "true"
}
```

## Configuration File Formats

### Using .env file
```bash
TMWS_DATABASE_URL=postgresql://user:pass@localhost:5432/tmws
TMWS_SECRET_KEY=your-secret-key-here
TMWS_ENVIRONMENT=development
TMWS_AGENT_ID=my-agent
```

### Using JSON file (tmws_config.json)
```json
{
  "environment_variables": {
    "TMWS_DATABASE_URL": "postgresql://user:pass@localhost:5432/tmws",
    "TMWS_SECRET_KEY": "your-secret-key-here",
    "TMWS_ENVIRONMENT": "development",
    "TMWS_AGENT_ID": "my-agent"
  }
}
```

### Using Docker Compose
```yaml
services:
  tmws:
    image: tmws:latest
    environment:
      TMWS_DATABASE_URL: postgresql://user:pass@db:5432/tmws
      TMWS_SECRET_KEY: ${SECRET_KEY}
      TMWS_ENVIRONMENT: production
      TMWS_AGENT_ID: docker-agent
```

## Configuration Priority

Environment variables are loaded in the following priority order:
1. System environment variables
2. .env file in project root
3. JSON configuration file
4. Default values (if available)

## Security Notes

1. **Never commit secrets**: Keep `.env` files and config files with secrets out of version control
2. **Use strong secret keys**: Generate with `openssl rand -base64 32`
3. **Rotate keys regularly**: Change secret keys periodically
4. **Use SSL in production**: Always use `sslmode=require` for PostgreSQL in production
5. **Restrict CORS origins**: Never use `*` in production
6. **Enable authentication**: Always set `TMWS_AUTH_ENABLED=true` in production
7. **Validate agent IDs**: Use the pattern validation to prevent injection attacks

## Database Setup

Before running TMWS, ensure PostgreSQL is installed and configured:

```bash
# Create database
createdb tmws_db

# Create user
createuser -P tmws_user

# Grant privileges
psql -c "GRANT ALL PRIVILEGES ON DATABASE tmws_db TO tmws_user;"

# Enable pgvector extension (for vector search)
psql -d tmws_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

## Testing Configuration

To test your configuration:

```bash
# Export all variables
export TMWS_DATABASE_URL="postgresql://localhost/tmws_test"
export TMWS_SECRET_KEY="test-secret-key-minimum-32-characters"
export TMWS_ENVIRONMENT="development"
export TMWS_AGENT_ID="test-agent"

# Run TMWS
python tmws/mcp_server.py

# Or with uvx
uvx --from git+https://github.com/apto-as/tmws.git tmws
```

## Troubleshooting

Common issues and solutions:

1. **"TMWS_DATABASE_URL environment variable is required"**
   - Set the database URL in your environment or config file

2. **"TMWS_SECRET_KEY environment variable is required"**
   - Generate and set a secret key (min 32 characters)

3. **"No agent detected"**
   - Set TMWS_AGENT_ID or MCP_AGENT_ID
   - For testing, set TMWS_ALLOW_DEFAULT_AGENT=true

4. **Database connection failed**
   - Check PostgreSQL is running
   - Verify connection string format
   - Ensure database and user exist
   - Check network connectivity

5. **"Weak or default secret key detected"**
   - Generate a strong random key for production
   - Avoid common patterns and dictionary words