#!/usr/bin/env python3
"""
MCP WebSocket Client Adapter
Bridges stdio MCP to WebSocket server
"""

import asyncio
import json
import sys
import websockets
import structlog
from typing import Optional, Dict, Any
import os

logger = structlog.get_logger()


class MCPWebSocketClient:
    """Adapts stdio MCP to WebSocket communication."""
    
    def __init__(self, server_url: str = None):
        """Initialize WebSocket client."""
        self.server_url = server_url or os.getenv("TMWS_SERVER_URL", "ws://localhost:8000/ws/mcp")
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False
        
    async def connect(self):
        """Connect to WebSocket server."""
        try:
            self.websocket = await websockets.connect(self.server_url)
            self.running = True
            logger.info(f"Connected to TMWS server at {self.server_url}")
        except Exception as e:
            logger.error(f"Failed to connect to server: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from WebSocket server."""
        self.running = False
        if self.websocket:
            await self.websocket.close()
            logger.info("Disconnected from TMWS server")
    
    async def handle_stdio_to_ws(self):
        """Read from stdin and send to WebSocket."""
        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)
        
        while self.running:
            try:
                # Read line from stdin
                line = await reader.readline()
                if not line:
                    break
                
                # Parse and send to WebSocket
                try:
                    message = json.loads(line.decode().strip())
                    if self.websocket:
                        await self.websocket.send(json.dumps(message))
                        logger.debug(f"Sent to server: {message.get('method', message.get('id'))}")
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON from stdin: {line}")
                    
            except Exception as e:
                logger.error(f"Error handling stdio input: {e}")
                break
    
    async def handle_ws_to_stdio(self):
        """Read from WebSocket and write to stdout."""
        while self.running:
            try:
                if not self.websocket:
                    await asyncio.sleep(0.1)
                    continue
                
                # Receive from WebSocket
                message = await self.websocket.recv()
                
                # Parse and write to stdout
                try:
                    data = json.loads(message)
                    print(json.dumps(data), flush=True)
                    logger.debug(f"Received from server: {data.get('result', data.get('error'))}")
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON from server: {message}")
                    
            except websockets.exceptions.ConnectionClosed:
                logger.info("WebSocket connection closed")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}")
                break
    
    async def run(self):
        """Run the client adapter."""
        try:
            # Connect to server
            await self.connect()
            
            # Run both handlers concurrently
            await asyncio.gather(
                self.handle_stdio_to_ws(),
                self.handle_ws_to_stdio()
            )
            
        except KeyboardInterrupt:
            logger.info("Client interrupted")
        except Exception as e:
            logger.error(f"Client error: {e}")
        finally:
            await self.disconnect()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP WebSocket Client Adapter")
    parser.add_argument("--server", default=None, help="WebSocket server URL")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Configure logging
    import logging
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        # In production, only log errors to stderr
        logging.basicConfig(level=logging.ERROR)
    
    # Create and run client
    client = MCPWebSocketClient(args.server)
    
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()