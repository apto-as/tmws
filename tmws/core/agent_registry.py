#!/usr/bin/env python3
"""
Agent Registry Service - Artemis Edition
エージェント自動検出・登録・管理システム

Performance-optimized agent lifecycle management with:
- Environment variable detection (sub-100ms)
- Concurrent capability analysis
- Memory-efficient registry operations
- Real-time status monitoring
"""

import asyncio
import os
import json
import logging
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import weakref
from concurrent.futures import ThreadPoolExecutor
import psutil
from pathlib import Path

from .config import get_settings

logger = logging.getLogger(__name__)

@dataclass
class AgentInfo:
    """Agent information structure - optimized for memory efficiency"""
    id: str
    name: str
    type: str
    capabilities: List[str]
    config_path: Optional[str] = None
    status: str = "active"
    last_seen: Optional[datetime] = None
    performance_score: float = 1.0
    memory_usage: int = 0
    response_time: float = 0.0
    
    def __post_init__(self):
        if self.last_seen is None:
            self.last_seen = datetime.now(timezone.utc)

@dataclass
class CapabilityInfo:
    """Capability metadata with performance metrics"""
    name: str
    description: str
    avg_response_time: float = 0.0
    success_rate: float = 1.0
    usage_count: int = 0

class AgentRegistryService:
    """
    High-performance agent registry with sub-100ms operations.
    
    Artemis design principles:
    - Memory pooling for agent objects
    - Concurrent capability scanning
    - Lazy loading with caching
    - Performance telemetry
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._agents: Dict[str, AgentInfo] = {}
        self._capabilities: Dict[str, CapabilityInfo] = {}
        self._agent_refs: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
        self._lock = asyncio.Lock()
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="agent-scanner")
        self._scan_interval = 60  # seconds
        self._last_scan = None
        self._performance_cache = {}
        
        # Pre-compiled patterns for faster matching
        self._env_patterns = {
            'claude_config': ['CLAUDE_CONFIG', 'ANTHROPIC_CONFIG'],
            'openai_config': ['OPENAI_CONFIG', 'OPENAI_API_KEY'],
            'mcp_config': ['MCP_CONFIG', 'MCP_SERVERS'],
        }
        
        logger.info("AgentRegistryService initialized - Artemis performance standards")
    
    async def detect_agents_from_env(self) -> List[AgentInfo]:
        """
        Environment variable detection with sub-100ms performance.
        
        Returns:
            List[AgentInfo]: Detected agents
        """
        start_time = asyncio.get_event_loop().time()
        agents = []
        
        try:
            # Concurrent environment scanning
            tasks = [
                self._scan_claude_config(),
                self._scan_openai_config(),
                self._scan_mcp_configs(),
                self._scan_custom_configs()
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, list):
                    agents.extend(result)
                elif isinstance(result, Exception):
                    logger.warning(f"Agent detection error: {result}")
            
            # Performance validation
            duration = (asyncio.get_event_loop().time() - start_time) * 1000
            if duration > 100:
                logger.warning(f"Agent detection exceeded 100ms: {duration:.2f}ms")
            else:
                logger.debug(f"Agent detection completed in {duration:.2f}ms")
                
        except Exception as e:
            logger.error(f"Agent detection failed: {e}")
            
        return agents
    
    async def _scan_claude_config(self) -> List[AgentInfo]:
        """Scan for Claude/Anthropic configurations"""
        agents = []
        
        # Check environment variables
        for env_var in self._env_patterns['claude_config']:
            config_path = os.getenv(env_var)
            if config_path and os.path.exists(config_path):
                agent = await self._parse_claude_config(config_path)
                if agent:
                    agents.append(agent)
        
        # Check standard locations
        home_path = Path.home()
        standard_locations = [
            home_path / '.claude' / 'config.json',
            home_path / '.config' / 'claude' / 'config.json',
            home_path / 'Library' / 'Application Support' / 'Claude' / 'config.json',
        ]
        
        for config_path in standard_locations:
            if config_path.exists():
                agent = await self._parse_claude_config(str(config_path))
                if agent:
                    agents.append(agent)
        
        return agents
    
    async def _parse_claude_config(self, config_path: str) -> Optional[AgentInfo]:
        """Parse Claude configuration with error handling"""
        try:
            loop = asyncio.get_event_loop()
            config_data = await loop.run_in_executor(
                self._executor, self._read_json_file, config_path
            )
            
            if not config_data:
                return None
                
            # Extract capabilities from configuration
            capabilities = ['text-generation', 'reasoning', 'analysis']
            if 'tools' in config_data:
                capabilities.extend(config_data['tools'])
                
            return AgentInfo(
                id=f"claude-{hash(config_path) & 0x7fffffff}",
                name="Claude AI Assistant",
                type="claude",
                capabilities=capabilities,
                config_path=config_path,
                performance_score=0.95
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse Claude config {config_path}: {e}")
            return None
    
    async def _scan_openai_config(self) -> List[AgentInfo]:
        """Scan for OpenAI configurations"""
        agents = []
        
        # Environment variables
        if os.getenv('OPENAI_API_KEY'):
            agents.append(AgentInfo(
                id="openai-env",
                name="OpenAI Assistant",
                type="openai",
                capabilities=['text-generation', 'embeddings', 'completion'],
                performance_score=0.90
            ))
        
        return agents
    
    async def _scan_mcp_configs(self) -> List[AgentInfo]:
        """Scan for MCP server configurations"""
        agents = []
        
        # Look for MCP config files
        config_locations = [
            Path.home() / '.mcp' / 'config.json',
            Path.home() / '.config' / 'mcp' / 'config.json',
        ]
        
        for config_path in config_locations:
            if config_path.exists():
                try:
                    loop = asyncio.get_event_loop()
                    config_data = await loop.run_in_executor(
                        self._executor, self._read_json_file, str(config_path)
                    )
                    
                    if config_data and 'servers' in config_data:
                        for server_name, server_config in config_data['servers'].items():
                            agent = AgentInfo(
                                id=f"mcp-{server_name}",
                                name=f"MCP Server: {server_name}",
                                type="mcp",
                                capabilities=server_config.get('capabilities', ['mcp-protocol']),
                                config_path=str(config_path),
                                performance_score=0.85
                            )
                            agents.append(agent)
                            
                except Exception as e:
                    logger.warning(f"Failed to parse MCP config {config_path}: {e}")
        
        return agents
    
    async def _scan_custom_configs(self) -> List[AgentInfo]:
        """Scan for custom agent configurations"""
        agents = []
        
        # Custom TMWS agents
        tmws_config = os.getenv('TMWS_AGENTS_CONFIG')
        if tmws_config and os.path.exists(tmws_config):
            try:
                loop = asyncio.get_event_loop()
                config_data = await loop.run_in_executor(
                    self._executor, self._read_json_file, tmws_config
                )
                
                if config_data and 'agents' in config_data:
                    for agent_config in config_data['agents']:
                        agent = AgentInfo(
                            id=agent_config.get('id', f"custom-{len(agents)}"),
                            name=agent_config.get('name', 'Custom Agent'),
                            type=agent_config.get('type', 'custom'),
                            capabilities=agent_config.get('capabilities', []),
                            config_path=tmws_config,
                            performance_score=agent_config.get('performance_score', 0.80)
                        )
                        agents.append(agent)
                        
            except Exception as e:
                logger.warning(f"Failed to parse custom config {tmws_config}: {e}")
        
        return agents
    
    def _read_json_file(self, file_path: str) -> Optional[Dict]:
        """Synchronous JSON file reader for executor"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
    
    async def register_agent(self, agent: AgentInfo) -> bool:
        """
        Register agent with performance validation.
        
        Args:
            agent: Agent information to register
            
        Returns:
            bool: Registration success
        """
        async with self._lock:
            try:
                # Validate agent capabilities
                validated_agent = await self._validate_agent(agent)
                if not validated_agent:
                    return False
                
                self._agents[agent.id] = validated_agent
                
                # Update capability registry
                for capability in agent.capabilities:
                    if capability not in self._capabilities:
                        self._capabilities[capability] = CapabilityInfo(
                            name=capability,
                            description=f"Capability provided by {agent.name}"
                        )
                    self._capabilities[capability].usage_count += 1
                
                logger.info(f"Agent registered: {agent.name} ({agent.id})")
                return True
                
            except Exception as e:
                logger.error(f"Agent registration failed: {e}")
                return False
    
    async def _validate_agent(self, agent: AgentInfo) -> Optional[AgentInfo]:
        """Validate agent configuration and capabilities"""
        try:
            # Performance test if possible
            if agent.config_path and os.path.exists(agent.config_path):
                # Basic validation passed
                agent.last_seen = datetime.now(timezone.utc)
                return agent
            
            # For environment-based agents
            if not agent.config_path:
                agent.last_seen = datetime.now(timezone.utc)
                return agent
                
        except Exception as e:
            logger.warning(f"Agent validation failed for {agent.id}: {e}")
        
        return None
    
    async def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """Get agent by ID with caching"""
        async with self._lock:
            return self._agents.get(agent_id)
    
    async def list_agents(self, agent_type: Optional[str] = None) -> List[AgentInfo]:
        """List all registered agents with optional type filtering"""
        async with self._lock:
            agents = list(self._agents.values())
            if agent_type:
                agents = [agent for agent in agents if agent.type == agent_type]
            return sorted(agents, key=lambda x: x.performance_score, reverse=True)
    
    async def get_capabilities(self) -> Dict[str, CapabilityInfo]:
        """Get all available capabilities"""
        async with self._lock:
            return dict(self._capabilities)
    
    async def unregister_agent(self, agent_id: str) -> bool:
        """Unregister agent and cleanup resources"""
        async with self._lock:
            try:
                if agent_id in self._agents:
                    agent = self._agents.pop(agent_id)
                    
                    # Update capability counts
                    for capability in agent.capabilities:
                        if capability in self._capabilities:
                            self._capabilities[capability].usage_count -= 1
                            if self._capabilities[capability].usage_count <= 0:
                                del self._capabilities[capability]
                    
                    logger.info(f"Agent unregistered: {agent.name} ({agent_id})")
                    return True
                
                return False
                
            except Exception as e:
                logger.error(f"Agent unregistration failed: {e}")
                return False
    
    async def update_agent_performance(self, agent_id: str, response_time: float, 
                                     success: bool) -> None:
        """Update agent performance metrics"""
        async with self._lock:
            if agent_id in self._agents:
                agent = self._agents[agent_id]
                agent.response_time = response_time
                agent.last_seen = datetime.now(timezone.utc)
                
                # Update performance score (weighted average)
                if success:
                    agent.performance_score = (agent.performance_score * 0.9) + (1.0 * 0.1)
                else:
                    agent.performance_score = (agent.performance_score * 0.9) + (0.0 * 0.1)
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get registry statistics"""
        async with self._lock:
            total_agents = len(self._agents)
            active_agents = sum(1 for agent in self._agents.values() 
                              if agent.status == "active")
            
            agent_types = {}
            total_capabilities = len(self._capabilities)
            
            for agent in self._agents.values():
                agent_types[agent.type] = agent_types.get(agent.type, 0) + 1
            
            return {
                "total_agents": total_agents,
                "active_agents": active_agents,
                "agent_types": agent_types,
                "total_capabilities": total_capabilities,
                "average_performance": sum(agent.performance_score 
                                         for agent in self._agents.values()) / max(total_agents, 1),
                "last_scan": self._last_scan.isoformat() if self._last_scan else None
            }
    
    async def auto_scan(self) -> None:
        """Automatic agent scanning with performance monitoring"""
        try:
            start_time = asyncio.get_event_loop().time()
            
            # Detect new agents
            detected_agents = await self.detect_agents_from_env()
            
            registered_count = 0
            for agent in detected_agents:
                if agent.id not in self._agents:
                    if await self.register_agent(agent):
                        registered_count += 1
            
            self._last_scan = datetime.now(timezone.utc)
            duration = (asyncio.get_event_loop().time() - start_time) * 1000
            
            logger.info(f"Auto-scan completed: {registered_count} new agents, "
                       f"{len(detected_agents)} total detected, {duration:.2f}ms")
                       
        except Exception as e:
            logger.error(f"Auto-scan failed: {e}")
    
    async def cleanup(self) -> None:
        """Cleanup resources"""
        self._executor.shutdown(wait=True)
        logger.info("AgentRegistryService cleanup completed")

class CapabilitiesManager:
    """
    High-performance capability management and routing.
    
    Optimized for:
    - Sub-millisecond capability lookup
    - Concurrent capability execution
    - Performance-based routing
    """
    
    def __init__(self, registry: AgentRegistryService):
        self.registry = registry
        self._capability_cache = {}
        self._performance_weights = {}
        
    async def find_best_agent(self, capability: str) -> Optional[AgentInfo]:
        """Find the best agent for a specific capability"""
        agents = await self.registry.list_agents()
        candidates = [agent for agent in agents 
                     if capability in agent.capabilities and agent.status == "active"]
        
        if not candidates:
            return None
            
        # Sort by performance score and response time
        candidates.sort(key=lambda x: (x.performance_score, -x.response_time), reverse=True)
        return candidates[0]
    
    async def execute_capability(self, capability: str, **kwargs) -> Any:
        """Execute a capability using the best available agent"""
        agent = await self.find_best_agent(capability)
        if not agent:
            raise ValueError(f"No agent available for capability: {capability}")
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            # This would integrate with actual agent execution
            # For now, return a placeholder
            result = f"Executed {capability} via {agent.name}"
            
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
            await self.registry.update_agent_performance(agent.id, response_time, True)
            
            return result
            
        except Exception as e:
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
            await self.registry.update_agent_performance(agent.id, response_time, False)
            raise

class StatisticsService:
    """
    Performance statistics and monitoring service.
    
    Real-time metrics with minimal overhead.
    """
    
    def __init__(self, registry: AgentRegistryService):
        self.registry = registry
        self._metrics_history = []
        self._max_history = 1000
    
    async def collect_metrics(self) -> Dict[str, Any]:
        """Collect comprehensive system metrics"""
        process = psutil.Process()
        
        registry_stats = await self.registry.get_statistics()
        
        metrics = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "system": {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "process_memory_mb": process.memory_info().rss / 1024 / 1024
            },
            "registry": registry_stats,
            "performance": {
                "avg_agent_response_time": self._calculate_avg_response_time(),
                "agent_success_rate": self._calculate_success_rate()
            }
        }
        
        # Store in history (with rotation)
        self._metrics_history.append(metrics)
        if len(self._metrics_history) > self._max_history:
            self._metrics_history.pop(0)
        
        return metrics
    
    def _calculate_avg_response_time(self) -> float:
        """Calculate average response time across all agents"""
        agents = list(self.registry._agents.values())
        if not agents:
            return 0.0
        
        total_time = sum(agent.response_time for agent in agents)
        return total_time / len(agents)
    
    def _calculate_success_rate(self) -> float:
        """Calculate overall success rate"""
        agents = list(self.registry._agents.values())
        if not agents:
            return 1.0
        
        total_score = sum(agent.performance_score for agent in agents)
        return total_score / len(agents)
    
    async def get_performance_report(self) -> Dict[str, Any]:
        """Generate performance report"""
        current_metrics = await self.collect_metrics()
        
        return {
            "current": current_metrics,
            "history_count": len(self._metrics_history),
            "trends": self._calculate_trends() if len(self._metrics_history) > 10 else {}
        }
    
    def _calculate_trends(self) -> Dict[str, float]:
        """Calculate performance trends from history"""
        if len(self._metrics_history) < 2:
            return {}
        
        recent = self._metrics_history[-10:]
        older = self._metrics_history[-20:-10] if len(self._metrics_history) >= 20 else []
        
        if not older:
            return {}
        
        recent_avg_response = sum(m["performance"]["avg_agent_response_time"] for m in recent) / len(recent)
        older_avg_response = sum(m["performance"]["avg_agent_response_time"] for m in older) / len(older)
        
        response_time_trend = ((recent_avg_response - older_avg_response) / max(older_avg_response, 0.001)) * 100
        
        return {
            "response_time_change_percent": response_time_trend
        }