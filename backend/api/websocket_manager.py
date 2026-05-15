import logging
import json
from typing import Dict, Set, List
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        # Maps chatbot_id -> set of active WebSockets
        self.active_connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, chatbot_id: int):
        await websocket.accept()
        if chatbot_id not in self.active_connections:
            self.active_connections[chatbot_id] = set()
        self.active_connections[chatbot_id].add(websocket)
        logger.debug(f"[WS] Connection added for chatbot {chatbot_id}. Total connections: {len(self.active_connections[chatbot_id])}")

    def disconnect(self, websocket: WebSocket, chatbot_id: int):
        if chatbot_id in self.active_connections:
            self.active_connections[chatbot_id].discard(websocket)
            if not self.active_connections[chatbot_id]:
                del self.active_connections[chatbot_id]
        logger.debug(f"[WS] Connection removed for chatbot {chatbot_id}")

    async def broadcast_to_chatbot(self, chatbot_id: int, message: str):
        """Send a message to all active connections for a specific chatbot."""
        if chatbot_id not in self.active_connections:
            return

        dead_connections = []
        for connection in self.active_connections[chatbot_id]:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.warning(f"[WS] Failed to send to connection for chatbot {chatbot_id}: {e}")
                dead_connections.append(connection)

        # Cleanup dead connections
        for dead in dead_connections:
            self.active_connections[chatbot_id].discard(dead)

manager = WebSocketManager()
