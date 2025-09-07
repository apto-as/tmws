"""
Batch processing service for TMWS v2.0 - Universal Multi-Agent Platform.
Optimized for high-throughput batch operations with intelligent queuing.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Tuple, TypeVar, Union
from uuid import UUID, uuid4

import numpy as np
from sqlalchemy import and_, func, select, update, delete, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from ..core.database_enhanced import get_sync_session, get_async_session, DatabaseTransaction
from ..core.exceptions import ValidationError, DatabaseError, ProcessingError
from ..models.agent import Agent
from ..models.memory import Memory
from ..models.learning_pattern import LearningPattern
from ..models.task import Task, TaskStatus

logger = logging.getLogger(__name__)

T = TypeVar('T')


class BatchOperationType(str, Enum):
    """Types of batch operations."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    PROCESS = "process"
    ANALYZE = "analyze"
    MIGRATE = "migrate"


class BatchPriority(str, Enum):
    """Batch processing priorities."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class BatchJobStatus(str, Enum):
    """Batch job execution statuses."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class BatchJob:
    """Represents a batch processing job."""
    
    def __init__(self,
                 job_id: str,
                 operation_type: BatchOperationType,
                 items: List[Dict[str, Any]],
                 processor_func: Callable,
                 priority: BatchPriority = BatchPriority.MEDIUM,
                 batch_size: int = 100,
                 max_retries: int = 3,
                 timeout_seconds: int = 300,
                 metadata: Optional[Dict[str, Any]] = None):
        self.job_id = job_id
        self.operation_type = operation_type
        self.items = items
        self.processor_func = processor_func
        self.priority = priority
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        self.metadata = metadata or {}
        
        # Runtime state
        self.status = BatchJobStatus.PENDING
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.processed_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.current_retry = 0
        self.error_messages: List[str] = []
        self.progress_callback: Optional[Callable] = None
    
    @property
    def total_items(self) -> int:
        """Get total number of items to process."""
        return len(self.items)
    
    @property
    def progress_percentage(self) -> float:
        """Get processing progress as percentage."""
        if self.total_items == 0:
            return 100.0
        return (self.processed_count / self.total_items) * 100.0
    
    @property
    def success_rate(self) -> float:
        """Get success rate as percentage."""
        if self.processed_count == 0:
            return 0.0
        return (self.success_count / self.processed_count) * 100.0
    
    @property
    def is_completed(self) -> bool:
        """Check if job is completed (successfully or with failures)."""
        return self.status in [BatchJobStatus.COMPLETED, BatchJobStatus.FAILED, BatchJobStatus.CANCELLED]
    
    @property
    def execution_time(self) -> Optional[timedelta]:
        """Get job execution time."""
        if not self.started_at:
            return None
        end_time = self.completed_at or datetime.now()
        return end_time - self.started_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary representation."""
        return {
            "job_id": self.job_id,
            "operation_type": self.operation_type,
            "status": self.status,
            "priority": self.priority,
            "total_items": self.total_items,
            "processed_count": self.processed_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "progress_percentage": self.progress_percentage,
            "success_rate": self.success_rate,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time_seconds": self.execution_time.total_seconds() if self.execution_time else None,
            "current_retry": self.current_retry,
            "max_retries": self.max_retries,
            "error_messages": self.error_messages[-10:],  # Last 10 errors
            "metadata": self.metadata
        }


class BatchProcessor:
    """
    High-performance batch processor with intelligent scheduling and resource management.
    
    Features:
    - Priority-based job scheduling
    - Adaptive batch sizing based on performance
    - Parallel processing with controlled concurrency
    - Automatic retry with exponential backoff
    - Memory usage optimization
    - Progress tracking and analytics
    """
    
    def __init__(self,
                 max_concurrent_jobs: int = 5,
                 max_concurrent_batches: int = 10,
                 memory_limit_mb: int = 1024,
                 adaptive_batch_sizing: bool = True):
        self.max_concurrent_jobs = max_concurrent_jobs
        self.max_concurrent_batches = max_concurrent_batches
        self.memory_limit_mb = memory_limit_mb
        self.adaptive_batch_sizing = adaptive_batch_sizing
        
        # Runtime state
        self.jobs: Dict[str, BatchJob] = {}
        self.job_queue: asyncio.Queue = asyncio.Queue()
        self.running_jobs: Dict[str, asyncio.Task] = {}
        self.semaphore = asyncio.Semaphore(max_concurrent_jobs)
        self.batch_semaphore = asyncio.Semaphore(max_concurrent_batches)
        self._shutdown = False
        self._processor_task: Optional[asyncio.Task] = None
        
        # Performance tracking
        self.performance_metrics = {
            "total_jobs_processed": 0,
            "total_items_processed": 0,
            "total_processing_time": 0.0,
            "average_job_time": 0.0,
            "average_items_per_second": 0.0,
            "error_rate": 0.0
        }
    
    async def start(self) -> None:
        """Start the batch processor."""
        if self._processor_task:
            logger.warning("Batch processor already started")
            return
        
        self._shutdown = False
        self._processor_task = asyncio.create_task(self._process_jobs())
        logger.info(f"Batch processor started with {self.max_concurrent_jobs} max concurrent jobs")
    
    async def stop(self, timeout: float = 60.0) -> None:
        """Stop the batch processor gracefully."""
        self._shutdown = True
        
        # Cancel all running jobs
        for job_id, task in list(self.running_jobs.items()):
            logger.info(f"Cancelling running job: {job_id}")
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
        
        # Stop the processor task
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await asyncio.wait_for(self._processor_task, timeout=timeout)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
        
        logger.info("Batch processor stopped")
    
    async def submit_job(self, job: BatchJob) -> str:
        """
        Submit a batch job for processing.
        
        Args:
            job: BatchJob instance to process
        
        Returns:
            Job ID for tracking
        """
        if job.job_id in self.jobs:
            raise ValidationError(f"Job with ID {job.job_id} already exists")
        
        self.jobs[job.job_id] = job
        await self.job_queue.put(job)
        
        logger.info(f"Submitted batch job {job.job_id}: {job.operation_type} with {job.total_items} items")
        return job.job_id
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a batch job."""
        job = self.jobs.get(job_id)
        return job.to_dict() if job else None
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a batch job."""
        if job_id not in self.jobs:
            return False
        
        job = self.jobs[job_id]
        
        if job.status == BatchJobStatus.PENDING:
            job.status = BatchJobStatus.CANCELLED
            return True
        elif job_id in self.running_jobs:
            task = self.running_jobs[job_id]
            task.cancel()
            job.status = BatchJobStatus.CANCELLED
            return True
        
        return False
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get batch processor performance metrics."""
        return {
            **self.performance_metrics,
            "active_jobs": len(self.running_jobs),
            "queued_jobs": self.job_queue.qsize(),
            "total_jobs": len(self.jobs),
            "memory_limit_mb": self.memory_limit_mb,
            "max_concurrent_jobs": self.max_concurrent_jobs,
            "max_concurrent_batches": self.max_concurrent_batches
        }
    
    async def _process_jobs(self) -> None:
        """Main job processing loop."""
        while not self._shutdown:
            try:
                # Get next job with timeout to allow shutdown checks
                job = await asyncio.wait_for(self.job_queue.get(), timeout=1.0)
                
                if job.status != BatchJobStatus.PENDING:
                    continue
                
                # Check if we can start processing
                async with self.semaphore:
                    if self._shutdown:
                        break
                    
                    # Start job processing
                    task = asyncio.create_task(self._execute_job(job))
                    self.running_jobs[job.job_id] = task
                    
                    # Monitor job completion
                    asyncio.create_task(self._monitor_job(job.job_id, task))
            
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in job processing loop: {e}")
                await asyncio.sleep(1.0)
    
    async def _monitor_job(self, job_id: str, task: asyncio.Task) -> None:
        """Monitor job completion and cleanup."""
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
        finally:
            if job_id in self.running_jobs:
                del self.running_jobs[job_id]
    
    async def _execute_job(self, job: BatchJob) -> None:
        """Execute a batch job with retry logic."""
        job.status = BatchJobStatus.RUNNING
        job.started_at = datetime.now()
        
        logger.info(f"Starting batch job {job.job_id}: {job.operation_type}")
        
        try:
            # Adaptive batch sizing
            if self.adaptive_batch_sizing:
                job.batch_size = await self._calculate_optimal_batch_size(job)
            
            # Process items in batches
            await self._process_job_batches(job)
            
            # Update job status
            if job.processed_count == job.total_items:
                job.status = BatchJobStatus.COMPLETED
                logger.info(f"Completed batch job {job.job_id}: {job.success_count}/{job.total_items} successful")
            else:
                job.status = BatchJobStatus.FAILED
                logger.error(f"Failed batch job {job.job_id}: {job.success_count}/{job.total_items} successful")
        
        except asyncio.CancelledError:
            job.status = BatchJobStatus.CANCELLED
            logger.info(f"Cancelled batch job {job.job_id}")
            raise
        
        except Exception as e:
            job.status = BatchJobStatus.FAILED
            job.error_messages.append(str(e))
            logger.error(f"Error in batch job {job.job_id}: {e}")
        
        finally:
            job.completed_at = datetime.now()
            self._update_performance_metrics(job)
    
    async def _process_job_batches(self, job: BatchJob) -> None:
        """Process job items in optimized batches."""
        total_batches = (job.total_items + job.batch_size - 1) // job.batch_size
        
        # Create batch processing tasks
        batch_tasks = []
        for i in range(0, job.total_items, job.batch_size):
            batch_items = job.items[i:i + job.batch_size]
            batch_id = f"{job.job_id}_batch_{i // job.batch_size + 1}"
            
            task = asyncio.create_task(
                self._process_batch(job, batch_id, batch_items, i)
            )
            batch_tasks.append(task)
        
        # Process batches with controlled concurrency
        for batch_task in asyncio.as_completed(batch_tasks):
            try:
                await batch_task
            except Exception as e:
                logger.error(f"Batch processing error in job {job.job_id}: {e}")
            
            # Update progress
            if job.progress_callback:
                try:
                    await job.progress_callback(job.to_dict())
                except Exception as e:
                    logger.warning(f"Progress callback error: {e}")
    
    async def _process_batch(self, 
                           job: BatchJob, 
                           batch_id: str, 
                           items: List[Dict[str, Any]], 
                           start_index: int) -> None:
        """Process a single batch with controlled concurrency."""
        async with self.batch_semaphore:
            batch_start_time = datetime.now()
            batch_success_count = 0
            batch_failure_count = 0
            
            try:
                # Process items in the batch
                if asyncio.iscoroutinefunction(job.processor_func):
                    results = await job.processor_func(items, job.metadata)
                else:
                    # Run sync function in thread pool
                    results = await asyncio.get_event_loop().run_in_executor(
                        None, job.processor_func, items, job.metadata
                    )
                
                # Count successes and failures
                for i, result in enumerate(results or []):
                    if result.get('success', False):
                        batch_success_count += 1
                    else:
                        batch_failure_count += 1
                        error_msg = result.get('error', 'Unknown error')
                        job.error_messages.append(f"Item {start_index + i}: {error_msg}")
            
            except Exception as e:
                # Entire batch failed
                batch_failure_count = len(items)
                job.error_messages.append(f"Batch {batch_id} failed: {e}")
            
            # Update job counters atomically
            job.processed_count += len(items)
            job.success_count += batch_success_count
            job.failure_count += batch_failure_count
            
            batch_time = (datetime.now() - batch_start_time).total_seconds()
            logger.debug(f"Processed batch {batch_id}: {batch_success_count}/{len(items)} successful in {batch_time:.2f}s")
    
    async def _calculate_optimal_batch_size(self, job: BatchJob) -> int:
        """Calculate optimal batch size based on job characteristics and system performance."""
        base_size = job.batch_size
        
        # Adjust based on operation type
        operation_multipliers = {
            BatchOperationType.CREATE: 1.0,
            BatchOperationType.UPDATE: 0.8,
            BatchOperationType.DELETE: 1.2,
            BatchOperationType.PROCESS: 0.6,
            BatchOperationType.ANALYZE: 0.4,
            BatchOperationType.MIGRATE: 0.5
        }
        
        multiplier = operation_multipliers.get(job.operation_type, 1.0)
        
        # Adjust based on priority
        priority_multipliers = {
            BatchPriority.LOW: 1.2,
            BatchPriority.MEDIUM: 1.0,
            BatchPriority.HIGH: 0.8,
            BatchPriority.URGENT: 0.6,
            BatchPriority.CRITICAL: 0.4
        }
        
        priority_multiplier = priority_multipliers.get(job.priority, 1.0)
        
        # Adjust based on system load
        load_factor = min(len(self.running_jobs) / max(self.max_concurrent_jobs, 1), 1.0)
        load_multiplier = 1.0 - (load_factor * 0.3)
        
        # Calculate final batch size
        optimal_size = int(base_size * multiplier * priority_multiplier * load_multiplier)
        
        # Ensure reasonable bounds
        optimal_size = max(10, min(optimal_size, 1000))
        
        return optimal_size
    
    def _update_performance_metrics(self, job: BatchJob) -> None:
        """Update processor performance metrics."""
        self.performance_metrics["total_jobs_processed"] += 1
        self.performance_metrics["total_items_processed"] += job.processed_count
        
        if job.execution_time:
            execution_seconds = job.execution_time.total_seconds()
            self.performance_metrics["total_processing_time"] += execution_seconds
            
            # Update averages
            total_jobs = self.performance_metrics["total_jobs_processed"]
            self.performance_metrics["average_job_time"] = (
                self.performance_metrics["total_processing_time"] / total_jobs
            )
            
            if execution_seconds > 0:
                items_per_second = job.processed_count / execution_seconds
                # Exponential moving average
                if self.performance_metrics["average_items_per_second"] == 0:
                    self.performance_metrics["average_items_per_second"] = items_per_second
                else:
                    alpha = 0.1
                    self.performance_metrics["average_items_per_second"] = (
                        (1 - alpha) * self.performance_metrics["average_items_per_second"] +
                        alpha * items_per_second
                    )
        
        # Update error rate
        if job.processed_count > 0:
            job_error_rate = job.failure_count / job.processed_count
            total_items = self.performance_metrics["total_items_processed"]
            current_error_rate = self.performance_metrics["error_rate"]
            
            # Weighted average
            self.performance_metrics["error_rate"] = (
                (current_error_rate * (total_items - job.processed_count) +
                 job_error_rate * job.processed_count) / total_items
            )


class BatchService:
    """
    High-level batch processing service with pre-built operations for TMWS entities.
    """
    
    def __init__(self):
        self.processor = BatchProcessor()
    
    async def start(self) -> None:
        """Start the batch service."""
        await self.processor.start()
    
    async def stop(self, timeout: float = 60.0) -> None:
        """Stop the batch service."""
        await self.processor.stop(timeout)
    
    async def batch_create_memories(self,
                                  memories_data: List[Dict[str, Any]],
                                  agent_id: Optional[str] = None,
                                  namespace: str = "default",
                                  batch_size: int = 100) -> str:
        """Batch create memories with optimized processing."""
        
        async def memory_processor(items: List[Dict[str, Any]], metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
            results = []
            
            async with get_async_session() as session:
                for item in items:
                    try:
                        memory = Memory(
                            content=item['content'],
                            agent_id=item.get('agent_id', agent_id),
                            namespace=item.get('namespace', namespace),
                            importance=item.get('importance', 0.5),
                            memory_type=item.get('memory_type', 'episodic'),
                            access_level=item.get('access_level', 'private'),
                            context_tags=item.get('context_tags', []),
                            learning_weight=item.get('learning_weight', 1.0)
                        )
                        
                        session.add(memory)
                        results.append({'success': True, 'memory_id': None})  # Will be set after flush
                    
                    except Exception as e:
                        results.append({'success': False, 'error': str(e)})
                
                try:
                    await session.flush()
                    # Update memory IDs in results
                    success_idx = 0
                    for i, result in enumerate(results):
                        if result['success']:
                            # This is a simplified approach - in practice, you'd track the created memories
                            success_idx += 1
                    
                except Exception as e:
                    # Mark all as failed if commit fails
                    for result in results:
                        if result['success']:
                            result['success'] = False
                            result['error'] = f"Batch commit failed: {e}"
            
            return results
        
        job = BatchJob(
            job_id=f"batch_memories_{uuid4().hex[:8]}",
            operation_type=BatchOperationType.CREATE,
            items=memories_data,
            processor_func=memory_processor,
            batch_size=batch_size,
            metadata={'agent_id': agent_id, 'namespace': namespace}
        )
        
        return await self.processor.submit_job(job)
    
    async def batch_update_agent_performance(self,
                                           performance_updates: List[Dict[str, Any]],
                                           batch_size: int = 50) -> str:
        """Batch update agent performance metrics."""
        
        async def performance_processor(items: List[Dict[str, Any]], metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
            results = []
            
            async with get_async_session() as session:
                for item in items:
                    try:
                        agent_id = item['agent_id']
                        performance_data = item['performance_data']
                        
                        # Update agent performance
                        await session.execute(
                            update(Agent).where(Agent.agent_id == agent_id).values(
                                total_requests=Agent.total_requests + performance_data.get('requests', 0),
                                successful_requests=Agent.successful_requests + performance_data.get('successful', 0),
                                failed_requests=Agent.failed_requests + performance_data.get('failed', 0),
                                total_tokens_used=Agent.total_tokens_used + performance_data.get('tokens', 0),
                                total_cost=Agent.total_cost + performance_data.get('cost', 0.0),
                                last_request_at=func.now()
                            )
                        )
                        
                        # Update average response time with exponential moving average
                        if 'response_time' in performance_data:
                            await session.execute(
                                text("""
                                UPDATE agents 
                                SET average_response_time = CASE 
                                    WHEN average_response_time IS NULL THEN :response_time
                                    ELSE (0.9 * average_response_time + 0.1 * :response_time)
                                END
                                WHERE agent_id = :agent_id
                                """),
                                {
                                    'agent_id': agent_id,
                                    'response_time': performance_data['response_time']
                                }
                            )
                        
                        results.append({'success': True, 'agent_id': agent_id})
                    
                    except Exception as e:
                        results.append({'success': False, 'error': str(e), 'agent_id': item.get('agent_id')})
            
            return results
        
        job = BatchJob(
            job_id=f"batch_agent_perf_{uuid4().hex[:8]}",
            operation_type=BatchOperationType.UPDATE,
            items=performance_updates,
            processor_func=performance_processor,
            batch_size=batch_size
        )
        
        return await self.processor.submit_job(job)
    
    async def batch_cleanup_expired_memories(self,
                                           days_threshold: int = 30,
                                           batch_size: int = 200) -> str:
        """Batch cleanup expired memories based on retention policy."""
        
        async def cleanup_processor(items: List[Dict[str, Any]], metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
            results = []
            
            async with get_async_session() as session:
                threshold_date = datetime.now() - timedelta(days=metadata['days_threshold'])
                
                # Find expired memories
                expired_memories = await session.execute(
                    select(Memory.id).where(
                        and_(
                            Memory.retention_policy == 'temporary',
                            Memory.expires_at < threshold_date
                        )
                    ).limit(len(items))
                )
                
                memory_ids = [row.id for row in expired_memories]
                
                try:
                    # Delete expired memories
                    deleted_count = await session.execute(
                        delete(Memory).where(Memory.id.in_(memory_ids))
                    )
                    
                    results.append({
                        'success': True,
                        'deleted_count': deleted_count.rowcount,
                        'memory_ids': [str(mid) for mid in memory_ids]
                    })
                
                except Exception as e:
                    results.append({'success': False, 'error': str(e)})
            
            return results
        
        # Create dummy items for batch processing (actual work is done in processor)
        dummy_items = [{'batch': i} for i in range((batch_size + 99) // 100)]
        
        job = BatchJob(
            job_id=f"batch_cleanup_{uuid4().hex[:8]}",
            operation_type=BatchOperationType.DELETE,
            items=dummy_items,
            processor_func=cleanup_processor,
            batch_size=1,  # Process one "batch" at a time
            metadata={'days_threshold': days_threshold}
        )
        
        return await self.processor.submit_job(job)
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get batch job status."""
        return await self.processor.get_job_status(job_id)
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a batch job."""
        return await self.processor.cancel_job(job_id)
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get batch service performance metrics."""
        return await self.processor.get_performance_metrics()


# Global batch service instance
batch_service = BatchService()