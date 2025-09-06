#!/usr/bin/env python3
"""
TMWS Tactical System Validation
Quick validation script to ensure tactical coordination system is properly integrated
"""

import sys
import asyncio
from pathlib import Path

# Add the src directory to Python path
tmws_root = Path(__file__).parent.parent
sys.path.insert(0, str(tmws_root))

async def validate_tactical_system():
    """Validate tactical system components"""
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║                TACTICAL SYSTEM VALIDATION                   ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    
    validation_results = []
    
    # Test 1: Import tactical coordinator
    try:
        from src.core.tactical_coordinator import create_tactical_coordinator
        print("✅ Tactical Coordinator import: SUCCESS")
        validation_results.append(("Tactical Coordinator Import", True))
    except ImportError as e:
        print(f"❌ Tactical Coordinator import: FAILED - {e}")
        validation_results.append(("Tactical Coordinator Import", False))
    
    # Test 2: Import process manager
    try:
        from src.core.process_manager import (
            create_tactical_process_manager,
            create_fastmcp_manager,
            create_fastapi_manager,
            ServiceState,
            ProcessPriority
        )
        print("✅ Process Manager import: SUCCESS")
        validation_results.append(("Process Manager Import", True))
    except ImportError as e:
        print(f"❌ Process Manager import: FAILED - {e}")
        validation_results.append(("Process Manager Import", False))
    
    # Test 3: Create tactical coordinator instance
    try:
        coordinator = create_tactical_coordinator()
        print("✅ Tactical Coordinator creation: SUCCESS")
        validation_results.append(("Tactical Coordinator Creation", True))
    except Exception as e:
        print(f"❌ Tactical Coordinator creation: FAILED - {e}")
        validation_results.append(("Tactical Coordinator Creation", False))
        return validation_results
    
    # Test 4: Create process manager instance
    try:
        process_manager = create_tactical_process_manager()
        print("✅ Process Manager creation: SUCCESS")
        validation_results.append(("Process Manager Creation", True))
    except Exception as e:
        print(f"❌ Process Manager creation: FAILED - {e}")
        validation_results.append(("Process Manager Creation", False))
    
    # Test 5: Check service state enums
    try:
        states = [state for state in ServiceState]
        priorities = [priority for priority in ProcessPriority]
        print(f"✅ Service States: {len(states)} defined")
        print(f"✅ Process Priorities: {len(priorities)} defined")
        validation_results.append(("Service States/Priorities", True))
    except Exception as e:
        print(f"❌ Service States/Priorities: FAILED - {e}")
        validation_results.append(("Service States/Priorities", False))
    
    # Test 6: Tactical coordinator basic functionality
    try:
        status = coordinator.get_tactical_status()
        print("✅ Tactical status retrieval: SUCCESS")
        validation_results.append(("Status Retrieval", True))
    except Exception as e:
        print(f"❌ Tactical status retrieval: FAILED - {e}")
        validation_results.append(("Status Retrieval", False))
    
    # Test 7: Mock service manager creation
    try:
        # Create mock FastAPI app
        class MockApp:
            pass
        
        # Create mock MCP server  
        class MockMCPServer:
            pass
        
        fastapi_manager = create_fastapi_manager(MockApp())
        fastmcp_manager = create_fastmcp_manager(MockMCPServer())
        print("✅ Service Manager creation: SUCCESS")
        validation_results.append(("Service Manager Creation", True))
    except Exception as e:
        print(f"❌ Service Manager creation: FAILED - {e}")
        validation_results.append(("Service Manager Creation", False))
    
    # Test 8: Process manager service registration
    try:
        process_manager.register_service("test_fastapi", fastapi_manager)
        process_manager.register_service("test_fastmcp", fastmcp_manager)
        print("✅ Service registration: SUCCESS")
        validation_results.append(("Service Registration", True))
    except Exception as e:
        print(f"❌ Service registration: FAILED - {e}")
        validation_results.append(("Service Registration", False))
    
    # Test 9: Dependency graph calculation
    try:
        startup_order = process_manager._calculate_startup_order()
        print(f"✅ Startup order calculation: SUCCESS - {startup_order}")
        validation_results.append(("Startup Order Calculation", True))
    except Exception as e:
        print(f"❌ Startup order calculation: FAILED - {e}")
        validation_results.append(("Startup Order Calculation", False))
    
    # Test 10: Tactical command execution (dry run)
    try:
        command_result = await coordinator.execute_tactical_command("status")
        print("✅ Tactical command execution: SUCCESS")
        validation_results.append(("Command Execution", True))
    except Exception as e:
        print(f"❌ Tactical command execution: FAILED - {e}")
        validation_results.append(("Command Execution", False))
    
    # Summary
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║                     VALIDATION SUMMARY                      ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    
    passed = sum(1 for _, result in validation_results if result)
    total = len(validation_results)
    success_rate = (passed / total) * 100
    
    for test_name, result in validation_results:
        status = "PASS" if result else "FAIL"
        print(f"║ {test_name:<45} {status:>8} ║")
    
    print("╠══════════════════════════════════════════════════════════════╣")
    print(f"║ Overall Result: {passed}/{total} tests passed ({success_rate:.1f}%)           ║")
    
    if success_rate == 100:
        print("║ 🎯 TACTICAL SYSTEM FULLY OPERATIONAL                        ║")
    elif success_rate >= 80:
        print("║ ⚠️  TACTICAL SYSTEM MOSTLY FUNCTIONAL                       ║")
    else:
        print("║ ❌ TACTICAL SYSTEM REQUIRES ATTENTION                       ║")
    
    print("╚══════════════════════════════════════════════════════════════╝")
    
    return validation_results


def check_dependencies():
    """Check required dependencies"""
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║                   DEPENDENCY CHECK                          ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    
    dependencies = [
        ("asyncio", "Built-in"),
        ("logging", "Built-in"),
        ("psutil", "pip install psutil"),
        ("aiohttp", "pip install aiohttp"),
        ("fastapi", "pip install fastapi"),
        ("uvicorn", "pip install uvicorn")
    ]
    
    for dep_name, install_cmd in dependencies:
        try:
            __import__(dep_name)
            print(f"✅ {dep_name}: Available")
        except ImportError:
            print(f"❌ {dep_name}: Missing - {install_cmd}")


async def main():
    """Main validation entry point"""
    print("TMWS Tactical System Validation")
    print("Bellona's System Integrity Check")
    print("=" * 64)
    
    # Check dependencies first
    check_dependencies()
    
    # Run validation
    results = await validate_tactical_system()
    
    # Exit with appropriate code
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    if passed == total:
        print("\n🎯 All systems operational. Tactical coordination ready.")
        sys.exit(0)
    else:
        print("\n⚠️ Some issues detected. Please review and fix before deployment.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())