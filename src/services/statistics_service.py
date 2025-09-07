"""
Statistics Collection Service for TMWS v2.0
Comprehensive metrics and analytics for agent activities.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.sql import text

from ..models.agent import Agent
from ..models.memory import Memory, MemoryPattern
from ..core.database import get_session
import logging

logger = logging.getLogger(__name__)


class StatisticsService:
    """Service for collecting and analyzing agent statistics."""
    
    def __init__(self, session: AsyncSession = None):
        self.session = session
        self.cache: Dict[str, Any] = {}
        self.cache_ttl = 300  # 5 minutes
        
    async def initialize(self, session: AsyncSession = None):
        """Initialize the service."""
        self.session = session or await get_session()
    
    async def collect_agent_metrics(self, agent_id: str) -> Dict[str, Any]:
        """
        Collect comprehensive metrics for an agent.
        
        Returns detailed statistics including:
        - Memory statistics
        - Access patterns
        - Performance metrics
        - Learning insights
        """
        
        try:
            # Get agent
            result = await self.session.execute(
                select(Agent).where(Agent.agent_id == agent_id)
            )
            agent = result.scalar_one_or_none()
            
            if not agent:
                return {"error": "Agent not found"}
            
            # Collect various metrics
            metrics = {
                "agent_id": agent_id,
                "display_name": agent.display_name,
                "basic_stats": await self._get_basic_stats(agent),
                "memory_stats": await self._get_memory_stats(agent_id),
                "access_patterns": await self._get_access_patterns(agent_id),
                "performance_metrics": await self._get_performance_metrics(agent),
                "learning_stats": await self._get_learning_stats(agent_id),
                "time_series": await self._get_time_series_data(agent_id),
                "collaboration_stats": await self._get_collaboration_stats(agent_id),
                "collected_at": datetime.utcnow().isoformat()
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting metrics for {agent_id}: {e}")
            return {"error": str(e)}
    
    async def _get_basic_stats(self, agent: Agent) -> Dict[str, Any]:
        """Get basic agent statistics."""
        
        return {
            "status": agent.status.value,
            "health_score": agent.health_score,
            "total_memories": agent.total_memories,
            "total_tasks": agent.total_tasks,
            "success_rate": agent.success_rate,
            "average_response_time_ms": agent.average_response_time_ms,
            "created_at": agent.created_at.isoformat() if agent.created_at else None,
            "last_active_at": agent.last_active_at.isoformat() if agent.last_active_at else None,
            "uptime_hours": self._calculate_uptime(agent.created_at, agent.last_active_at)
        }
    
    async def _get_memory_stats(self, agent_id: str) -> Dict[str, Any]:
        """Get memory-related statistics."""
        
        # Total memories
        total_result = await self.session.execute(
            select(func.count(Memory.id)).where(Memory.agent_id == agent_id)
        )
        total_memories = total_result.scalar() or 0
        
        # Average memory length
        avg_length_result = await self.session.execute(
            select(func.avg(func.length(Memory.content))).where(Memory.agent_id == agent_id)
        )
        avg_length = avg_length_result.scalar() or 0
        
        # Memory by access level
        access_level_result = await self.session.execute(
            select(Memory.access_level, func.count(Memory.id))
            .where(Memory.agent_id == agent_id)
            .group_by(Memory.access_level)
        )
        access_levels = {str(level): count for level, count in access_level_result}
        
        # Most used tags
        tag_query = text("""
            SELECT tag, COUNT(*) as count
            FROM (
                SELECT jsonb_array_elements_text(tags) as tag
                FROM memories_v2
                WHERE agent_id = :agent_id
            ) t
            GROUP BY tag
            ORDER BY count DESC
            LIMIT 10
        """)
        
        tag_result = await self.session.execute(tag_query, {"agent_id": agent_id})
        top_tags = [{"tag": row[0], "count": row[1]} for row in tag_result]
        
        # Memory importance distribution
        importance_result = await self.session.execute(
            select(
                func.case(
                    (Memory.importance_score < 0.33, 'low'),
                    (Memory.importance_score < 0.67, 'medium'),
                    else_='high'
                ).label('importance_level'),
                func.count(Memory.id)
            )
            .where(Memory.agent_id == agent_id)
            .group_by('importance_level')
        )
        importance_dist = {level: count for level, count in importance_result}
        
        return {
            "total_memories": total_memories,
            "average_memory_length": float(avg_length) if avg_length else 0,
            "access_level_distribution": access_levels,
            "top_tags": top_tags,
            "importance_distribution": importance_dist,
            "shared_memory_count": await self._count_shared_memories(agent_id),
            "consolidated_memory_count": await self._count_consolidated_memories(agent_id)
        }
    
    async def _get_access_patterns(self, agent_id: str) -> Dict[str, Any]:
        """Analyze memory access patterns."""
        
        # Most accessed memories
        most_accessed = await self.session.execute(
            select(Memory.id, Memory.content[:100], Memory.access_count)
            .where(Memory.agent_id == agent_id)
            .order_by(Memory.access_count.desc())
            .limit(5)
        )
        
        top_accessed = [
            {
                "id": str(mem_id),
                "preview": content,
                "access_count": count
            }
            for mem_id, content, count in most_accessed
        ]
        
        # Access time distribution (hourly)
        hourly_query = text("""
            SELECT EXTRACT(HOUR FROM accessed_at) as hour, COUNT(*) as count
            FROM memories_v2
            WHERE agent_id = :agent_id AND accessed_at IS NOT NULL
            GROUP BY hour
            ORDER BY hour
        """)
        
        hourly_result = await self.session.execute(hourly_query, {"agent_id": agent_id})
        hourly_distribution = {int(hour): count for hour, count in hourly_result}
        
        # Recent access activity
        recent_cutoff = datetime.utcnow() - timedelta(days=7)
        recent_result = await self.session.execute(
            select(func.count(Memory.id))
            .where(and_(
                Memory.agent_id == agent_id,
                Memory.accessed_at >= recent_cutoff
            ))
        )
        recent_accesses = recent_result.scalar() or 0
        
        return {
            "top_accessed_memories": top_accessed,
            "hourly_access_distribution": hourly_distribution,
            "recent_accesses_7d": recent_accesses,
            "peak_access_hours": self._find_peak_hours(hourly_distribution)
        }
    
    async def _get_performance_metrics(self, agent: Agent) -> Dict[str, Any]:
        """Get performance-related metrics."""
        
        return {
            "average_response_time_ms": agent.average_response_time_ms,
            "success_rate": agent.success_rate,
            "health_score": agent.health_score,
            "reliability_score": self._calculate_reliability(agent),
            "efficiency_score": self._calculate_efficiency(agent)
        }
    
    async def _get_learning_stats(self, agent_id: str) -> Dict[str, Any]:
        """Get learning and pattern statistics."""
        
        # Pattern count
        pattern_result = await self.session.execute(
            select(func.count(MemoryPattern.id))
            .where(MemoryPattern.agent_id == agent_id)
        )
        total_patterns = pattern_result.scalar() or 0
        
        # Pattern type distribution
        pattern_type_result = await self.session.execute(
            select(MemoryPattern.pattern_type, func.count(MemoryPattern.id))
            .where(MemoryPattern.agent_id == agent_id)
            .group_by(MemoryPattern.pattern_type)
        )
        pattern_types = {ptype: count for ptype, count in pattern_type_result}
        
        # Average pattern confidence
        avg_confidence_result = await self.session.execute(
            select(func.avg(MemoryPattern.confidence))
            .where(MemoryPattern.agent_id == agent_id)
        )
        avg_confidence = avg_confidence_result.scalar() or 0
        
        return {
            "total_patterns": total_patterns,
            "pattern_type_distribution": pattern_types,
            "average_pattern_confidence": float(avg_confidence) if avg_confidence else 0,
            "active_patterns": await self._count_active_patterns(agent_id),
            "learning_velocity": await self._calculate_learning_velocity(agent_id)
        }
    
    async def _get_time_series_data(self, agent_id: str, days: int = 30) -> Dict[str, Any]:
        """Get time series data for the last N days."""
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Daily memory creation
        daily_query = text("""
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM memories_v2
            WHERE agent_id = :agent_id AND created_at >= :cutoff
            GROUP BY date
            ORDER BY date
        """)
        
        daily_result = await self.session.execute(
            daily_query, 
            {"agent_id": agent_id, "cutoff": cutoff}
        )
        
        daily_memories = {
            str(date): count 
            for date, count in daily_result
        }
        
        return {
            "daily_memory_creation": daily_memories,
            "trend": self._calculate_trend(daily_memories)
        }
    
    async def _get_collaboration_stats(self, agent_id: str) -> Dict[str, Any]:
        """Get collaboration and sharing statistics."""
        
        # Memories shared by this agent
        shared_by_query = text("""
            SELECT COUNT(DISTINCT memory_id)
            FROM memory_sharing
            WHERE shared_by_agent_id = :agent_id
        """)
        
        shared_by_result = await self.session.execute(shared_by_query, {"agent_id": agent_id})
        memories_shared = shared_by_result.scalar() or 0
        
        # Memories shared with this agent
        shared_with_query = text("""
            SELECT COUNT(DISTINCT memory_id)
            FROM memory_sharing
            WHERE shared_with_agent_id = :agent_id
        """)
        
        shared_with_result = await self.session.execute(shared_with_query, {"agent_id": agent_id})
        memories_received = shared_with_result.scalar() or 0
        
        # Top collaborators
        collaborator_query = text("""
            SELECT shared_with_agent_id, COUNT(*) as count
            FROM memory_sharing
            WHERE shared_by_agent_id = :agent_id
            GROUP BY shared_with_agent_id
            ORDER BY count DESC
            LIMIT 5
        """)
        
        collaborator_result = await self.session.execute(collaborator_query, {"agent_id": agent_id})
        top_collaborators = [
            {"agent_id": agent, "shared_count": count}
            for agent, count in collaborator_result
        ]
        
        return {
            "memories_shared": memories_shared,
            "memories_received": memories_received,
            "collaboration_score": self._calculate_collaboration_score(memories_shared, memories_received),
            "top_collaborators": top_collaborators
        }
    
    # Helper methods
    
    def _calculate_uptime(self, created_at: datetime, last_active_at: datetime) -> float:
        """Calculate uptime in hours."""
        if not created_at:
            return 0
        
        end_time = last_active_at or datetime.utcnow()
        delta = end_time - created_at
        return delta.total_seconds() / 3600
    
    def _find_peak_hours(self, hourly_distribution: Dict[int, int]) -> List[int]:
        """Find peak access hours."""
        if not hourly_distribution:
            return []
        
        max_count = max(hourly_distribution.values())
        threshold = max_count * 0.8  # Within 80% of peak
        
        return [
            hour for hour, count in hourly_distribution.items()
            if count >= threshold
        ]
    
    def _calculate_reliability(self, agent: Agent) -> float:
        """Calculate reliability score (0-1)."""
        factors = [
            agent.success_rate,
            agent.health_score,
            1.0 if agent.average_response_time_ms and agent.average_response_time_ms < 1000 else 0.5
        ]
        return sum(factors) / len(factors)
    
    def _calculate_efficiency(self, agent: Agent) -> float:
        """Calculate efficiency score (0-1)."""
        if not agent.average_response_time_ms:
            return 0.5
        
        # Faster response = higher efficiency
        if agent.average_response_time_ms < 100:
            return 1.0
        elif agent.average_response_time_ms < 500:
            return 0.8
        elif agent.average_response_time_ms < 1000:
            return 0.6
        else:
            return 0.4
    
    async def _count_shared_memories(self, agent_id: str) -> int:
        """Count memories shared by agent."""
        result = await self.session.execute(
            select(func.count(Memory.id))
            .where(and_(
                Memory.agent_id == agent_id,
                Memory.access_level != 'private'
            ))
        )
        return result.scalar() or 0
    
    async def _count_consolidated_memories(self, agent_id: str) -> int:
        """Count consolidated memories."""
        query = text("""
            SELECT COUNT(DISTINCT consolidated_memory_id)
            FROM memory_consolidations
            WHERE agent_id = :agent_id
        """)
        result = await self.session.execute(query, {"agent_id": agent_id})
        return result.scalar() or 0
    
    async def _count_active_patterns(self, agent_id: str) -> int:
        """Count active patterns."""
        result = await self.session.execute(
            select(func.count(MemoryPattern.id))
            .where(and_(
                MemoryPattern.agent_id == agent_id,
                MemoryPattern.is_active == True
            ))
        )
        return result.scalar() or 0
    
    async def _calculate_learning_velocity(self, agent_id: str) -> float:
        """Calculate learning velocity (patterns per day)."""
        # Get patterns from last 30 days
        cutoff = datetime.utcnow() - timedelta(days=30)
        result = await self.session.execute(
            select(func.count(MemoryPattern.id))
            .where(and_(
                MemoryPattern.agent_id == agent_id,
                MemoryPattern.created_at >= cutoff
            ))
        )
        pattern_count = result.scalar() or 0
        return pattern_count / 30.0
    
    def _calculate_trend(self, daily_data: Dict[str, int]) -> str:
        """Calculate trend from daily data."""
        if len(daily_data) < 7:
            return "insufficient_data"
        
        values = list(daily_data.values())
        recent_avg = sum(values[-7:]) / 7
        previous_avg = sum(values[-14:-7]) / 7 if len(values) >= 14 else recent_avg
        
        if recent_avg > previous_avg * 1.1:
            return "increasing"
        elif recent_avg < previous_avg * 0.9:
            return "decreasing"
        else:
            return "stable"
    
    def _calculate_collaboration_score(self, shared: int, received: int) -> float:
        """Calculate collaboration score (0-1)."""
        if shared + received == 0:
            return 0.0
        
        # Balance between sharing and receiving
        balance = min(shared, received) / max(shared, received) if max(shared, received) > 0 else 0
        # Activity level
        activity = min((shared + received) / 100, 1.0)  # Cap at 100 for full score
        
        return (balance + activity) / 2