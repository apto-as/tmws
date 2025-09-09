#!/usr/bin/env python3
"""
Test WebSocket MCP Connection
"""

import asyncio
import json
import websockets
import uuid
from datetime import datetime


async def test_mcp_connection():
    """Test MCP protocol over WebSocket."""
    uri = "ws://localhost:8000/ws/mcp"
    
    print(f"Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected successfully!")
            
            # Send initialization request
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "clientInfo": {
                        "name": "TMWS Test Client",
                        "version": "1.0.0"
                    },
                    "agent_id": "test-agent",
                    "namespace": "test"
                }
            }
            
            print("\n1. Sending initialization request...")
            await websocket.send(json.dumps(init_request))
            
            response = await websocket.recv()
            response_data = json.loads(response)
            print(f"Response: {json.dumps(response_data, indent=2)}")
            
            # Send initialized confirmation
            initialized_msg = {
                "jsonrpc": "2.0",
                "method": "initialized"
            }
            await websocket.send(json.dumps(initialized_msg))
            print("\n2. Sent initialized confirmation")
            
            # List available tools
            list_tools_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
            
            print("\n3. Listing available tools...")
            await websocket.send(json.dumps(list_tools_request))
            
            response = await websocket.recv()
            response_data = json.loads(response)
            print(f"Available tools: {json.dumps(response_data, indent=2)}")
            
            # Test creating a memory
            create_memory_request = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "create_memory",
                    "arguments": {
                        "content": f"Test memory created at {datetime.now().isoformat()}",
                        "importance": 0.5,
                        "tags": ["test", "websocket"]
                    }
                }
            }
            
            print("\n4. Creating a test memory...")
            await websocket.send(json.dumps(create_memory_request))
            
            response = await websocket.recv()
            response_data = json.loads(response)
            print(f"Memory creation response: {json.dumps(response_data, indent=2)}")
            
            # Test searching memories
            search_request = {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "search_memories",
                    "arguments": {
                        "query": "test",
                        "limit": 5
                    }
                }
            }
            
            print("\n5. Searching for memories...")
            await websocket.send(json.dumps(search_request))
            
            response = await websocket.recv()
            response_data = json.loads(response)
            print(f"Search results: {json.dumps(response_data, indent=2)}")
            
            # Test ping
            ping_request = {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "ping",
                "params": {}
            }
            
            print("\n6. Sending ping...")
            await websocket.send(json.dumps(ping_request))
            
            response = await websocket.recv()
            response_data = json.loads(response)
            print(f"Ping response: {json.dumps(response_data, indent=2)}")
            
            print("\n✅ All tests passed successfully!")
            
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False
    
    return True


async def test_multiple_connections():
    """Test multiple simultaneous WebSocket connections."""
    uri = "ws://localhost:8000/ws/mcp"
    
    print("\n" + "="*50)
    print("Testing multiple simultaneous connections...")
    print("="*50)
    
    async def create_client(client_id: int):
        """Create and test a client connection."""
        try:
            async with websockets.connect(uri) as websocket:
                print(f"\nClient {client_id}: Connected")
                
                # Initialize
                init_request = {
                    "jsonrpc": "2.0",
                    "id": client_id * 100 + 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "clientInfo": {
                            "name": f"Test Client {client_id}",
                            "version": "1.0.0"
                        },
                        "agent_id": f"test-agent-{client_id}",
                        "namespace": "test"
                    }
                }
                
                await websocket.send(json.dumps(init_request))
                response = await websocket.recv()
                response_data = json.loads(response)
                
                if "result" in response_data:
                    print(f"Client {client_id}: Initialized successfully")
                    return True
                else:
                    print(f"Client {client_id}: Initialization failed")
                    return False
                    
        except Exception as e:
            print(f"Client {client_id}: Error - {e}")
            return False
    
    # Create multiple clients concurrently
    tasks = [create_client(i) for i in range(1, 4)]
    results = await asyncio.gather(*tasks)
    
    if all(results):
        print("\n✅ Multiple connection test passed!")
    else:
        print("\n❌ Multiple connection test failed!")
    
    return all(results)


async def main():
    """Run all tests."""
    print("TMWS WebSocket MCP Test Suite")
    print("==============================\n")
    
    # First, check if server is running
    try:
        async with websockets.connect("ws://localhost:8000/ws/mcp") as ws:
            pass
    except Exception:
        print("❌ Server is not running!")
        print("Please start the server first with: tmws-server")
        return
    
    # Run tests
    print("Test 1: Basic MCP Protocol")
    test1_passed = await test_mcp_connection()
    
    print("\n" + "="*50)
    
    print("\nTest 2: Multiple Connections")
    test2_passed = await test_multiple_connections()
    
    print("\n" + "="*50)
    print("\nTest Summary:")
    print(f"  Basic MCP Protocol: {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"  Multiple Connections: {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 All tests passed! TMWS WebSocket server is working correctly.")
    else:
        print("\n⚠️ Some tests failed. Please check the server logs.")


if __name__ == "__main__":
    asyncio.run(main())