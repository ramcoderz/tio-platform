from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.agents.orchestrator_agent import run_orchestration_stream
from backend.db.session import SessionLocal
from backend.memory.service import get_or_create_conversation, get_conversation_by_session, add_message, get_all_history
from backend.rag.safety import sanitize_input
from backend.models.entities import Conversation
from sqlalchemy import select
import json
import logging

logger = logging.getLogger(__name__)

websocket_router = APIRouter()

@websocket_router.websocket("/ws/chat/{session_id}")
@websocket_router.websocket("/ws/{session_id}")
async def chat_socket(websocket: WebSocket, session_id: str):
    await websocket.accept()
    history = []
    
    try:
        while True:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            message = sanitize_input(data.get("message", ""))
            chatbot_id = data.get("chatbot_id")
            
            if "[SECURITY ALERT]" in message:
                await websocket.send_json({"error": "Message rejected for security reasons."})
                continue
            
            async with SessionLocal() as db:
                if chatbot_id:
                    conv = await get_or_create_conversation(db, session_id, chatbot_id)
                else:
                    # Try to find recent conversation for this session
                    # This is a fallback; usually chatbot_id is provided
                    stmt = select(Conversation).where(Conversation.session_id == session_id).order_by(Conversation.created_at.desc())
                    conv = (await db.execute(stmt)).scalars().first()
                
                if not conv:
                    await websocket.send_json({"error": "No active conversation found. Please provide a chatbot_id."})
                    continue
                
                # Update local history from DB if it's the first message in this socket session
                if not history:
                    history = await get_all_history(db, conv.id)
                
                await add_message(db, conv.id, "user", message)
                history.append({"role": "user", "content": message})
                
                full_answer = ""
                citations = []
                
                try:
                    async for chunk_data in run_orchestration_stream(message, history, db, session_id=session_id):
                        if chunk_data["type"] == "metadata":
                            citations = chunk_data.get("citations", [])
                            await websocket.send_json(chunk_data)
                        elif chunk_data["type"] == "token":
                            content = chunk_data["content"]
                            full_answer += content
                            await websocket.send_json({"type": "token", "content": content})
                except Exception as e:
                    await websocket.send_json({"error": str(e)})
                    break
                
                # Save assistant response to DB
                await add_message(db, conv.id, "assistant", full_answer, citations, 1.0)
            
            # Send final
            await websocket.send_json({
                "type": "final",
                "answer": full_answer,
                "citations": citations,
                "confidence": 1.0
            })
            history.append({"role": "assistant", "content": full_answer})
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WS Error for session {session_id}: {e}", exc_info=True)
