#!/usr/bin/env python3
"""
Test script for custom agent registration functionality.
Tests both AgentContextManager and integration with MCP tools.
"""

import os
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from tmws.agent_context_manager import AgentContextManager


def test_agent_context_manager():
    """Test AgentContextManager functionality."""
    
    print("=== Testing AgentContextManager ===\n")
    
    # Initialize manager
    manager = AgentContextManager()
    
    # Test 1: Verify Trinitas agents are loaded
    print("Test 1: Trinitas agents loaded")
    agents = manager.list_available_agents()
    trinitas_count = sum(1 for a in agents if a["is_system"])
    print(f"✓ Found {trinitas_count} Trinitas agents")
    assert trinitas_count == 6, "Should have 6 Trinitas agents"
    
    # Test 2: Register a custom agent
    print("\nTest 2: Register custom agent")
    result = manager.register_custom_agent(
        short_name="test_agent",
        full_id="test-agent-001",
        capabilities=["testing", "validation"],
        namespace="test",
        display_name="Test Agent",
        access_level="private"
    )
    print(f"✓ Registration result: {result['success']}")
    assert result["success"], f"Registration failed: {result.get('error')}"
    
    # Test 3: Verify agent is in the list
    print("\nTest 3: Verify agent in list")
    agents = manager.list_available_agents()
    test_agent = next((a for a in agents if a["name"] == "test_agent"), None)
    print(f"✓ Found test_agent: {test_agent is not None}")
    assert test_agent is not None, "Test agent not found in list"
    assert not test_agent["is_system"], "Custom agent should not be system agent"
    
    # Test 4: Switch to custom agent
    print("\nTest 4: Switch to custom agent")
    switch_result = manager.switch_agent("test_agent")
    print(f"✓ Switch successful: {switch_result['success']}")
    assert switch_result["success"], f"Switch failed: {switch_result.get('error')}"
    assert manager.current_agent == "test-agent-001", "Current agent not updated"
    
    # Test 5: Get current context
    print("\nTest 5: Get current context")
    context = manager.get_current_agent_context()
    print(f"✓ Current agent: {context['current_agent']}")
    print(f"  Is custom: {context['is_custom_agent']}")
    assert context["is_custom_agent"], "Should be marked as custom agent"
    
    # Test 6: Cannot register duplicate
    print("\nTest 6: Duplicate registration protection")
    dup_result = manager.register_custom_agent(
        short_name="test_agent",
        full_id="test-agent-002",
        capabilities=["testing"]
    )
    print(f"✓ Duplicate rejected: {not dup_result['success']}")
    assert not dup_result["success"], "Should reject duplicate registration"
    
    # Test 7: Cannot override Trinitas agent
    print("\nTest 7: Trinitas agent protection")
    sys_result = manager.register_custom_agent(
        short_name="athena",
        full_id="fake-athena",
        capabilities=["fake"]
    )
    print(f"✓ System agent protected: {not sys_result['success']}")
    assert not sys_result["success"], "Should not allow overriding system agents"
    
    # Test 8: Save custom agents
    print("\nTest 8: Save custom agents")
    save_result = manager.save_custom_agents("test_agents.json")
    print(f"✓ Save successful: {save_result['success']}")
    assert save_result["success"], f"Save failed: {save_result.get('error')}"
    assert Path("test_agents.json").exists(), "Config file not created"
    
    # Test 9: Unregister custom agent
    print("\nTest 9: Unregister custom agent")
    unreg_result = manager.unregister_custom_agent("test_agent")
    print(f"✓ Unregister successful: {unreg_result['success']}")
    assert unreg_result["success"], f"Unregister failed: {unreg_result.get('error')}"
    
    # Test 10: Cannot unregister Trinitas agent
    print("\nTest 10: Cannot unregister Trinitas agent")
    sys_unreg = manager.unregister_custom_agent("artemis")
    print(f"✓ System agent protected: {not sys_unreg['success']}")
    assert not sys_unreg["success"], "Should not allow unregistering system agents"
    
    # Test 11: Load agents from config
    print("\nTest 11: Load agents from config")
    test_config = {
        "version": "1.0",
        "custom_agents": [
            {
                "name": "loaded_agent",
                "full_id": "loaded-agent-001",
                "capabilities": ["loaded_capability"],
                "namespace": "loaded",
                "display_name": "Loaded Agent"
            }
        ]
    }
    with open("test_load.json", "w") as f:
        json.dump(test_config, f)
    
    # Clear and reload
    manager.custom_agents.clear()
    manager.all_agents = manager.TRINITAS_AGENTS.copy()
    manager._load_custom_agents_from_config = lambda: None  # Skip auto-load
    
    # Manually load from test file
    with open("test_load.json", "r") as f:
        config = json.load(f)
        for agent in config["custom_agents"]:
            load_result = manager.register_custom_agent(
                short_name=agent["name"],
                full_id=agent["full_id"],
                capabilities=agent.get("capabilities", []),
                namespace=agent.get("namespace", "custom"),
                display_name=agent.get("display_name")
            )
            print(f"✓ Loaded agent '{agent['name']}': {load_result['success']}")
    
    # Cleanup
    Path("test_agents.json").unlink(missing_ok=True)
    Path("test_load.json").unlink(missing_ok=True)
    
    print("\n=== All tests passed! ===")
    return True


def test_validation():
    """Test input validation."""
    
    print("\n=== Testing Input Validation ===\n")
    
    manager = AgentContextManager()
    
    # Test invalid agent names
    invalid_names = [
        ("", "empty name"),
        ("a", "too short"),
        ("a" * 33, "too long"),
        ("123start", "starts with number"),
        ("has spaces", "contains spaces"),
        ("has@special", "contains special chars"),
    ]
    
    for name, reason in invalid_names:
        result = manager.register_custom_agent(
            short_name=name,
            full_id="test-id",
            capabilities=["test"]
        )
        print(f"✓ Rejected '{name}' ({reason}): {not result['success']}")
        assert not result["success"], f"Should reject {reason}"
    
    # Test valid names
    valid_names = [
        "ab",
        "test_agent",
        "agent-123",
        "my_custom_agent",
        "agent_2024",
    ]
    
    for i, name in enumerate(valid_names):
        result = manager.register_custom_agent(
            short_name=name,
            full_id=f"test-id-{i}",
            capabilities=["test"]
        )
        print(f"✓ Accepted valid name '{name}': {result['success']}")
        assert result["success"], f"Should accept valid name: {name}"
    
    print("\n=== Validation tests passed! ===")
    return True


if __name__ == "__main__":
    try:
        # Set environment for testing
        os.environ["TMWS_AGENT_ID"] = "test-runner"
        
        # Run tests
        test_agent_context_manager()
        test_validation()
        
        print("\n✅ All tests completed successfully!")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)