from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.agents.orchestrator_agent import run_orchestration_stream
from backend.db.session import SessionLocal
import json
from backend.utils.cache import semantic_cache

websocket_router = APIRouter()

@websocket_router.websocket("/ws/chat/{session_id}")
@websocket_router.websocket("/ws/{session_id}")
async def chat_socket(websocket: WebSocket, session_id: str):
    await websocket.accept()
    history = []
    
    try:
        while True:
            raw_data = await websocket.receive_text()
            print(f"DEBUG: Received WS data: {raw_data}")
            data = json.loads(raw_data)
            message = data.get("message", "")
            async with SessionLocal() as db:
                from backend.memory.service import conversation, add_message, get_all_history
                conv = await conversation(db, session_id)
                
                # Update local history from DB if it's the first message in this socket session
                if not history:
                    history = await get_all_history(db, conv.id)
                
                await add_message(db, conv.id, "user", message, {}, 0.0)
                history.append({"role": "user", "content": message})
                
                # Initialize state for this message turn
                full_answer = ""
                citations = []
                intent = "simple"
                
                print(f"DEBUG: Starting orchestration stream for session {session_id}")
                await semantic_cache.set(f"streaming:{session_id}", True, ttl=60)
                try:
                    async for chunk_data in run_orchestration_stream(message, history, db, session_id=session_id):
                        if chunk_data["type"] == "metadata":
                            citations = chunk_data.get("citations", [])
                            intent = chunk_data.get("intent", intent)
                            await websocket.send_json(chunk_data)
                        elif chunk_data["type"] == "thinking":
                            await websocket.send_json(chunk_data)
                        elif chunk_data["type"] == "token":
                            content = chunk_data["content"]
                            full_answer += content
                            await websocket.send_json({"type": "token", "content": content})
                except WebSocketDisconnect:
                    print(f"INFO: WebSocket disconnected during stream for {session_id}")
                    return
                except Exception as e:
                    print(f"ERROR in orchestration stream: {e}")
                    try:
                        await websocket.send_json({"error": str(e)})
                    except: pass
                    break
                finally:
                    await semantic_cache.set(f"streaming:{session_id}", False)
                
                # Save assistant response to DB
                await add_message(db, conv.id, "assistant", full_answer, citations, 1.0)
            
            # Send final to mark completion and share metadata
            if 'full_answer' in locals():
                await websocket.send_json({
                    "type": "final",
                    "answer": full_answer,
                    "citations": citations,
                    "confidence": 1.0, 
                    "intent": intent,
                    "needs_clarification": False
                })
                history.append({"role": "assistant", "content": full_answer})
            else:
                 await websocket.send_json({"type": "final", "answer": "Session interrupted.", "intent": "error"})
    except WebSocketDisconnect:
        return
    finally:
        await semantic_cache.set(f"streaming:{session_id}", False)
