"""
Database configuration and session management for TMWS.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import sqlalchemy as sa
from sqlalchemy import event, pool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

from .config import get_settings

logger = logging.getLogger(__name__)

# Base class for all database models
Base = declarative_base()

# Global variables for database engine and session maker
_engine: Optional[object] = None
_session_maker: Optional[async_sessionmaker] = None


def _setup_connection_events(engine) -> None:
    """Setup connection pool events for monitoring and security."""
    
    @event.listens_for(engine.sync_engine, "checkout")
    def receive_checkout(dbapi_connection, connection_record, connection_proxy):
        """Log connection checkout for monitoring."""
        logger.debug("Connection checked out from pool")
    
    @event.listens_for(engine.sync_engine, "checkin")
    def receive_checkin(dbapi_connection, connection_record):
        """Log connection checkin for monitoring."""
        logger.debug("Connection checked in to pool")


def get_engine():
    """Get database engine singleton."""
    global _engine
    
    if _engine is None:
        settings = get_settings()
        
        # Engine configuration with security and performance optimizations
        engine_config = {
            "echo": settings.db_echo_sql and not settings.is_production,
            "echo_pool": False,  # Disable pool logging in production
            "pool_recycle": settings.db_pool_recycle,
            "pool_pre_ping": settings.db_pool_pre_ping,
        }
        
        # Add connection arguments for PostgreSQL
        if settings.database_url_async.startswith("postgresql"):
            engine_config.update({
                "connect_args": {
                    "server_settings": {
                        "application_name": "tmws",
                        "jit": "off",  # Disable JIT for better connection times
                    },
                },
                "poolclass": pool.NullPool,  # Async engine requires NullPool
            })
        
        _engine = create_async_engine(settings.database_url_async, **engine_config)
        
        # Setup connection monitoring
        _setup_connection_events(_engine)
        
        logger.info(f"Database engine created for {settings.environment} environment")
    
    return _engine


def get_session_maker():
    """Get session maker singleton."""
    global _session_maker
    
    if _session_maker is None:
        engine = get_engine()
        _session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=True,
            autocommit=False,
        )
        logger.info("Database session maker created")
    
    return _session_maker


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session with automatic cleanup.
    
    Usage:
        async with get_db_session() as session:
            # Use session here
            pass
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


async def get_db_session_dependency() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database session.
    
    Usage in FastAPI routes:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db_session_dependency)):
            # Use db here
    """
    async with get_db_session() as session:
        yield session


class DatabaseHealthCheck:
    """Database health check utilities."""
    
    @staticmethod
    async def check_connection() -> bool:
        """Check if database connection is healthy."""
        try:
            async with get_db_session() as session:
                result = await session.execute(sa.text("SELECT 1"))
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    @staticmethod
    async def get_pool_status() -> dict:
        """Get connection pool status."""
        engine = get_engine()
        pool = engine.pool
        
        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.invalid(),
        }


async def create_tables():
    """Create all tables in the database."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")


async def drop_tables():
    """Drop all tables in the database."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.info("Database tables dropped")


async def close_db_connections():
    """Close all database connections."""
    global _engine, _session_maker
    
    if _engine:
        await _engine.dispose()
        _engine = None
        logger.info("Database engine disposed")
    
    if _session_maker:
        _session_maker = None
        logger.info("Session maker cleared")