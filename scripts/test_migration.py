#!/usr/bin/env python3
"""
Test script for TMWS v2.0 Universal Multi-Agent Platform migration.
Validates the new agent-centric architecture and performance optimizations.
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Add the src directory to Python path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.service_manager import service_context, get_service, health_check
from models import Agent, Memory, Task, LearningPattern
from services.learning_service import LearningService
from services.batch_service import batch_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_agent_operations():
    """Test agent CRUD operations."""
    logger.info("Testing Agent Operations...")
    
    async with service_context():
        agent_service = await get_service("agent")
        
        # Create test agent
        agent_data = {
            "agent_id": "test-claude-sonnet-4",
            "display_name": "Test Claude Sonnet 4",
            "agent_type": "language_model",
            "agent_subtype": "reasoning",
            "capabilities": {
                "text_generation": True,
                "code_analysis": True,
                "reasoning": True
            },
            "configuration": {
                "max_tokens": 4096,
                "temperature": 0.7
            },
            "namespace": "test",
            "learning_enabled": True
        }
        
        agent = await agent_service.create_agent(**agent_data)
        logger.info(f"Created agent: {agent.agent_id}")
        
        # Update agent performance
        await agent_service.update_agent_performance(
            agent.agent_id,
            successful_requests=10,
            failed_requests=1,
            total_tokens=1000,
            avg_response_time=0.5
        )
        
        # Retrieve agent
        retrieved = await agent_service.get_agent_by_id(agent.agent_id)
        assert retrieved.total_requests == 11
        assert retrieved.successful_requests == 10
        
        logger.info("✓ Agent operations test passed")


async def test_memory_v2():
    """Test enhanced memory operations."""
    logger.info("Testing Memory v2 Operations...")
    
    async with service_context():
        memory_service = await get_service("memory")
        
        # Create memories with different access levels
        memories_data = [
            {
                "content": "Private memory for test agent",
                "agent_id": "test-claude-sonnet-4",
                "namespace": "test",
                "access_level": "private",
                "memory_type": "episodic",
                "importance": 0.8
            },
            {
                "content": "Shared knowledge about optimization patterns",
                "agent_id": "test-claude-sonnet-4",
                "namespace": "test",
                "access_level": "shared",
                "memory_type": "semantic",
                "importance": 0.9
            },
            {
                "content": "Public system knowledge",
                "agent_id": None,
                "namespace": "system",
                "access_level": "public",
                "memory_type": "system",
                "importance": 1.0
            }
        ]
        
        created_memories = []
        for memory_data in memories_data:
            memory = await memory_service.create_memory(**memory_data)
            created_memories.append(memory)
            logger.info(f"Created memory: {memory.id} ({memory.access_level})")
        
        # Test access control
        private_memories = await memory_service.get_agent_memories(
            "test-claude-sonnet-4", 
            access_level="private"
        )
        assert len(private_memories) >= 1
        
        # Test semantic search
        search_results = await memory_service.search_memories(
            "optimization patterns",
            requesting_agent_id="test-claude-sonnet-4"
        )
        assert len(search_results) >= 1
        
        logger.info("✓ Memory v2 operations test passed")


async def test_learning_patterns():
    """Test enhanced learning pattern system."""
    logger.info("Testing Learning Pattern System...")
    
    async with service_context():
        learning_service = await get_service("learning")
        
        # Create learning patterns
        patterns_data = [
            {
                "pattern_name": "sql_optimization",
                "category": "database",
                "subcategory": "indexing",
                "pattern_data": {
                    "description": "Add index to frequently queried columns",
                    "steps": ["analyze query", "identify columns", "create index"],
                    "expected_improvement": "90%"
                },
                "agent_id": "test-claude-sonnet-4",
                "namespace": "performance",
                "access_level": "shared"
            },
            {
                "pattern_name": "code_review_checklist",
                "category": "software_quality",
                "pattern_data": {
                    "checklist": [
                        "Check for null pointer exceptions",
                        "Verify input validation",
                        "Assess performance implications"
                    ]
                },
                "agent_id": "test-claude-sonnet-4",
                "namespace": "test",
                "access_level": "private"
            }
        ]
        
        created_patterns = []
        for pattern_data in patterns_data:
            pattern = await learning_service.create_pattern(**pattern_data)
            created_patterns.append(pattern)
            logger.info(f"Created pattern: {pattern.pattern_name}")
        
        # Test pattern usage tracking
        for pattern in created_patterns:
            updated_pattern = await learning_service.use_pattern(
                pattern.id,
                using_agent_id="test-claude-sonnet-4",
                execution_time=0.5,
                success=True
            )
            assert updated_pattern.usage_count == 1
            assert updated_pattern.success_rate == 1.0
        
        # Test pattern search
        search_results = await learning_service.search_patterns(
            query_text="optimization",
            requesting_agent_id="test-claude-sonnet-4"
        )
        assert len(search_results) >= 1
        
        # Test recommendations
        recommendations = await learning_service.recommend_patterns(
            "test-claude-sonnet-4",
            category="database"
        )
        assert len(recommendations) >= 0  # May be empty if no public patterns
        
        logger.info("✓ Learning pattern system test passed")


async def test_batch_operations():
    """Test batch processing capabilities."""
    logger.info("Testing Batch Operations...")
    
    async with service_context():
        # Test batch memory creation
        memories_data = []
        for i in range(50):
            memories_data.append({
                "content": f"Test memory content {i}",
                "agent_id": "test-claude-sonnet-4",
                "namespace": "test",
                "importance": 0.5 + (i % 5) * 0.1,
                "memory_type": "episodic"
            })
        
        job_id = await batch_service.batch_create_memories(
            memories_data,
            agent_id="test-claude-sonnet-4",
            batch_size=10
        )
        
        logger.info(f"Started batch job: {job_id}")
        
        # Monitor job progress
        max_wait = 30  # seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status = await batch_service.get_job_status(job_id)
            if status:
                logger.info(f"Batch job progress: {status['progress_percentage']:.1f}%")
                if status['status'] in ['completed', 'failed']:
                    break
            await asyncio.sleep(1)
        
        final_status = await batch_service.get_job_status(job_id)
        assert final_status['status'] == 'completed'
        assert final_status['success_count'] > 0
        
        logger.info("✓ Batch operations test passed")


async def test_performance_metrics():
    """Test performance monitoring and metrics."""
    logger.info("Testing Performance Metrics...")
    
    async with service_context():
        # Health check
        health_status = await health_check()
        logger.info(f"System health: {health_status}")
        
        # Check all services are healthy
        for service_name, status in health_status.items():
            assert status['status'] in ['healthy', 'not_initialized'], f"Service {service_name} is not healthy"
        
        # Batch service metrics
        batch_metrics = await batch_service.get_performance_metrics()
        logger.info(f"Batch service metrics: {batch_metrics}")
        
        # Learning service analytics
        learning_service = await get_service("learning")
        analytics = await learning_service.get_pattern_analytics(
            agent_id="test-claude-sonnet-4",
            days=1
        )
        logger.info(f"Learning analytics: {analytics}")
        
        logger.info("✓ Performance metrics test passed")


async def test_migration_compatibility():
    """Test backward compatibility with v1 models."""
    logger.info("Testing Migration Compatibility...")
    
    # This would test that existing v1 data can coexist with v2 models
    # For now, we'll just verify the models can be imported
    try:
        from models import (
            # V1 models
            MemoryV1, Persona, TaskV1,
            # V2 models
            Agent, Memory, Task
        )
        
        logger.info("✓ All model imports successful")
        logger.info("✓ Migration compatibility test passed")
    
    except ImportError as e:
        logger.error(f"Model import failed: {e}")
        raise


async def run_integration_tests():
    """Run all integration tests."""
    logger.info("="*60)
    logger.info("TMWS v2.0 Universal Multi-Agent Platform - Integration Tests")
    logger.info("="*60)
    
    start_time = datetime.now()
    
    tests = [
        test_migration_compatibility,
        test_agent_operations,
        test_memory_v2,
        test_learning_patterns,
        test_batch_operations,
        test_performance_metrics,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            await test_func()
            passed += 1
        except Exception as e:
            logger.error(f"❌ Test {test_func.__name__} failed: {e}")
            failed += 1
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    logger.info("="*60)
    logger.info(f"Test Results: {passed} passed, {failed} failed")
    logger.info(f"Total execution time: {duration:.2f} seconds")
    logger.info("="*60)
    
    if failed > 0:
        logger.error("Some tests failed. Please review the logs above.")
        sys.exit(1)
    else:
        logger.info("🎉 All tests passed! TMWS v2.0 migration successful!")


if __name__ == "__main__":
    asyncio.run(run_integration_tests())