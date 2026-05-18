import logging
import json
from typing import Dict, Set, List
from fastapi import WebSocket
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        # Maps chatbot_id -> set of active WebSockets
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # Maps session_id -> WebSocket
        self.active_sessions: Dict[str, WebSocket] = {}
        # Maps WebSocket -> session_id
        self.socket_sessions: Dict[WebSocket, str] = {}
        # Maps WebSocket -> chatbot_id
        self.socket_chatbots: Dict[WebSocket, int] = {}

    async def register(self, websocket: WebSocket, session_id: str, chatbot_id: int):
        """Register a new connection, closing any existing connection for the same session."""
        # 1. Single socket per session: close existing socket for this session if it exists
        if session_id in self.active_sessions:
            old_socket = self.active_sessions[session_id]
            logger.info(f"[WS] Session {session_id} reconnected. Closing old socket.")
            try:
                if old_socket.client_state == WebSocketState.CONNECTED:
                    await old_socket.close(code=4000, reason="Replaced by new connection")
            except Exception as e:
                logger.debug(f"[WS] Error closing old socket for session {session_id}: {e}")
            self.disconnect_socket(old_socket)

        # 2. Register the new socket
        self.active_sessions[session_id] = websocket
        self.socket_sessions[websocket] = session_id
        self.socket_chatbots[websocket] = chatbot_id

        if chatbot_id not in self.active_connections:
            self.active_connections[chatbot_id] = set()
        self.active_connections[chatbot_id].add(websocket)
        
        logger.info(f"[WS] Registered socket for session {session_id}, chatbot {chatbot_id}")

    def disconnect_socket(self, websocket: WebSocket):
        """Fully clean up all tracking maps for a disconnected socket."""
        session_id = self.socket_sessions.pop(websocket, None)
        chatbot_id = self.socket_chatbots.pop(websocket, None)

        if session_id and self.active_sessions.get(session_id) == websocket:
            self.active_sessions.pop(session_id, None)

        if chatbot_id and chatbot_id in self.active_connections:
            self.active_connections[chatbot_id].discard(websocket)
            if not self.active_connections[chatbot_id]:
                self.active_connections.pop(chatbot_id, None)

        logger.debug(f"[WS] Disconnected socket. Session: {session_id}, Chatbot: {chatbot_id}")

    async def safe_send_json(self, websocket: WebSocket, data: dict) -> bool:
        """Safely send a JSON message to a specific websocket, checking its state."""
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(data)
                return True
        except Exception as e:
            logger.warning(f"[WS] Safe send JSON failed: {e}")
            self.disconnect_socket(websocket)
        return False

    async def safe_send_text(self, websocket: WebSocket, text: str) -> bool:
        """Safely send a text message to a specific websocket, checking its state."""
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_text(text)
                return True
        except Exception as e:
            logger.warning(f"[WS] Safe send text failed: {e}")
            self.disconnect_socket(websocket)
        return False

    async def broadcast_to_chatbot(self, chatbot_id: int, message: str | dict):
        """Send a message to all active connections for a specific chatbot safely."""
        if chatbot_id not in self.active_connections:
            return

        dead_connections = []
        # Copy set to avoid mutation during iteration
        for connection in list(self.active_connections[chatbot_id]):
            success = False
            if isinstance(message, dict):
                success = await self.safe_send_json(connection, message)
            else:
                success = await self.safe_send_text(connection, message)
            if not success:
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect_socket(dead)

manager = WebSocketManager()

