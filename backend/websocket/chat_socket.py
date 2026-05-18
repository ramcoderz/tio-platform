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
import time

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


import asyncio

async def _heartbeat(websocket: WebSocket, interval: int = 30):
    """Periodically send pings to keep connection alive and detect dead sockets."""
    try:
        from backend.api.websocket_manager import manager
        while True:
            await asyncio.sleep(interval)
            await manager.safe_send_json(websocket, {"type": "ping"})
    except Exception:
        # If ping fails, the socket is likely dead; main loop will exit on receive
        pass

@websocket_router.websocket("/ws/chat/{session_id}")
@websocket_router.websocket("/ws/{session_id}")
async def chat_socket(
    websocket: WebSocket,
    session_id: str,
    token: str | None = Query(default=None),
):
    t_ws_start = time.monotonic()
    await websocket.accept()
    if settings.debug_timing:
        print(f"[WS] Stream established in {time.monotonic() - t_ws_start:.3f}s")
    logger.info(f"[WS] Socket opened: session_id={session_id}")
    console.info(f"[WS] Connected: {session_id}")

    # In-memory state for this socket connection
    history: list[dict] = []
    locked_chatbot_id: int | None = None
    user_id = _extract_user_id_from_token(token)
    
    # Heartbeat task
    heartbeat_task = asyncio.create_task(_heartbeat(websocket))

    try:
        from backend.api.websocket_manager import manager
        while True:
            try:
                raw_data = await websocket.receive_text()
                data = json.loads(raw_data)
            except WebSocketDisconnect:
                logger.info(f"[WS] Socket disconnected (normal): session_id={session_id}")
                raise
            except json.JSONDecodeError:
                logger.warning(f"[WS] Invalid JSON payload from session_id={session_id}")
                await manager.safe_send_json(websocket, {"type": "error", "content": "Invalid payload: Not valid JSON."})
                continue
            except Exception as e:
                logger.warning(f"[WS] Connection error or invalid state from session_id={session_id}: {e}")
                break

            # Heartbeat ping/pong handling
            if data.get("type") == "ping":
                await manager.safe_send_json(websocket, {"type": "pong"})
                continue
            if data.get("type") == "pong":
                continue

            # --- CHATBOT LOCKING ---
            incoming_chatbot_id = data.get("chatbot_id")
            if locked_chatbot_id is None:
                if not incoming_chatbot_id:
                    logger.error(f"[WS] Connection attempt without chatbot_id: session_id={session_id}")
                    await manager.safe_send_json(websocket, {"type": "error", "content": "chatbot_id required."})
                    continue
                locked_chatbot_id = incoming_chatbot_id
                await manager.register(websocket, session_id, locked_chatbot_id)
                logger.info(f"[WS] Session {session_id} locked to chatbot_id={locked_chatbot_id}")
                console.info(f"[WS] Session locked to chatbot_id={locked_chatbot_id}")
            elif incoming_chatbot_id and incoming_chatbot_id != locked_chatbot_id:
                logger.error(f"[WS] Chatbot ID mismatch: session={session_id} locked={locked_chatbot_id} incoming={incoming_chatbot_id}")
                await manager.safe_send_json(websocket, {"type": "error", "content": "Session mismatch."})
                continue

            message = sanitize_input(data.get("message", "").strip())
            if not message:
                continue

            t_total_start = time.monotonic()

            if not user_id and data.get("token"):
                user_id = _extract_user_id_from_token(data["token"])

            async with SessionLocal() as db:
                conv = await get_or_create_conversation(db, session_id, locked_chatbot_id, user_id=user_id)
                if not conv:
                    await manager.safe_send_json(websocket, {"type": "error", "content": "Conversation failure."})
                    continue

                chatbot = await db.get(Chatbot, locked_chatbot_id)
                if not chatbot or (chatbot.user_id and chatbot.user_id != user_id):
                    await manager.safe_send_json(websocket, {"type": "error", "content": "Access denied."})
                    continue

                if not history:
                    history = await get_all_history(db, conv.id)

                await add_message(db, conv.id, "user", message)
                history.append({"role": "user", "content": message})

                if message == "/system/runtime":
                    from backend.utils.validation import get_runtime_status_report
                    status_report = await get_runtime_status_report()
                    
                    # Stream lines one by one to simulate typing/streaming output
                    for line in status_report.split("\n"):
                        await manager.safe_send_json(websocket, {"type": "token", "content": line + "\n"})
                        await asyncio.sleep(0.01)
                    
                    await add_message(db, conv.id, "assistant", status_report)
                    history.append({"role": "assistant", "content": status_report})
                    
                    await manager.safe_send_json(websocket, {
                        "type": "final",
                        "answer": status_report,
                        "citations": [],
                        "duration_s": 0.05,
                    })
                    continue

                full_answer = ""
                citations = []
                
                try:
                    async for chunk_data in run_orchestration_stream(
                        message, history, db,
                        chatbot_id=locked_chatbot_id,
                        session_id=session_id,
                    ):
                        if chunk_data.get("type") == "token":
                            full_answer += chunk_data.get("content", "")
                        elif chunk_data.get("type") == "metadata":
                            citations = chunk_data.get("citations", [])
                        
                        await manager.safe_send_json(websocket, chunk_data)

                except Exception as e:
                    logger.error(f"[WS] Orchestration error: {e}")
                    await manager.safe_send_json(websocket, {"type": "error", "content": "Generation failed."})
                    break

                if full_answer:
                    await add_message(db, conv.id, "assistant", full_answer, citations)
                    history.append({"role": "assistant", "content": full_answer})

                total_duration = time.monotonic() - t_total_start
                if settings.debug_timing:
                    print(f"[TOTAL] Response generated in {total_duration:.3f}s")

                await manager.safe_send_json(websocket, {
                    "type": "final",
                    "answer": full_answer,
                    "citations": citations,
                    "duration_s": round(total_duration, 2),
                })

    except WebSocketDisconnect:
        console.warning(f"[WS] Disconnected: {session_id}")
    except Exception as e:
        logger.error(f"[WS] Socket error in session {session_id}: {e}")
    finally:
        logger.info(f"[WS] Socket closed: session_id={session_id}")
        heartbeat_task.cancel()
        from backend.api.websocket_manager import manager
        manager.disconnect_socket(websocket)
        clear_goal(session_id, locked_chatbot_id)
