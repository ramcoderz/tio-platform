# TiO (Transformer-based Intelligent Orchestration)

Production-ready no-code AI orchestration platform with enterprise RAG, conversational memory, iterative context refinement, and multi-agent orchestration.

## Run
- `pip install -r requirements.txt`
- `cd frontend && npm install && npm run build && cd ..`
- `python main.py`
- Open `http://localhost:8000`

## Performance Tips
- First upload may be slower while `all-MiniLM-L6-v2` downloads.
- Keep Ollama running to avoid cold starts. On unstable GPU systems, run Ollama with CPU fallback (`OLLAMA_LLM_LIBRARY=cpu`).
- Session-aware retrieval and short-lived response caching are enabled for faster repeated queries.

## Core capabilities
- Document ingestion: PDF, DOCX, TXT, CSV, Images + OCR (EasyOCR)
- Embeddings: SentenceTransformers `all-MiniLM-L6-v2`
- Retrieval: FAISS (top-k cosine) + ChromaDB support
- Conversational RAG with iterative chunk-by-chunk refinement
- Multi-agent flow: query refinement, retrieval, reasoning, validation, memory, orchestration
- WebSocket streaming chat with citation-backed responses
- React SPA frontend with chat typing indicator, light/dark theme, and session-aware file context

## Core algorithm
User Query -> Conversation History -> Query Refinement Agent -> Embedding Generation -> Vector Retrieval (Top-K) -> Iterative Context Refinement -> Initial Answer Generation -> Load Next Chunk -> Refine Existing Answer -> Validation Agent -> Final Answer

## Troubleshooting
- Provider health: `GET /api/providers/status`
- End and clean a session explicitly: `DELETE /api/chat/session/{session_id}`
- Upload supports: `.pdf`, `.docx`, `.txt`, `.csv`, `.png`, `.jpg`, `.jpeg`, `.webp`
