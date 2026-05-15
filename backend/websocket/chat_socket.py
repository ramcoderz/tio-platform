"""
WebSocket chat handler — enforces strict session + chatbot isolation.

Improvements:
  - chatbot_id required on first message; enforced throughout session
  - session_id + chatbot_id jointly scope every conversation
  - goal memory cleared on disconnect
  - final message includes confidence + goal metadata
  - sends 'done' signal so frontend knows stream is complete
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from backend.agents.orchestrator_agent import run_orchestration_stream
from backend.db.session import SessionLocal
from backend.memory.service import get_or_create_conversation, add_message, get_all_history
from backend.rag.safety import sanitize_input
from backend.models.entities import Conversation, Chatbot
from backend.utils.auth import decode_token
from backend.utils.goal_memory import get_or_create_goal, clear_goal
from backend.config.settings import get_settings
from sqlalchemy import select
import json
import logging

logger = logging.getLogger(__name__)
from backend.utils.console import console
settings = get_settings()

websocket_router = APIRouter()


def _extract_user_id_from_token(token: str | None) -> int | None:
    """Decode JWT and return user_id, or None if invalid/missing."""
    if not token:
        return None
    try:
        payload = decode_token(token)
        return payload.get("uid")
    except Exception:
        return None


@websocket_router.websocket("/ws/chat/{session_id}")
@websocket_router.websocket("/ws/{session_id}")
async def chat_socket(
    websocket: WebSocket,
    session_id: str,
    token: str | None = Query(default=None),
):
    await websocket.accept()
    console.info(f"Websocket connected: {session_id}")

    # In-memory state for this socket connection
    history: list[dict] = []
    locked_chatbot_id: int | None = None   # locked after first message
    user_id = _extract_user_id_from_token(token)

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "content": "Invalid JSON payload."})
                continue

            message = sanitize_input(data.get("message", "").strip())
            if not message:
                continue

            # Accept token from payload as fallback
            if not user_id and data.get("token"):
                user_id = _extract_user_id_from_token(data["token"])

            # Security: block prompt injection attempts
            if "[SECURITY ALERT]" in message:
                console.critical(f"Security Alert: Blocked prompt injection attempt from {session_id}")
                await websocket.send_json({"type": "error", "content": "Message rejected for security reasons."})
                continue

            # --- STRICT CHATBOT LOCKING ---
            # The first message MUST supply chatbot_id.
            # After that, the socket is locked to that chatbot_id.
            incoming_chatbot_id = data.get("chatbot_id")
            if locked_chatbot_id is None:
                if not incoming_chatbot_id:
                    await websocket.send_json({
                        "type": "error",
                        "content": "chatbot_id is required on the first message."
                    })
                    continue
                locked_chatbot_id = incoming_chatbot_id
                # Register with manager
                from backend.api.websocket_manager import manager
                # Note: manager.connect usually calls accept(), but we already did it
                if locked_chatbot_id not in manager.active_connections:
                    manager.active_connections[locked_chatbot_id] = set()
                manager.active_connections[locked_chatbot_id].add(websocket)
                
                console.info(f"Session locked to chatbot_id={locked_chatbot_id}", stage="WS")
            elif incoming_chatbot_id and incoming_chatbot_id != locked_chatbot_id:
                console.critical(
                    f"Cross-session contamination attempt blocked!\n"
                    f"       Session: {session_id}\n"
                    f"       Locked to: {locked_chatbot_id}\n"
                    f"       Attempted: {incoming_chatbot_id}"
                )
                await websocket.send_json({
                    "type": "error",
                    "content": "Session is already bound to a different chatbot. Start a new session to switch."
                })
                continue

            async with SessionLocal() as db:
                # Get or create conversation — strictly scoped to session_id + chatbot_id
                conv = await get_or_create_conversation(
                    db, session_id, locked_chatbot_id, user_id=user_id
                )

                if not conv:
                    await websocket.send_json({
                        "type": "error",
                        "content": "Could not create or find conversation."
                    })
                    continue

                # Validate chatbot exists and belongs to user
                chatbot = await db.get(Chatbot, locked_chatbot_id)
                if not chatbot or (chatbot.user_id and chatbot.user_id != user_id):
                    await websocket.send_json({
                        "type": "error",
                        "content": f"Chatbot {locked_chatbot_id} not found or access denied."
                    })
                    locked_chatbot_id = None # Reset lock
                    continue

                # Load history from DB on first message only
                if not history:
                    history = await get_all_history(db, conv.id)
                    logger.debug(f"[WS] Loaded {len(history)} history messages for session={session_id}")

                # Persist user message
                await add_message(db, conv.id, "user", message)
                history.append({"role": "user", "content": message})

                full_answer = ""
                citations = []
                confidence = 0.0
                goal_text = None
                conversation_mode = "exploratory"

                try:
                    async for chunk_data in run_orchestration_stream(
                        message, history, db,
                        chatbot_id=locked_chatbot_id,
                        session_id=session_id,
                    ):
                        ctype = chunk_data.get("type")

                        if ctype == "metadata":
                            citations = chunk_data.get("citations", [])
                            confidence = chunk_data.get("confidence", 0.0)
                            goal_text = chunk_data.get("goal")
                            conversation_mode = chunk_data.get("conversation_mode", "exploratory")
                            await websocket.send_json(chunk_data)

                        elif ctype == "token":
                            content = chunk_data.get("content", "")
                            full_answer += content
                            await websocket.send_json({"type": "token", "content": content})

                        elif ctype == "thought":
                            await websocket.send_json(chunk_data)

                        elif ctype == "error":
                            await websocket.send_json(chunk_data)
                            break

                except Exception as e:
                    logger.error(f"[WS] Orchestration error session={session_id}: {e}", exc_info=True)
                    await websocket.send_json({"type": "error", "content": "Internal error during response generation."})
                    break

                # Persist assistant message
                if full_answer:
                    await add_message(db, conv.id, "assistant", full_answer, citations, confidence)
                    history.append({"role": "assistant", "content": full_answer})

            # Send final signal
            await websocket.send_json({
                "type": "final",
                "answer": full_answer,
                "citations": citations,
                "confidence": confidence,
                "goal": goal_text,
                "conversation_mode": conversation_mode,
            })

    except WebSocketDisconnect:
        console.warning(f"Websocket disconnected: {session_id}")
        if locked_chatbot_id:
            from backend.api.websocket_manager import manager
            manager.disconnect(websocket, locked_chatbot_id)
        # Clean up in-memory goal state on disconnect
        clear_goal(session_id, locked_chatbot_id)

    except Exception as e:
        logger.error(f"[WS] Unhandled error session={session_id}: {e}", exc_info=True)
        if locked_chatbot_id:
            from backend.api.websocket_manager import manager
            manager.disconnect(websocket, locked_chatbot_id)
        clear_goal(session_id, locked_chatbot_id)
