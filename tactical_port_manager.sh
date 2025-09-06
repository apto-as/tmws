#!/bin/bash
# TMWS Tactical Port Management System
# Bellona's Coordinated Service Management Script
# Version: 1.0.0

set -euo pipefail

# ============================================================================
# TACTICAL CONFIGURATION
# ============================================================================

# Service Port Definitions
readonly POSTGRES_PORT=5432
readonly POSTGRES_BACKUP_PORT=5433
readonly REDIS_PORT=6379
readonly REDIS_BACKUP_PORT=6380
readonly API_PORT=8000
readonly API_BACKUP_PORT=8001
readonly HEALTH_PORT=8090

# Service Status Tracking
declare -A SERVICE_STATUS
SERVICE_STATUS[postgresql]="OFFLINE"
SERVICE_STATUS[redis]="OFFLINE"
SERVICE_STATUS[tmws_api]="OFFLINE"
SERVICE_STATUS[mcp_server]="OFFLINE"

# ============================================================================
# TACTICAL UTILITIES
# ============================================================================

log_tactical() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [TACTICAL] $1"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $1" >&2
}

check_port_availability() {
    local port=$1
    local service=$2
    
    if lsof -i ":$port" >/dev/null 2>&1; then
        log_error "Port $port is occupied. Service $service cannot bind."
        return 1
    else
        log_tactical "Port $port is available for service $service."
        return 0
    fi
}

wait_for_service() {
    local service=$1
    local port=$2
    local max_attempts=30
    local attempt=1
    
    log_tactical "Waiting for $service to be ready on port $port..."
    
    while [ $attempt -le $max_attempts ]; do
        case $service in
            "postgresql")
                if pg_isready -h localhost -p $port >/dev/null 2>&1; then
                    SERVICE_STATUS[postgresql]="ONLINE"
                    log_tactical "PostgreSQL is ready on port $port"
                    return 0
                fi
                ;;
            "redis")
                if redis-cli -p $port ping >/dev/null 2>&1; then
                    SERVICE_STATUS[redis]="ONLINE"
                    log_tactical "Redis is ready on port $port"
                    return 0
                fi
                ;;
            "tmws_api")
                if curl -s "http://localhost:$port/api/v1/health" >/dev/null 2>&1; then
                    SERVICE_STATUS[tmws_api]="ONLINE"
                    log_tactical "TMWS API is ready on port $port"
                    return 0
                fi
                ;;
        esac
        
        sleep 2
        ((attempt++))
    done
    
    log_error "$service failed to start within timeout period"
    return 1
}

# ============================================================================
# SERVICE MANAGEMENT FUNCTIONS
# ============================================================================

start_postgresql() {
    log_tactical "Initiating PostgreSQL startup sequence..."
    
    if check_port_availability $POSTGRES_PORT "PostgreSQL"; then
        # Check if PostgreSQL is already running
        if pgrep -x "postgres" >/dev/null; then
            log_tactical "PostgreSQL already running"
            SERVICE_STATUS[postgresql]="ONLINE"
        else
            # Start PostgreSQL service (platform-specific)
            if command -v brew >/dev/null 2>&1; then
                brew services start postgresql@14 2>/dev/null || brew services start postgresql
            elif command -v systemctl >/dev/null 2>&1; then
                sudo systemctl start postgresql
            else
                log_error "Unable to start PostgreSQL: unsupported platform"
                return 1
            fi
            
            wait_for_service "postgresql" $POSTGRES_PORT
        fi
    else
        log_error "PostgreSQL startup failed: port conflict"
        return 1
    fi
}

start_redis() {
    log_tactical "Initiating Redis startup sequence..."
    
    if check_port_availability $REDIS_PORT "Redis"; then
        # Check if Redis is already running
        if pgrep -x "redis-server" >/dev/null; then
            log_tactical "Redis already running"
            SERVICE_STATUS[redis]="ONLINE"
        else
            # Start Redis service
            if command -v brew >/dev/null 2>&1; then
                brew services start redis
            elif command -v systemctl >/dev/null 2>&1; then
                sudo systemctl start redis
            else
                # Fallback: direct redis-server start
                redis-server --daemonize yes --port $REDIS_PORT
            fi
            
            wait_for_service "redis" $REDIS_PORT
        fi
    else
        log_error "Redis startup failed: port conflict"
        return 1
    fi
}

start_tmws_api() {
    log_tactical "Initiating TMWS API startup sequence..."
    
    if check_port_availability $API_PORT "TMWS API"; then
        # Change to TMWS directory
        cd "$(dirname "$0")"
        
        # Verify environment
        if [ ! -f ".env" ]; then
            log_error "Environment file .env not found"
            return 1
        fi
        
        # Start API server in background
        log_tactical "Starting TMWS API server on port $API_PORT..."
        nohup python main.py > tmws_api.log 2>&1 &
        echo $! > tmws_api.pid
        
        wait_for_service "tmws_api" $API_PORT
    else
        log_error "TMWS API startup failed: port conflict"
        return 1
    fi
}

start_mcp_server() {
    log_tactical "Initiating MCP Server registration..."
    
    # MCP Server uses stdio, no port binding required
    if [ -f "mcp_server.py" ]; then
        log_tactical "MCP Server configuration verified"
        SERVICE_STATUS[mcp_server]="ONLINE"
    else
        log_error "MCP Server not found"
        return 1
    fi
}

# ============================================================================
# COORDINATED STARTUP SEQUENCE
# ============================================================================

execute_startup_sequence() {
    log_tactical "=== INITIATING COORDINATED STARTUP SEQUENCE ==="
    
    # Phase 1: Infrastructure Foundation (Parallel)
    log_tactical "Phase 1: Starting infrastructure services..."
    start_postgresql &
    PID_POSTGRES=$!
    start_redis &
    PID_REDIS=$!
    
    # Wait for infrastructure to be ready
    wait $PID_POSTGRES $PID_REDIS
    
    if [[ "${SERVICE_STATUS[postgresql]}" == "ONLINE" && "${SERVICE_STATUS[redis]}" == "ONLINE" ]]; then
        log_tactical "Phase 1 complete: Infrastructure online"
    else
        log_error "Phase 1 failed: Infrastructure not ready"
        return 1
    fi
    
    # Phase 2: Service Layer
    log_tactical "Phase 2: Starting application services..."
    start_tmws_api
    
    if [[ "${SERVICE_STATUS[tmws_api]}" == "ONLINE" ]]; then
        log_tactical "Phase 2 complete: Application services online"
    else
        log_error "Phase 2 failed: Application services not ready"
        return 1
    fi
    
    # Phase 3: Integration Layer
    log_tactical "Phase 3: Configuring integration layer..."
    start_mcp_server
    
    if [[ "${SERVICE_STATUS[mcp_server]}" == "ONLINE" ]]; then
        log_tactical "Phase 3 complete: Integration layer online"
    else
        log_error "Phase 3 failed: Integration layer not ready"
        return 1
    fi
    
    log_tactical "=== TACTICAL STARTUP SEQUENCE COMPLETE ==="
    display_service_status
}

# ============================================================================
# MONITORING AND STATUS
# ============================================================================

display_service_status() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║                    TACTICAL SERVICE STATUS                 ║"
    echo "╠════════════════════════════════════════════════════════════╣"
    
    for service in postgresql redis tmws_api mcp_server; do
        local status="${SERVICE_STATUS[$service]}"
        local color=""
        
        case $status in
            "ONLINE")  color="\033[32m" ;;  # Green
            "OFFLINE") color="\033[31m" ;;  # Red
            *)         color="\033[33m" ;;  # Yellow
        esac
        
        printf "║ %-20s │ %b%-8s\033[0m │ Status: Active     ║\n" "$service" "$color" "$status"
    done
    
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
}

health_check_all() {
    log_tactical "Executing comprehensive health check..."
    
    # PostgreSQL Health Check
    if pg_isready -h localhost -p $POSTGRES_PORT >/dev/null 2>&1; then
        SERVICE_STATUS[postgresql]="ONLINE"
    else
        SERVICE_STATUS[postgresql]="OFFLINE"
    fi
    
    # Redis Health Check
    if redis-cli -p $REDIS_PORT ping >/dev/null 2>&1; then
        SERVICE_STATUS[redis]="ONLINE"
    else
        SERVICE_STATUS[redis]="OFFLINE"
    fi
    
    # TMWS API Health Check
    if curl -s "http://localhost:$API_PORT/api/v1/health" >/dev/null 2>&1; then
        SERVICE_STATUS[tmws_api]="ONLINE"
    else
        SERVICE_STATUS[tmws_api]="OFFLINE"
    fi
    
    display_service_status
}

# ============================================================================
# SHUTDOWN PROCEDURES
# ============================================================================

graceful_shutdown() {
    log_tactical "Initiating graceful shutdown sequence..."
    
    # Shutdown in reverse order
    log_tactical "Stopping TMWS API..."
    if [ -f "tmws_api.pid" ]; then
        kill $(cat tmws_api.pid) 2>/dev/null || true
        rm -f tmws_api.pid
    fi
    
    log_tactical "Stopping Redis..."
    if command -v brew >/dev/null 2>&1; then
        brew services stop redis 2>/dev/null || true
    else
        redis-cli -p $REDIS_PORT shutdown 2>/dev/null || true
    fi
    
    log_tactical "Stopping PostgreSQL..."
    if command -v brew >/dev/null 2>&1; then
        brew services stop postgresql@14 2>/dev/null || brew services stop postgresql 2>/dev/null || true
    elif command -v systemctl >/dev/null 2>&1; then
        sudo systemctl stop postgresql 2>/dev/null || true
    fi
    
    log_tactical "Graceful shutdown complete"
}

# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

show_usage() {
    cat << EOF
TMWS Tactical Port Manager - Bellona's Service Coordination System

USAGE:
    $0 [COMMAND]

COMMANDS:
    start       Execute coordinated startup sequence
    stop        Execute graceful shutdown sequence
    status      Display current service status
    health      Run comprehensive health check
    restart     Execute full restart cycle
    help        Show this help message

EXAMPLES:
    $0 start          # Start all services in coordinated sequence
    $0 health         # Check health of all services
    $0 restart        # Full restart cycle

EOF
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

main() {
    case "${1:-help}" in
        "start")
            execute_startup_sequence
            ;;
        "stop")
            graceful_shutdown
            ;;
        "status")
            display_service_status
            ;;
        "health")
            health_check_all
            ;;
        "restart")
            graceful_shutdown
            sleep 3
            execute_startup_sequence
            ;;
        "help"|*)
            show_usage
            ;;
    esac
}

# Signal handlers
trap graceful_shutdown SIGTERM SIGINT

# Execute main function
main "$@"