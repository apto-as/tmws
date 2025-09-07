"""
Enhanced database configuration for TMWS v2.0 - Universal Multi-Agent Platform.
Optimized for high-performance multi-agent operations with advanced connection pooling.
"""

import asyncio
import logging
from contextlib import asynccontextmanager, contextmanager
from typing import Any, AsyncGenerator, Dict, Generator, Optional, Type
from urllib.parse import urlparse

import sqlalchemy as sa
from sqlalchemy import create_engine, event, pool, MetaData
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine
)
from sqlalchemy.orm import Session, sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool, NullPool
from alembic import command
from alembic.config import Config

from .config import settings
from .exceptions import DatabaseError, ConfigurationError

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Enhanced database manager with optimized connection pooling and multi-agent support.
    
    Features:
    - Optimized connection pools for different workload patterns
    - Read/write connection splitting for scalability
    - Advanced monitoring and diagnostics
    - Automatic failover and recovery
    - Multi-tenant isolation support
    """
    
    def __init__(self):
        self._sync_engine: Optional[sa.Engine] = None
        self._async_engine: Optional[AsyncEngine] = None
        self._sync_session_factory: Optional[sessionmaker] = None
        self._async_session_factory: Optional[async_sessionmaker] = None
        self._read_engine: Optional[sa.Engine] = None
        self._write_engine: Optional[sa.Engine] = None
        self._connection_pools: Dict[str, Any] = {}
        self._initialized = False
        self._lock = asyncio.Lock()
    
    @property
    def sync_engine(self) -> sa.Engine:
        """Get synchronous database engine."""
        if not self._sync_engine:
            raise DatabaseError("Database not initialized. Call initialize() first.")
        return self._sync_engine
    
    @property
    def async_engine(self) -> AsyncEngine:
        """Get asynchronous database engine."""
        if not self._async_engine:
            raise DatabaseError("Database not initialized. Call initialize() first.")
        return self._async_engine
    
    def _create_optimized_pool_config(self, workload_type: str = "mixed") -> Dict[str, Any]:
        """
        Create optimized connection pool configuration based on workload type.
        
        Workload types:
        - read_heavy: Optimized for read operations (larger pool, longer timeout)
        - write_heavy: Optimized for write operations (smaller pool, shorter timeout)
        - mixed: Balanced configuration (default)
        - batch: Optimized for batch operations (minimal pool, long timeout)
        """
        base_config = {
            "poolclass": QueuePool,
            "pool_pre_ping": True,
            "pool_recycle": 3600,  # 1 hour
            "pool_reset_on_return": "commit",
            "connect_args": {
                "connect_timeout": 30,
                "command_timeout": 60,
                "application_name": "tmws_v2"
            }
        }
        
        workload_configs = {
            "read_heavy": {
                "pool_size": 20,
                "max_overflow": 40,
                "pool_timeout": 60,
                "connect_args": {
                    **base_config["connect_args"],
                    "options": "-c default_transaction_isolation=repeatable_read"
                }
            },
            "write_heavy": {
                "pool_size": 10,
                "max_overflow": 15,
                "pool_timeout": 30,
                "connect_args": {
                    **base_config["connect_args"],
                    "options": "-c synchronous_commit=on"
                }
            },
            "mixed": {
                "pool_size": 15,
                "max_overflow": 25,
                "pool_timeout": 45
            },
            "batch": {
                "pool_size": 5,
                "max_overflow": 10,
                "pool_timeout": 300,  # 5 minutes
                "connect_args": {
                    **base_config["connect_args"],
                    "options": "-c statement_timeout=300000"  # 5 minutes
                }
            }
        }
        
        config = {**base_config, **workload_configs.get(workload_type, workload_configs["mixed"])}
        return config
    
    def _setup_engine_events(self, engine: sa.Engine) -> None:
        """Setup engine event listeners for monitoring and optimization."""
        
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            """Set SQLite pragmas for better performance."""
            if "sqlite" in str(engine.url):
                cursor = dbapi_connection.cursor()
                # Performance optimizations
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=10000")
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.execute("PRAGMA mmap_size=268435456")  # 256MB
                cursor.close()
        
        @event.listens_for(engine, "checkout")
        def receive_checkout(dbapi_connection, connection_record, connection_proxy):
            """Log connection checkout."""
            logger.debug(f"Connection checked out: {id(dbapi_connection)}")
        
        @event.listens_for(engine, "checkin")
        def receive_checkin(dbapi_connection, connection_record):
            """Log connection checkin."""
            logger.debug(f"Connection checked in: {id(dbapi_connection)}")
        
        @event.listens_for(engine, "invalidate")
        def receive_invalidate(dbapi_connection, connection_record, exception):
            """Log connection invalidation."""
            logger.warning(f"Connection invalidated: {exception}")
    
    async def initialize(self, 
                        primary_url: Optional[str] = None,
                        read_url: Optional[str] = None,
                        workload_type: str = "mixed") -> None:
        """
        Initialize database connections with optimized configuration.
        
        Args:
            primary_url: Primary database URL (default from settings)
            read_url: Read replica URL (optional, for read/write splitting)
            workload_type: Workload optimization type
        """
        async with self._lock:
            if self._initialized:
                logger.warning("Database already initialized")
                return
            
            try:
                # Use provided URL or get from settings
                db_url = primary_url or settings.database_url
                if not db_url:
                    raise ConfigurationError("Database URL not configured")
                
                # Create optimized pool configuration
                pool_config = self._create_optimized_pool_config(workload_type)
                
                # Parse URL for engine-specific optimizations
                parsed_url = urlparse(db_url)
                is_postgres = parsed_url.scheme.startswith('postgresql')
                is_sqlite = parsed_url.scheme.startswith('sqlite')
                
                # Engine-specific optimizations
                if is_postgres:
                    pool_config["connect_args"].update({
                        "options": "-c timezone=UTC -c statement_timeout=60000",
                        "server_settings": {
                            "jit": "off",  # Disable JIT for better predictability
                            "application_name": f"tmws_v2_{workload_type}"
                        }
                    })
                elif is_sqlite and not db_url.startswith("sqlite:///:memory:"):
                    # Use NullPool for SQLite file databases to avoid locking issues
                    pool_config["poolclass"] = NullPool
                
                # Create synchronous engine
                self._sync_engine = create_engine(db_url, **pool_config)
                self._setup_engine_events(self._sync_engine)
                
                # Create asynchronous engine
                async_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
                if is_sqlite:
                    async_url = db_url.replace("sqlite://", "sqlite+aiosqlite://")
                
                async_pool_config = {
                    k: v for k, v in pool_config.items() 
                    if k not in ["poolclass", "connect_args"]
                }
                
                self._async_engine = create_async_engine(
                    async_url,
                    **async_pool_config,
                    echo=settings.debug,
                    future=True
                )
                
                # Create session factories
                self._sync_session_factory = sessionmaker(
                    bind=self._sync_engine,
                    expire_on_commit=False,
                    autoflush=True,
                    autocommit=False
                )
                
                self._async_session_factory = async_sessionmaker(
                    bind=self._async_engine,
                    expire_on_commit=False,
                    autoflush=True,
                    autocommit=False
                )
                
                # Setup read replica if provided
                if read_url:
                    read_pool_config = self._create_optimized_pool_config("read_heavy")
                    self._read_engine = create_engine(read_url, **read_pool_config)
                    self._setup_engine_events(self._read_engine)
                
                # Store write engine reference
                self._write_engine = self._sync_engine
                
                logger.info(f"Database initialized with {workload_type} workload optimization")
                logger.info(f"Pool size: {pool_config.get('pool_size', 'N/A')}, Max overflow: {pool_config.get('max_overflow', 'N/A')}")
                
                self._initialized = True
                
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}")
                raise DatabaseError(f"Database initialization failed: {e}")
    
    @contextmanager
    def get_session(self, readonly: bool = False) -> Generator[Session, None, None]:
        """
        Get a synchronous database session.
        
        Args:
            readonly: Use read replica if available
        """
        if not self._initialized:
            raise DatabaseError("Database not initialized")
        
        engine = self._read_engine if readonly and self._read_engine else self._write_engine
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        session = session_factory()
        
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    @asynccontextmanager
    async def get_async_session(self, readonly: bool = False) -> AsyncGenerator[AsyncSession, None]:
        """
        Get an asynchronous database session.
        
        Args:
            readonly: Future support for async read replicas
        """
        if not self._async_session_factory:
            raise DatabaseError("Async database not initialized")
        
        async with self._async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Async database session error: {e}")
                raise
    
    def create_all_tables(self, metadata: MetaData) -> None:
        """Create all tables defined in metadata."""
        if not self._sync_engine:
            raise DatabaseError("Database not initialized")
        
        try:
            metadata.create_all(bind=self._sync_engine)
            logger.info("All tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise DatabaseError(f"Table creation failed: {e}")
    
    def drop_all_tables(self, metadata: MetaData) -> None:
        """Drop all tables defined in metadata."""
        if not self._sync_engine:
            raise DatabaseError("Database not initialized")
        
        try:
            metadata.drop_all(bind=self._sync_engine)
            logger.info("All tables dropped successfully")
        except Exception as e:
            logger.error(f"Failed to drop tables: {e}")
            raise DatabaseError(f"Table dropping failed: {e}")
    
    async def run_migrations(self, alembic_cfg_path: Optional[str] = None) -> None:
        """Run database migrations using Alembic."""
        if not self._sync_engine:
            raise DatabaseError("Database not initialized")
        
        try:
            alembic_cfg = Config(alembic_cfg_path or "alembic.ini")
            alembic_cfg.set_main_option("sqlalchemy.url", str(self._sync_engine.url))
            
            # Run migrations in a separate thread to avoid blocking
            await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: command.upgrade(alembic_cfg, "head")
            )
            
            logger.info("Database migrations completed successfully")
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise DatabaseError(f"Migration failed: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform database health check."""
        if not self._initialized:
            return {"status": "unhealthy", "error": "Database not initialized"}
        
        health_status = {
            "status": "healthy",
            "sync_engine_pool": None,
            "async_engine_pool": None,
            "read_engine_pool": None
        }
        
        try:
            # Check synchronous engine pool
            if self._sync_engine and hasattr(self._sync_engine.pool, 'size'):
                pool = self._sync_engine.pool
                health_status["sync_engine_pool"] = {
                    "size": pool.size(),
                    "checked_in": pool.checkedin(),
                    "checked_out": pool.checkedout(),
                    "overflow": pool.overflow(),
                    "invalid": pool.invalid()
                }
            
            # Check asynchronous engine
            if self._async_engine:
                health_status["async_engine_available"] = True
            
            # Check read engine pool
            if self._read_engine and hasattr(self._read_engine.pool, 'size'):
                pool = self._read_engine.pool
                health_status["read_engine_pool"] = {
                    "size": pool.size(),
                    "checked_in": pool.checkedin(),
                    "checked_out": pool.checkedout(),
                    "overflow": pool.overflow(),
                    "invalid": pool.invalid()
                }
            
            # Perform actual connectivity test
            with self.get_session() as session:
                result = session.execute(sa.text("SELECT 1")).scalar()
                if result != 1:
                    health_status["status"] = "unhealthy"
                    health_status["error"] = "Connectivity test failed"
            
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
            logger.error(f"Database health check failed: {e}")
        
        return health_status
    
    async def close(self) -> None:
        """Close all database connections."""
        async with self._lock:
            if self._sync_engine:
                self._sync_engine.dispose()
                self._sync_engine = None
            
            if self._async_engine:
                await self._async_engine.dispose()
                self._async_engine = None
            
            if self._read_engine:
                self._read_engine.dispose()
                self._read_engine = None
            
            if self._write_engine != self._sync_engine and self._write_engine:
                self._write_engine.dispose()
                self._write_engine = None
            
            self._sync_session_factory = None
            self._async_session_factory = None
            self._connection_pools.clear()
            self._initialized = False
            
            logger.info("Database connections closed")


# Global database manager instance
db_manager = DatabaseManager()


# Convenience functions for backward compatibility
def get_sync_session(readonly: bool = False):
    """Get a synchronous database session."""
    return db_manager.get_session(readonly=readonly)


def get_async_session(readonly: bool = False):
    """Get an asynchronous database session."""
    return db_manager.get_async_session(readonly=readonly)


async def init_database(primary_url: Optional[str] = None, 
                       read_url: Optional[str] = None,
                       workload_type: str = "mixed") -> None:
    """Initialize the database with optimized configuration."""
    await db_manager.initialize(primary_url, read_url, workload_type)


async def close_database() -> None:
    """Close database connections."""
    await db_manager.close()


# Database utilities
class DatabaseTransaction:
    """Context manager for database transactions with advanced features."""
    
    def __init__(self, session: Session, isolation_level: Optional[str] = None):
        self.session = session
        self.isolation_level = isolation_level
        self._savepoint = None
    
    def __enter__(self):
        if self.isolation_level:
            self.session.execute(sa.text(f"SET TRANSACTION ISOLATION LEVEL {self.isolation_level}"))
        self._savepoint = self.session.begin_nested()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self._savepoint.rollback()
            return False
        else:
            self._savepoint.commit()
            return True


class AsyncDatabaseTransaction:
    """Async context manager for database transactions."""
    
    def __init__(self, session: AsyncSession, isolation_level: Optional[str] = None):
        self.session = session
        self.isolation_level = isolation_level
        self._savepoint = None
    
    async def __aenter__(self):
        if self.isolation_level:
            await self.session.execute(sa.text(f"SET TRANSACTION ISOLATION LEVEL {self.isolation_level}"))
        self._savepoint = await self.session.begin_nested()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self._savepoint.rollback()
            return False
        else:
            await self._savepoint.commit()
            return True