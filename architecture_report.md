# TiO Production Architecture Report

TiO has been transformed from a basic RAG chatbot into a **Context-Aware Conversational Copilot Platform**. This report outlines the technical components, techniques, and packages that power the system.

## 1. Intelligence Pipeline (Orchestrator)
The core logic resides in the `orchestrator_agent.py`, which follows a multi-stage reasoning process:

*   **Context Compression**: Before answering, the system synthesizes a "Context Snapshot" from retrieved documents, extracting only key facts to reduce noise.
*   **Response Planning**: It extracts **Goal**, **Workflow**, and **Plan** for every response, ensuring the AI is proactive and follows the site's business logic.
*   **High-Fidelity Grounding**: Uses `spaCy` (NER) to ensure that entities mentioned are grounded in actual retrieved context. It follows a strict "No-Placeholder" policy.
*   **External Research Fallback**: If local retrieval confidence is low (< 0.3), it autonomously triggers `Tavily AI` to perform grounded external research.

## 2. Retrieval & Search Technique
TiO uses a **Hybrid Retrieval** strategy to maximize precision and recall:

*   **Embeddings**: `BAAI/bge-small-en-v1.5` (via SentenceTransformers) for dense semantic search.
*   **Vector Store**: `FAISS` / `ChromaDB` for efficient similarity search.
*   **RRF (Reciprocal Rank Fusion)**: Combines results from vector search and keyword-based search (BM25 logic) to rank the most relevant chunks.
*   **Cross-Encoder Reranking**: Uses `ms-marco-MiniLM-L-6-v2` as a second-stage reranker to score the top candidates for maximum relevance.

## 3. Ingestion & Crawling
The ingestion pipeline is designed for "Website Understanding" rather than just data dumping:

*   **Crawler**: Powered by `Trafilatura` and `Playwright`. It performs intelligent content extraction, prioritizing high-value pages (APIs, Docs, Services) over noise (Legal, Cookies).
*   **Site Profile**: During ingestion, TiO builds a persistent JSON map of the site including:
    *   **Site Summary**: A high-level description of the site's purpose.
    *   **Top Entities**: Key organizations, products, or locations mentioned.
    *   **Mapped Workflows**: Step-by-step processes discovered on the site.
*   **Package Stack**: `beautifulsoup4`, `trafilatura`, `playwright`, `httpx`.

## 4. Multi-Tenancy & Security
The platform is built for production-grade isolation:

*   **User Ownership**: All chatbots and documents are linked to a `user_id`.
*   **Session Scoping**: Conversations are scoped by `user_id` + `chatbot_id` + `session_id`.
*   **Deep Deletion**: A centralized cleanup utility ensures that deleting an account or chatbot purges:
    *   Database records (History, Messages, Metadata).
    *   Physical storage (Uploaded PDF/TXT files).
    *   Vector indexes (Chroma collections).
    *   Session memory (Redis/SQL snapshots).

## 5. Reasoning Transparency & UX
TiO provides deep transparency into its internal decision-making process:

*   **Thought Traces**: Before every response, the `orchestrator_agent.py` yields a `thought` event containing the **Goal**, **Workflow**, and **Logical Plan**. This is rendered as a technical "Neural Reasoning Trace" in the UI.
*   **Multi-Format Export**: Users can download their grounded research histories in:
    *   **PDF**: Formatted document with citations (via `fpdf2`).
    *   **Markdown**: Technical log for research integration.
    *   **Docx**: Business-ready reporting (via `python-docx`).

## 6. Deep Observability
The platform provides administrative tools for real-time RAG analysis:

*   **Context Debugging**: A dedicated `/admin/debug/retrieval` endpoint allows simulating queries to see raw vector scores and chunk metadata.
*   **Auto-Cleanup**: A background worker continuously monitors document TTL (Time-To-Live) and purges expired research snapshots from both the database and vector store.

## 7. Main Packages Used
| Component | Package / Technology |
| :--- | :--- |
| **Backend** | FastAPI, SQLAlchemy, Pydantic |
| **Inference** | Ollama (Local), Tavily (External Fallback) |
| **NLP** | spaCy (en_core_web_sm), SentenceTransformers |
| **Retrieval** | FAISS, ChromaDB, Rank-BM25 |
| **Ingestion** | Trafilatura, Playwright, BeautifulSoup4 |
| **Export** | fpdf2, python-docx |
| **Frontend** | React, Vite, Framer Motion, Lucide Icons |

## 8. Project Structure
*   `backend/agents/`: Intelligence logic and reasoning layers.
*   `backend/api/`: REST endpoints and WebSocket orchestration.
*   `backend/utils/export.py`: Multi-format document generation.
*   `backend/db/migrate.py`: Schema management and migration logic.
*   `frontend/src/pages/`: Operational page hierarchy (Landing, Dashboard, Monitor, Detail).

---
*Report generated for TiO Intelligence Platform - May 2026*
