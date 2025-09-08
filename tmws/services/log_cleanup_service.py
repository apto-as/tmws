"""
Log Cleanup Service for TMWS
Comprehensive log management with database-based storage and cleanup
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum

from sqlalchemy import Column, String, DateTime, JSON, Integer, Text, Index, delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base

logger = logging.getLogger(__name__)

Base = declarative_base()


class LogLevel(Enum):
    """Log levels for system logs."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class SystemLog(Base):
    """Database model for system logs."""
    __tablename__ = "system_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    level = Column(String(20), nullable=False, index=True)
    component = Column(String(100), index=True)  # Which component generated the log
    message = Column(Text, nullable=False)
    context = Column(JSON)  # Additional context data
    
    # Performance optimization indexes
    __table_args__ = (
        Index("idx_logs_timestamp_level", "timestamp", "level"),
        Index("idx_logs_component_timestamp", "component", "timestamp"),
    )


class LogCleanupService:
    """
    Service for managing log cleanup and retention.
    Implements configurable retention policies and automated cleanup.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        
        # Default retention policies (days)
        self.retention_policies = {
            LogLevel.DEBUG: 7,      # Keep debug logs for 7 days
            LogLevel.INFO: 30,      # Keep info logs for 30 days
            LogLevel.WARNING: 90,   # Keep warnings for 90 days
            LogLevel.ERROR: 180,    # Keep errors for 180 days
            LogLevel.CRITICAL: 365  # Keep critical logs for 1 year
        }
        
        # Cleanup configuration
        self.batch_size = 1000  # Delete in batches to avoid locking
        self.cleanup_interval_hours = 24  # Run cleanup daily
        self.last_cleanup: Optional[datetime] = None
    
    async def log_event(
        self,
        level: LogLevel,
        message: str,
        component: str = None,
        context: Dict[str, Any] = None
    ) -> SystemLog:
        """
        Log an event to the database.
        
        Args:
            level: Log level
            message: Log message
            component: Component that generated the log
            context: Additional context data
            
        Returns:
            Created log entry
        """
        
        log_entry = SystemLog(
            timestamp=datetime.utcnow(),
            level=level.value,
            component=component or "system",
            message=message,
            context=context or {}
        )
        
        self.session.add(log_entry)
        await self.session.commit()
        await self.session.refresh(log_entry)
        
        return log_entry
    
    async def cleanup_old_logs(
        self,
        force: bool = False,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Clean up old logs based on retention policies.
        
        Args:
            force: Force cleanup even if recently run
            dry_run: Only simulate cleanup without deleting
            
        Returns:
            Cleanup results with statistics
        """
        
        # Check if cleanup is needed
        if not force and self.last_cleanup:
            hours_since_cleanup = (datetime.utcnow() - self.last_cleanup).total_seconds() / 3600
            if hours_since_cleanup < self.cleanup_interval_hours:
                return {
                    "status": "skipped",
                    "reason": f"Cleanup ran {hours_since_cleanup:.1f} hours ago",
                    "next_cleanup": (
                        self.last_cleanup + timedelta(hours=self.cleanup_interval_hours)
                    ).isoformat()
                }
        
        cleanup_stats = {
            "started_at": datetime.utcnow().isoformat(),
            "dry_run": dry_run,
            "deleted_by_level": {},
            "total_deleted": 0,
            "errors": []
        }
        
        try:
            # Process each log level
            for level, retention_days in self.retention_policies.items():
                cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
                
                # Count logs to delete
                count_stmt = select(func.count()).select_from(SystemLog).where(
                    SystemLog.level == level.value,
                    SystemLog.timestamp < cutoff_date
                )
                result = await self.session.execute(count_stmt)
                count_to_delete = result.scalar()
                
                if count_to_delete == 0:
                    cleanup_stats["deleted_by_level"][level.value] = {
                        "count": 0,
                        "cutoff_date": cutoff_date.isoformat()
                    }
                    continue
                
                deleted_count = 0
                
                if not dry_run:
                    # Delete in batches to avoid locking
                    while deleted_count < count_to_delete:
                        # Get batch of IDs to delete
                        batch_stmt = select(SystemLog.id).where(
                            SystemLog.level == level.value,
                            SystemLog.timestamp < cutoff_date
                        ).limit(self.batch_size)
                        
                        batch_result = await self.session.execute(batch_stmt)
                        log_ids = [row[0] for row in batch_result]
                        
                        if not log_ids:
                            break
                        
                        # Delete batch
                        delete_stmt = delete(SystemLog).where(SystemLog.id.in_(log_ids))
                        await self.session.execute(delete_stmt)
                        await self.session.commit()
                        
                        deleted_count += len(log_ids)
                        
                        # Small delay to reduce database load
                        await asyncio.sleep(0.1)
                
                cleanup_stats["deleted_by_level"][level.value] = {
                    "count": deleted_count if not dry_run else count_to_delete,
                    "cutoff_date": cutoff_date.isoformat(),
                    "retention_days": retention_days
                }
                cleanup_stats["total_deleted"] += deleted_count if not dry_run else count_to_delete
                
        except Exception as e:
            logger.error(f"Log cleanup failed: {e}")
            cleanup_stats["errors"].append(str(e))
        
        # Update last cleanup time
        if not dry_run and not cleanup_stats["errors"]:
            self.last_cleanup = datetime.utcnow()
        
        cleanup_stats["completed_at"] = datetime.utcnow().isoformat()
        cleanup_stats["status"] = "completed" if not cleanup_stats["errors"] else "partial"
        
        return cleanup_stats
    
    async def get_log_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about stored logs.
        
        Returns:
            Log statistics by level and time range
        """
        
        stats = {
            "total_logs": 0,
            "by_level": {},
            "by_component": {},
            "oldest_log": None,
            "newest_log": None,
            "storage_info": {}
        }
        
        # Total count
        total_stmt = select(func.count()).select_from(SystemLog)
        total_result = await self.session.execute(total_stmt)
        stats["total_logs"] = total_result.scalar()
        
        # Count by level
        level_stmt = select(
            SystemLog.level,
            func.count()
        ).group_by(SystemLog.level)
        
        level_result = await self.session.execute(level_stmt)
        for level, count in level_result:
            stats["by_level"][level] = count
        
        # Count by component (top 10)
        component_stmt = select(
            SystemLog.component,
            func.count()
        ).group_by(SystemLog.component).order_by(func.count().desc()).limit(10)
        
        component_result = await self.session.execute(component_stmt)
        for component, count in component_result:
            stats["by_component"][component] = count
        
        # Get date range
        if stats["total_logs"] > 0:
            oldest_stmt = select(func.min(SystemLog.timestamp))
            oldest_result = await self.session.execute(oldest_stmt)
            oldest = oldest_result.scalar()
            if oldest:
                stats["oldest_log"] = oldest.isoformat()
            
            newest_stmt = select(func.max(SystemLog.timestamp))
            newest_result = await self.session.execute(newest_stmt)
            newest = newest_result.scalar()
            if newest:
                stats["newest_log"] = newest.isoformat()
        
        # Estimate storage size (simplified)
        # In production, use pg_relation_size or similar
        avg_log_size = 500  # bytes (estimated)
        stats["storage_info"] = {
            "estimated_size_mb": (stats["total_logs"] * avg_log_size) / (1024 * 1024),
            "retention_policies": {
                level.value: days for level, days in self.retention_policies.items()
            }
        }
        
        return stats
    
    async def search_logs(
        self,
        level: Optional[LogLevel] = None,
        component: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        search_text: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search logs with filters.
        
        Args:
            level: Filter by log level
            component: Filter by component
            start_date: Start date filter
            end_date: End date filter
            search_text: Text search in message
            limit: Maximum results
            
        Returns:
            List of matching log entries
        """
        
        query = select(SystemLog)
        
        # Apply filters
        filters = []
        if level:
            filters.append(SystemLog.level == level.value)
        if component:
            filters.append(SystemLog.component == component)
        if start_date:
            filters.append(SystemLog.timestamp >= start_date)
        if end_date:
            filters.append(SystemLog.timestamp <= end_date)
        if search_text:
            filters.append(SystemLog.message.contains(search_text))
        
        if filters:
            query = query.where(*filters)
        
        # Order by newest first and limit
        query = query.order_by(SystemLog.timestamp.desc()).limit(limit)
        
        result = await self.session.execute(query)
        logs = result.scalars().all()
        
        return [
            {
                "id": log.id,
                "timestamp": log.timestamp.isoformat(),
                "level": log.level,
                "component": log.component,
                "message": log.message,
                "context": log.context
            }
            for log in logs
        ]
    
    async def archive_old_logs(
        self,
        archive_days: int = 90,
        archive_path: str = "/archive/logs"
    ) -> Dict[str, Any]:
        """
        Archive old logs to external storage before deletion.
        
        Args:
            archive_days: Archive logs older than this many days
            archive_path: Path to archive location
            
        Returns:
            Archive operation results
        """
        
        # This is a placeholder for actual archive implementation
        # In production, this would export to S3, filesystem, or other storage
        
        archive_date = datetime.utcnow() - timedelta(days=archive_days)
        
        # Count logs to archive
        count_stmt = select(func.count()).select_from(SystemLog).where(
            SystemLog.timestamp < archive_date
        )
        result = await self.session.execute(count_stmt)
        count_to_archive = result.scalar()
        
        return {
            "status": "not_implemented",
            "message": "Archive functionality requires external storage configuration",
            "logs_to_archive": count_to_archive,
            "archive_date": archive_date.isoformat(),
            "archive_path": archive_path
        }
    
    def update_retention_policy(
        self,
        level: LogLevel,
        retention_days: int
    ) -> None:
        """
        Update retention policy for a log level.
        
        Args:
            level: Log level to update
            retention_days: New retention period in days
        """
        
        if retention_days < 1:
            raise ValueError("Retention days must be at least 1")
        
        old_retention = self.retention_policies.get(level)
        self.retention_policies[level] = retention_days
        
        logger.info(
            f"Updated retention policy for {level.value}: "
            f"{old_retention} -> {retention_days} days"
        )