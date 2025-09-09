"""
WebSocket handler for client connections
"""

import json
import asyncio
from typing import Any, Dict, Optional
from fastapi import WebSocket
import structlog

logger = structlog.get_logger()


class WebSocketHandler:
    """Handles WebSocket communication with clients."""
    
    def __init__(self, websocket: WebSocket, client_id: str):
        """Initialize WebSocket handler."""
        self.websocket = websocket
        self.client_id = client_id
        self.connected = True
        self._send_lock = asyncio.Lock()
        
    async def send_message(self, message: Dict[str, Any]) -> bool:
        """Send a message to the client."""
        if not self.connected:
            return False
            
        try:
            async with self._send_lock:
                await self.websocket.send_text(json.dumps(message))
            return True
        except Exception as e:
            logger.error("Failed to send message", 
                        client_id=self.client_id, 
                        error=str(e))
            self.connected = False
            return False
    
    async def send_error(self, error_message: str, error_code: Optional[str] = None):
        """Send an error message to the client."""
        await self.send_message({
            "type": "error",
            "error": error_message,
            "code": error_code or "UNKNOWN_ERROR"
        })
    
    async def send_response(self, request_id: str, result: Any):
        """Send a response to a specific request."""
        await self.send_message({
            "type": "response",
            "request_id": request_id,
            "result": result
        })
    
    async def send_notification(self, event: str, data: Any):
        """Send a notification to the client."""
        await self.send_message({
            "type": "notification",
            "event": event,
            "data": data
        })
    
    async def close(self, code: int = 1000, reason: str = "Normal closure"):
        """Close the WebSocket connection."""
        if self.connected:
            try:
                await self.websocket.close(code=code, reason=reason)
            except Exception as e:
                logger.error("Error closing WebSocket", 
                            client_id=self.client_id,
                            error=str(e))
            finally:
                self.connected = False