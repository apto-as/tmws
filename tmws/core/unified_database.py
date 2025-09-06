"""
Unified Database Management for TMWS
Shared connection pool and session management for FastMCP and FastAPI
Enhanced by Bellona's Tactical Coordination
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, Dict, Any
from functools import lru_cache

import sqlalchemy as sa
from sqlalchemy import event, pool
from sqlalchemy.ext.asyncio import (
    AsyncSession, 
    async_sessionmaker, 
    create_async_engine,
    AsyncEngine
)

from .config import get_settings

logger = logging.getLogger(__name__)

# Singleton instances for shared resources
_shared_engine: Optional[AsyncEngine] = None
_shared_session_maker: Optional[async_sessionmaker] = None
_engine_lock = asyncio.Lock()
_connection_stats: Dict[str, int] = {
    "fastmcp_connections": 0,
    "fastapi_connections": 0,
    "total_queries": 0,
    "cache_hits": 0
}


class UnifiedDatabaseManager:
    """
    Unified database manager for sharing connections between FastMCP and FastAPI
    Implements Bellona's tactical resource optimization patterns
    """
    
    def __init__(self):
        self.engine: Optional[AsyncEngine] = None
        self.session_maker: Optional[async_sessionmaker] = None
        self.is_initialized = False
        self._query_cache = {}  # Simple query cache
        self._cache_max_size = 100
        
    async def initialize(self, force: bool = False) -> bool:
        """Initialize the shared database connection pool"""
        global _shared_engine, _shared_session_maker
        
        async with _engine_lock:
            if self.is_initialized and not force:
                logger.info("[TACTICAL] Database already initialized")
                return True
            
            try:
                settings = get_settings()
                
                # Create optimized connection pool for unified server
                pool_config = {
                    "echo": settings.db_echo_sql and not settings.is_production,
                    "echo_pool": False,
                    "pool_recycle": 3600,  # Recycle connections after 1 hour
                    "pool_pre_ping": True,  # Verify connections before use
                }
                
                # PostgreSQL-specific optimizations (only PostgreSQL is supported)
                pool_config.update({
                    "poolclass": pool.AsyncAdaptedQueuePool,
                    "pool_size": 10,  # Base pool size
                    "max_overflow": 20,  # Allow up to 30 total connections
                    "connect_args": {
                        "server_settings": {
                            "application_name": "tmws_unified",
                            "jit": "off",
                        },
                        "prepared_statement_cache_size": 256,
                        "tcp_keepalives_idle": "600",
                        "tcp_keepalives_interval": "30",
                        "tcp_keepalives_count": "10",
                    }
                })
                
                # Create the shared engine
                self.engine = create_async_engine(
                    settings.database_url_async,
                    **pool_config
                )
                
                # Create shared session maker
                self.session_maker = async_sessionmaker(
                    self.engine,
                    class_=AsyncSession,
                    expire_on_commit=False,
                    autoflush=True,
                    autocommit=False,
                )
                
                # Store globally for access by both services
                _shared_engine = self.engine
                _shared_session_maker = self.session_maker
                
                # Setup connection monitoring
                self._setup_monitoring()
                
                # Test the connection
                await self.health_check()
                
                self.is_initialized = True
                logger.info("[TACTICAL] Unified database pool initialized successfully")
                return True
                
            except Exception as e:
                logger.error(f"[TACTICAL] Failed to initialize database: {e}")
                raise
    
    def _setup_monitoring(self):
        """Setup connection monitoring and optimization hooks"""
        
        @event.listens_for(self.engine.sync_engine, "connect")
        def on_connect(dbapi_conn, connection_record):
            """Configure connection on creation"""
            connection_record.info['service'] = 'unified'
            
            # PostgreSQL performance optimizations
            cursor = dbapi_conn.cursor()
            cursor.execute("SET work_mem = '16MB'")
            cursor.execute("SET effective_cache_size = '256MB'")
            cursor.close()
        
        @event.listens_for(self.engine.sync_engine, "checkout")
        def on_checkout(dbapi_conn, connection_record, connection_proxy):
            """Monitor connection checkout"""
            _connection_stats["total_queries"] += 1
            logger.debug(f"[POOL] Connection checked out (total queries: {_connection_stats['total_queries']})")
    
    @asynccontextmanager
    async def get_session(self, service_name: str = "unified") -> AsyncGenerator[AsyncSession, None]:
        """
        Get a database session with automatic cleanup
        
        Args:
            service_name: Name of the service using the session (for monitoring)
        """
        if not self.is_initialized:
            await self.initialize()
        
        # Track connection usage by service
        if service_name.startswith("mcp"):
            _connection_stats["fastmcp_connections"] += 1
        elif service_name.startswith("api"):
            _connection_stats["fastapi_connections"] += 1
        
        async with self.session_maker() as session:
            try:
                # Set session-level optimizations
                if "postgresql" in str(session.bind.url):
                    await session.execute(sa.text("SET statement_timeout = '30s'"))
                
                yield session
                await session.commit()
                
            except Exception as e:
                await session.rollback()
                logger.error(f"[{service_name}] Database session error: {e}")
                raise
            finally:
                await session.close()
    
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check with metrics"""
        try:
            async with self.get_session("health_check") as session:
                result = await session.execute(sa.text("SELECT 1"))
                
                # Get pool statistics
                pool_stats = {
                    "size": self.engine.pool.size() if hasattr(self.engine.pool, 'size') else 0,
                    "checked_in": self.engine.pool.checkedin() if hasattr(self.engine.pool, 'checkedin') else 0,
                    "checked_out": self.engine.pool.checkedout() if hasattr(self.engine.pool, 'checkedout') else 0,
                    "overflow": self.engine.pool.overflow() if hasattr(self.engine.pool, 'overflow') else 0,
                }
                
                return {
                    "status": "healthy",
                    "pool_stats": pool_stats,
                    "connection_stats": _connection_stats.copy(),
                    "cache_hit_rate": (
                        _connection_stats["cache_hits"] / max(_connection_stats["total_queries"], 1) * 100
                    )
                }
                
        except Exception as e:
            logger.error(f"[TACTICAL] Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "connection_stats": _connection_stats.copy()
            }
    
    async def optimize_connections(self):
        """Tactical connection pool optimization"""
        logger.info("[TACTICAL] Running connection pool optimization")
        
        # Clear query cache if too large
        if len(self._query_cache) > self._cache_max_size:
            self._query_cache.clear()
            logger.info("[TACTICAL] Query cache cleared")
        
        # Recycle idle connections
        if hasattr(self.engine.pool, 'recreate'):
            self.engine.pool.recreate()
            logger.info("[TACTICAL] Connection pool recreated")
    
    async def shutdown(self):
        """Graceful shutdown of database connections"""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.session_maker = None
            self.is_initialized = False
            logger.info("[TACTICAL] Database connections closed")


# Global instance for unified access
_unified_db_manager = UnifiedDatabaseManager()


# Convenience functions for backward compatibility
async def get_unified_db_session(service_name: str = "unified") -> AsyncGenerator[AsyncSession, None]:
    """Get a database session from the unified pool"""
    async with _unified_db_manager.get_session(service_name) as session:
        yield session


async def initialize_unified_database(force: bool = False) -> bool:
    """Initialize the unified database manager"""
    return await _unified_db_manager.initialize(force)


async def get_unified_health_status() -> Dict[str, Any]:
    """Get health status of the unified database"""
    return await _unified_db_manager.health_check()


async def shutdown_unified_database():
    """Shutdown the unified database manager"""
    await _unified_db_manager.shutdown()


# Export the manager for direct access if needed
def get_unified_db_manager() -> UnifiedDatabaseManager:
    """Get the unified database manager instance"""
    return _unified_db_manager