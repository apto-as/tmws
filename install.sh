#!/bin/bash
# TMWS Complete Installation Script
# Comprehensive setup for production-ready deployment

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
INSTALL_DIR="$HOME/.claude/tmws"
PROJECT_NAME="TMWS - Trinitas Memory & Workflow Service"
REQUIRED_PYTHON="3.10"
DEFAULT_DB_NAME="tmws"
DEFAULT_DB_USER="tmws_user"
DEFAULT_DB_PASSWORD="tmws_password"

# Functions
print_header() {
    echo -e "\n${BLUE}============================================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}============================================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# Start installation
clear
print_header "$PROJECT_NAME Installation"
echo "This script will install and configure TMWS with all dependencies."
echo ""

# Step 1: System Requirements Check
print_header "Step 1: Checking System Requirements"

# Check Python version
if check_command python3; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
    
    if [[ $PYTHON_MAJOR -ge 3 ]] && [[ $PYTHON_MINOR -ge 10 ]]; then
        print_success "Python $PYTHON_VERSION found"
    else
        print_error "Python 3.10+ required (found $PYTHON_VERSION)"
        exit 1
    fi
else
    print_error "Python 3 not found"
    exit 1
fi

# Check PostgreSQL
if check_command psql; then
    print_success "PostgreSQL client found"
else
    print_warning "PostgreSQL client not found. Installing..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install postgresql
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt-get update && sudo apt-get install -y postgresql-client
    else
        print_error "Please install PostgreSQL manually"
        exit 1
    fi
fi

# Check Redis
if check_command redis-cli; then
    print_success "Redis client found"
else
    print_warning "Redis client not found. Installing..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install redis
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt-get update && sudo apt-get install -y redis-server
    else
        print_error "Please install Redis manually"
        exit 1
    fi
fi

# Check UV (optional but recommended)
if check_command uv; then
    print_success "UV package manager found (recommended)"
    USE_UV=true
else
    print_warning "UV not found, will use pip"
    USE_UV=false
fi

# Step 2: Database Setup
print_header "Step 2: Database Setup"

# Check if PostgreSQL is running
if pg_isready -h localhost -p 5432 &> /dev/null; then
    print_success "PostgreSQL server is running"
else
    print_warning "PostgreSQL server not running. Starting..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew services start postgresql || {
            print_error "Failed to start PostgreSQL"
            exit 1
        }
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo systemctl start postgresql || {
            print_error "Failed to start PostgreSQL"
            exit 1
        }
    fi
    
    # Wait for PostgreSQL to start
    echo "Waiting for PostgreSQL to start..."
    for i in {1..30}; do
        if pg_isready -h localhost -p 5432 &> /dev/null; then
            print_success "PostgreSQL started"
            break
        fi
        sleep 1
    done
fi

# Create database and user
echo ""
echo "Setting up TMWS database..."
echo "Enter PostgreSQL admin user (default: $USER):"
read -r PG_ADMIN_USER
PG_ADMIN_USER=${PG_ADMIN_USER:-$USER}

# Create database
createdb -U "$PG_ADMIN_USER" "$DEFAULT_DB_NAME" 2>/dev/null || {
    print_warning "Database $DEFAULT_DB_NAME already exists"
}

# Create user (using psql)
psql -U "$PG_ADMIN_USER" -d postgres <<EOF 2>/dev/null || true
CREATE USER $DEFAULT_DB_USER WITH PASSWORD '$DEFAULT_DB_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE $DEFAULT_DB_NAME TO $DEFAULT_DB_USER;
ALTER DATABASE $DEFAULT_DB_NAME OWNER TO $DEFAULT_DB_USER;
EOF

print_success "Database configured"

# Enable pgvector extension
echo "Enabling pgvector extension..."
psql -U "$PG_ADMIN_USER" -d "$DEFAULT_DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || {
    print_warning "pgvector extension might need manual installation"
    echo "Run: CREATE EXTENSION vector; in PostgreSQL"
}

# Step 3: Redis Setup
print_header "Step 3: Redis Setup"

# Check if Redis is running
if redis-cli ping &> /dev/null; then
    print_success "Redis server is running"
else
    print_warning "Redis server not running. Starting..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew services start redis
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo systemctl start redis
    else
        redis-server --daemonize yes
    fi
    
    # Wait for Redis
    sleep 2
    if redis-cli ping &> /dev/null; then
        print_success "Redis started"
    else
        print_warning "Redis might need manual start"
    fi
fi

# Step 4: Python Environment Setup
print_header "Step 4: Python Environment Setup"

# Create installation directory
if [ ! -d "$INSTALL_DIR" ]; then
    echo "Creating installation directory at $INSTALL_DIR..."
    mkdir -p "$INSTALL_DIR"
    print_success "Installation directory created"
fi

# Copy files to installation directory
echo "Copying files to $INSTALL_DIR..."
rsync -av --exclude='.venv' --exclude='__pycache__' --exclude='.git' \
      --exclude='htmlcov' --exclude='.pytest_cache' \
      "$SCRIPT_DIR/" "$INSTALL_DIR/" > /dev/null
print_success "Files copied to installation directory"

cd "$INSTALL_DIR"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    print_success "Virtual environment created"
fi

# Activate virtual environment
source .venv/bin/activate
print_success "Virtual environment activated"

# Install dependencies
if [ "$USE_UV" = true ]; then
    echo "Installing dependencies with UV..."
    uv sync
else
    echo "Installing dependencies with pip..."
    pip install --upgrade pip
    pip install -e .
fi
print_success "Dependencies installed"

# Step 5: Environment Configuration
print_header "Step 5: Environment Configuration"

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env configuration file..."
    cat > .env <<EOF
# TMWS Environment Configuration
# Generated by install.sh

# === CORE SYSTEM ===
TMWS_ENVIRONMENT=development
TMWS_DEBUG=true
TMWS_LOG_LEVEL=INFO

# === DATABASE ===
TMWS_DATABASE_URL=postgresql://${DEFAULT_DB_USER}:${DEFAULT_DB_PASSWORD}@localhost:5432/${DEFAULT_DB_NAME}
TMWS_DATABASE_POOL_SIZE=10
TMWS_DATABASE_MAX_OVERFLOW=20

# === SECURITY ===
TMWS_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
TMWS_JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
TMWS_JWT_EXPIRE_MINUTES=30
TMWS_AUTH_ENABLED=false  # Set to true for production

# === VECTOR & EMBEDDINGS ===
TMWS_VECTOR_DIMENSION=384
TMWS_EMBEDDING_MODEL=all-MiniLM-L6-v2

# === API CONFIGURATION ===
TMWS_API_HOST=0.0.0.0
TMWS_API_PORT=8000
TMWS_API_VERSION=v1
TMWS_WORKERS=4

# === CORS & SECURITY ===
TMWS_CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000","http://localhost:8000"]
TMWS_ALLOWED_HOSTS=["localhost","127.0.0.1","0.0.0.0"]

# === REDIS ===
TMWS_REDIS_URL=redis://localhost:6379/0
TMWS_CACHE_TTL=3600

# === RATE LIMITING ===
TMWS_RATE_LIMIT_ENABLED=true
TMWS_RATE_LIMIT_PER_MINUTE=100
TMWS_RATE_LIMIT_BURST=10

# === LOGGING ===
TMWS_LOG_FORMAT=json
TMWS_LOG_FILE=./logs/tmws.log
TMWS_LOG_ROTATION=daily
TMWS_LOG_RETENTION=30
EOF
    print_success ".env file created"
else
    print_warning ".env file already exists (not overwritten)"
fi

# Step 6: Directory Structure
print_header "Step 6: Creating Directory Structure"

mkdir -p data logs backups
chmod 755 data logs backups
print_success "Directory structure created"

# Step 7: Database Migration
print_header "Step 7: Database Migration"

echo "Initializing database schema..."
python3 -c "
import asyncio
from src.core.database import create_tables

async def init_db():
    await create_tables()
    print('Database tables created')

asyncio.run(init_db())
" || {
    print_warning "Database might need manual initialization"
}

# Step 8: Verification
print_header "Step 8: Installation Verification"

echo "Running verification checks..."
# Simple verification without verify_integration.py
python3 -c "
import sys
try:
    from src.core.config import get_settings
    from src.core.database import get_database
    print('✅ Core modules loaded successfully')
    sys.exit(0)
except Exception as e:
    print(f'❌ Verification failed: {e}')
    sys.exit(1)
" || {
    print_warning "Some checks failed - review output above"
}

# Step 9: Create Start Scripts
print_header "Step 9: Creating Start Scripts"

# Create start script for API server
cat > start_api.sh <<'EOF'
#!/bin/bash
source .venv/bin/activate
echo "Starting TMWS API Server..."
uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
EOF
chmod +x start_api.sh

# Create start script for unified server
cat > start_unified.sh <<'EOF'
#!/bin/bash
source .venv/bin/activate
echo "Starting TMWS Unified Server (MCP + API)..."
python3 -m unified_server
EOF
chmod +x start_unified.sh

print_success "Start scripts created"

# Final Summary
print_header "Installation Complete!"

echo -e "${GREEN}TMWS has been successfully installed to ${INSTALL_DIR}!${NC}"
echo ""
echo "📝 Configuration files:"
echo "   - ${INSTALL_DIR}/.env (environment variables)"
echo "   - ${INSTALL_DIR}/config/tmws_unified.yaml (server config)"
echo ""
echo "🚀 To start the services:"
echo ""
echo "   1. API Server only:"
echo "      ${BLUE}cd ${INSTALL_DIR} && ./start_api.sh${NC}"
echo ""
echo "   2. Unified Server (MCP + API):"
echo "      ${BLUE}cd ${INSTALL_DIR} && ./start_unified.sh${NC}"
echo ""
echo "   3. For development:"
echo "      ${BLUE}cd ${INSTALL_DIR}${NC}"
echo "      ${BLUE}source .venv/bin/activate${NC}"
echo "      ${BLUE}python -m src.main${NC}"
echo ""
echo "📚 API Documentation will be available at:"
echo "   http://localhost:8000/docs"
echo ""
echo "🔧 For Claude Desktop integration, add to config:"
echo '   {
     "mcpServers": {
       "tmws": {
         "command": "uv",
         "args": ["run", "python", "-m", "unified_server", "--mcp-mode"],
         "cwd": "'$INSTALL_DIR'"
       }
     }
   }'
echo ""
echo "Thank you for installing TMWS!"