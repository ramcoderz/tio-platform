import logging
import json
from typing import Any, Dict
from backend.api.websocket_manager import manager

logger = logging.getLogger(__name__)

async def broadcast_ingestion_event(chatbot_id: int, event_type: str, data: Dict[str, Any]):
    """
    Broadcasts an ingestion event via WebSocket to all connected clients for a chatbot.
    Event types: progress | complete | failure
    """
    payload = {
        "type": "ingestion_event",
        "chatbot_id": chatbot_id,
        "event": event_type,
        "data": data
    }
    
    # Also include the chatbot status_json if provided for UI consistency
    if "status_json" in data:
        payload["status_json"] = data["status_json"]
        
    try:
        await manager.broadcast_to_chatbot(chatbot_id, json.dumps(payload))
        logger.debug(f"[WS] Broadcasted {event_type} for chatbot {chatbot_id}")
    except Exception as e:
        # Don't let WS failures break the ingestion pipeline
        logger.warning(f"[WS] Failed to broadcast event: {e}")
