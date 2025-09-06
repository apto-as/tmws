#!/usr/bin/env python3
"""
TMWS Integration Test Suite
Comprehensive testing of all system components
"""

import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import httpx
from datetime import datetime
from typing import Dict, Any

BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"


class TMWSIntegrationTest:
    """Integration test suite for TMWS"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(base_url=BASE_URL, timeout=30.0)
        self.results = []
    
    async def test_health_check(self) -> bool:
        """Test system health endpoints"""
        print("\n🔍 Testing Health Check...")
        try:
            response = await self.client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            print("✅ Health check passed")
            return True
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            return False
    
    async def test_task_crud(self) -> bool:
        """Test task CRUD operations"""
        print("\n📝 Testing Task Operations...")
        try:
            # Create task
            create_response = await self.client.post(
                f"{API_PREFIX}/tasks",
                params={
                    "title": "Integration Test Task",
                    "description": "Testing task creation",
                    "priority": "high",
                    "assigned_persona": "artemis"
                }
            )
            assert create_response.status_code == 201
            task = create_response.json()["task"]
            task_id = task["id"]
            print(f"✅ Task created: {task_id}")
            
            # Read task
            get_response = await self.client.get(f"{API_PREFIX}/tasks/{task_id}")
            assert get_response.status_code == 200
            print("✅ Task retrieved")
            
            # Update task
            update_response = await self.client.put(
                f"{API_PREFIX}/tasks/{task_id}",
                params={
                    "status": "IN_PROGRESS",
                    "progress": 50
                }
            )
            assert update_response.status_code == 200
            print("✅ Task updated")
            
            # Complete task
            complete_response = await self.client.post(
                f"{API_PREFIX}/tasks/{task_id}/complete"
            )
            assert complete_response.status_code == 200
            print("✅ Task completed")
            
            # Delete task
            delete_response = await self.client.delete(
                f"{API_PREFIX}/tasks/{task_id}"
            )
            assert delete_response.status_code == 200
            print("✅ Task deleted")
            
            return True
        except Exception as e:
            print(f"❌ Task operations failed: {e}")
            return False
    
    async def test_workflow_operations(self) -> bool:
        """Test workflow operations"""
        print("\n⚙️ Testing Workflow Operations...")
        try:
            # Create workflow
            create_response = await self.client.post(
                f"{API_PREFIX}/workflows",
                params={
                    "name": "Test Workflow",
                    "workflow_type": "integration_test",
                    "description": "Testing workflow creation",
                    "priority": "MEDIUM"
                }
            )
            assert create_response.status_code == 201
            workflow = create_response.json()["workflow"]
            workflow_id = workflow["id"]
            print(f"✅ Workflow created: {workflow_id}")
            
            # Get workflow status
            status_response = await self.client.get(
                f"{API_PREFIX}/workflows/{workflow_id}/status"
            )
            assert status_response.status_code == 200
            status = status_response.json()["status"]
            print(f"✅ Workflow status: {status}")
            
            # List workflows
            list_response = await self.client.get(f"{API_PREFIX}/workflows")
            assert list_response.status_code == 200
            workflows = list_response.json()["workflows"]
            assert len(workflows) > 0
            print(f"✅ Listed {len(workflows)} workflows")
            
            # Delete workflow
            delete_response = await self.client.delete(
                f"{API_PREFIX}/workflows/{workflow_id}"
            )
            assert delete_response.status_code == 200
            print("✅ Workflow deleted")
            
            return True
        except Exception as e:
            print(f"❌ Workflow operations failed: {e}")
            return False
    
    async def test_memory_operations(self) -> bool:
        """Test memory storage and search"""
        print("\n🧠 Testing Memory Operations...")
        try:
            # Store memory
            store_response = await self.client.post(
                f"{API_PREFIX}/memory/store",
                json={
                    "content": "Integration test memory content",
                    "importance": 0.8,
                    "metadata": {"test": True}
                }
            )
            assert store_response.status_code == 200
            memory_id = store_response.json()["memory_id"]
            print(f"✅ Memory stored: {memory_id}")
            
            # Search memory
            search_response = await self.client.post(
                f"{API_PREFIX}/memory/search",
                json={
                    "query": "integration test",
                    "limit": 5
                }
            )
            assert search_response.status_code == 200
            results = search_response.json()["results"]
            assert len(results) > 0
            print(f"✅ Found {len(results)} memories")
            
            return True
        except Exception as e:
            print(f"❌ Memory operations failed: {e}")
            return False
    
    async def test_persona_operations(self) -> bool:
        """Test persona management"""
        print("\n👤 Testing Persona Operations...")
        try:
            # List personas
            list_response = await self.client.get(f"{API_PREFIX}/personas")
            assert list_response.status_code == 200
            personas = list_response.json()["personas"]
            print(f"✅ Listed {len(personas)} personas")
            
            # Get specific persona if exists
            if personas:
                persona_id = personas[0]["id"]
                get_response = await self.client.get(
                    f"{API_PREFIX}/personas/{persona_id}"
                )
                assert get_response.status_code == 200
                print(f"✅ Retrieved persona: {persona_id}")
            
            return True
        except Exception as e:
            print(f"❌ Persona operations failed: {e}")
            return False
    
    async def test_statistics(self) -> bool:
        """Test statistics endpoints"""
        print("\n📊 Testing Statistics...")
        try:
            # Task statistics
            task_stats = await self.client.get(f"{API_PREFIX}/tasks/stats/summary")
            assert task_stats.status_code == 200
            print("✅ Task statistics retrieved")
            
            # Workflow statistics
            workflow_stats = await self.client.get(
                f"{API_PREFIX}/workflows/stats/summary"
            )
            assert workflow_stats.status_code == 200
            print("✅ Workflow statistics retrieved")
            
            return True
        except Exception as e:
            print(f"❌ Statistics retrieval failed: {e}")
            return False
    
    async def run_all_tests(self):
        """Run all integration tests"""
        print("=" * 60)
        print("🚀 TMWS Integration Test Suite")
        print("=" * 60)
        
        tests = [
            ("Health Check", self.test_health_check),
            ("Task CRUD", self.test_task_crud),
            ("Workflow Operations", self.test_workflow_operations),
            ("Memory Operations", self.test_memory_operations),
            ("Persona Operations", self.test_persona_operations),
            ("Statistics", self.test_statistics),
        ]
        
        passed = 0
        failed = 0
        
        for name, test_func in tests:
            try:
                result = await test_func()
                self.results.append((name, result))
                if result:
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"❌ {name} test crashed: {e}")
                self.results.append((name, False))
                failed += 1
        
        print("\n" + "=" * 60)
        print("📋 Test Results Summary")
        print("=" * 60)
        for name, result in self.results:
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"{status}: {name}")
        
        print(f"\n📊 Total: {passed} passed, {failed} failed")
        
        if failed == 0:
            print("\n🎉 All tests passed successfully!")
        else:
            print(f"\n⚠️ {failed} tests failed. Please review the errors above.")
        
        await self.client.aclose()
        return failed == 0


async def main():
    """Main entry point"""
    print("\n🔄 Starting TMWS Integration Tests...")
    print("Make sure TMWS server is running on http://localhost:8000")
    print("-" * 60)
    
    # Check if server is running
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/health", timeout=5.0)
            if response.status_code != 200:
                print("❌ TMWS server is not responding correctly")
                print("Please start the server with: python -m src.main")
                return False
    except Exception as e:
        print(f"❌ Cannot connect to TMWS server: {e}")
        print("Please start the server with: python -m src.main")
        return False
    
    # Run tests
    tester = TMWSIntegrationTest()
    success = await tester.run_all_tests()
    
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)