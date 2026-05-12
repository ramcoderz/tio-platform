# TiO — Context-Aware Chatbot Builder

> **Transform any website into a domain-aware conversational assistant using Retrieval-Augmented Generation, local LLM inference, and adaptive behavior profiles.**

---

## Why TiO Exists

Most chatbot implementations fall into one of two traps:

1. **Generic LLM wrappers** — They call GPT or Claude directly with no grounding. The model answers from pre-trained knowledge, hallucinating freely when asked about a specific organization, product, or service.
2. **Simple document Q&A** — They chunk a single PDF and do basic vector search. They lack domain awareness, fail on multi-source questions, and produce disconnected answers.

TiO is neither. It is a **retrieval-first, domain-adaptive chatbot builder**. You give it a URL. It crawls the website, parses its documents, builds a hybrid retrieval index, and generates a chatbot that:

- Grounds every answer in the actual website content
- Adapts its tone and behavior to the detected domain (education, medical, tourism, etc.)
- Provides structured workflow assistance via domain-specific skills
- Streams responses token-by-token from a locally running LLM
- Maintains isolated, per-user conversation history across devices

No cloud API dependencies. No training. No configuration. Paste a URL and the chatbot is ready.

---

## Problem Statement

| Problem | How it manifests | TiO's approach |
|---------|-----------------|---------------|
| Generic responses | "What courses do you offer?" → model guesses | Retrieval from crawled course pages |
| No domain awareness | Medical site chatbot behaves like a retail assistant | Auto-detected domain + behavior profile |
| Weak document grounding | PDF chatbot ignores linked resources | Multi-source ingestion (site + PDFs + DOCX) |
| Privacy risk | API keys, user queries sent to cloud | 100% local inference via Ollama |
| No workflow support | Can only answer Q&A, not guide workflows | Domain skills (Trip Planner, Course Finder, etc.) |
| Shared history | All users see the same conversation | Per-user, per-chatbot session isolation |

---

## System Overview

```
┌──────────────────────────────────────────────────┐
│              User provides a URL                  │
└─────────────────────┬────────────────────────────┘
                      │
           ┌──────────▼──────────┐
           │   Secure Ingestion   │
           │  (crawl + validate)  │
           └──────────┬──────────┘
                      │
           ┌──────────▼──────────┐
           │  Semantic Chunking   │
           │ (400-700 tokens, sec-│
           │  tion-aware split)  │
           └──────────┬──────────┘
                      │
           ┌──────────▼──────────┐
           │  Hybrid Retrieval   │
           │  ChromaDB (dense)   │
           │  + BM25 (sparse)    │
           │  + RRF fusion       │
           └──────────┬──────────┘
                      │
           ┌──────────▼──────────┐
           │  Behavior Profile   │
           │  (domain-detected)  │
           └──────────┬──────────┘
                      │
           ┌──────────▼──────────┐
           │  Intent Routing     │
           │  (keyword + semantic│
           │   skill selection)  │
           └──────────┬──────────┘
           │
           ┌──────────▼──────────┐
           │  Prompt Assembly    │
           │  profile + history  │
           │  + chunks + query   │
           └──────────┬──────────┘
                      │
           ┌──────────▼──────────┐
           │  Ollama Inference   │
           │  (streaming output) │
           └──────────┬──────────┘
                      │
           ┌──────────▼──────────┐
           │  Validated Answer   │
           │  + citations sent   │
           │  via WebSocket      │
           └─────────────────────┘
```

---

## Key Features

### Ingestion
- **Deep web crawling** — follows internal links up to 2 levels deep, prioritising content-rich paths (`/departments`, `/faculty`, `/services`, `/reviews`)
- **Multi-format document parsing** — auto-discovers and ingests linked PDF, DOCX, TXT, and Markdown files from crawled pages
- **Secure ingestion pipeline** — MIME validation, 25MB file cap, isolated temp storage, automatic cleanup

### Retrieval
- **Hybrid RAG** — combines ChromaDB dense vector search with BM25 sparse retrieval, fused via Reciprocal Rank Fusion (RRF) for high precision across both semantic and exact matches.
- **Lightweight Intent Routing** — detects user intent (planner, finder, summarizer) to activate domain-specific skills and behavior rules.
- **Section-Aware Chunking** — splits text at natural paragraph and heading boundaries with a target of 400–700 tokens for optimal contextual retrieval.

### Experience
- **5 Primary Domains** — specialized behavior for Education, Medical, Tourism, Developer, and Ecommerce sites.
- **Proactive Behavior** — system makes reasonable assumptions and provides recommendations rather than asking for clarification.
- **Embeddable Widget** — floating, mobile-responsive chat widget with token streaming and isolated sessions for external site integration.
- **Live Monitoring** — admin dashboard with query analytics, latency tracking, and unanswered query logs.

### Domain Intelligence
- **Auto domain detection** — classifies websites into 5 domains: `tourism`, `education`, `medical`, `developer`, `ecommerce` (with `general` fallback).
- **Behavior Profiles** — unique system prompts, proactive recommendation styles, and domain-specific quick actions for each category.aded into the system prompt
- **Domain-adaptive UI** — quick action chips in the chat interface change based on the chatbot's detected domain

### Skills System
- **Tourism Planner** — generates a full itinerary using website offerings + real-time web search
- **Course Finder** — maps career goals to available programs from the ingested content
- **Department Navigator** — routes medical queries to the appropriate department
- **API Assistant** — generates integration code snippets from developer documentation
- **Doc Summarizer** — cross-document synthesis across all ingested content

### Chat & UX
- **WebSocket streaming** — token-by-token response rendering, no full-page waits
- **Voice input** — Web Speech API integration for hands-free queries
- **Source citations** — retrieved chunks shown in a slide-in panel
- **Chat export** — download conversation as PDF, Markdown, or DOCX
- **Per-user history** — `session_id` is deterministically derived from `user_id + chatbot_id`, scoped in the database

### Safety
- **PII masking** — regex-based redaction of emails, phone numbers, SSNs, and credit cards before they enter the prompt
- **Prompt injection detection** — rejects messages matching known injection patterns
- **Output sanitization** — strips system instruction leakage from model responses
- **JWT auth** — bcrypt password hashing, 30-minute inactivity timeout

### Admin
- System-wide stats: total chatbots, documents, messages, conversations
- Per-document management: list, delete, view
- Data purge controls with confirmation
- System config key-value store

---

## Architecture

```
tio/
├── backend/
│   ├── agents/
│   │   ├── orchestrator_agent.py     # Main query pipeline
│   │   ├── specialized_agents.py     # 5 domain skills
│   │   ├── retrieval_agent.py        # RAG retrieval wrapper
│   │   ├── web_search_agent.py       # DuckDuckGo for skills
│   │   ├── query_refinement_agent.py # Query rewriting
│   │   ├── validation_agent.py       # Confidence scoring
│   │   ├── memory_agent.py           # Session memory
│   │   ├── relationship_agent.py     # Cross-doc entity linking
│   │   └── reasoning_agent.py        # Chain-of-thought wrapper
│   ├── api/
│   │   ├── router.py                 # All REST endpoints
│   │   ├── auth.py                   # Register / login / me
│   │   ├── export.py                 # Chat export (PDF/MD/DOCX)
│   │   ├── audit.py                  # Audit log endpoints
│   │   └── tasks.py                  # Task management
│   ├── config/settings.py            # Pydantic env config
│   ├── db/
│   │   ├── session.py                # Async SQLAlchemy session
│   │   ├── seed.py                   # Starter data on boot
│   │   └── migrate.py                # Schema migration helpers
│   ├── ingestion/
│   │   ├── scraper.py                # Recursive web crawler
│   │   └── service.py                # Full ingestion pipeline
│   ├── llm/
│   │   ├── ollama_client.py          # Local LLM generate + stream
│   │   └── profiles.py               # 8 domain behavior profiles
│   ├── memory/service.py             # Conversation CRUD
│   ├── models/entities.py            # SQLAlchemy ORM models
│   ├── orchestration/graph.py        # Agent coordination
│   ├── rag/
│   │   ├── safety.py                 # PII + injection + output
│   │   ├── embeddings.py             # Chunking + embedding
│   │   ├── raptor.py                 # Hierarchical summarization
│   │   ├── iterative_refinement.py   # Multi-step query expansion
│   │   └── types.py                  # Shared type definitions
│   ├── tasks/document_cleanup.py     # Background temp file cleanup
│   ├── utils/
│   │   ├── cache.py                  # Redis + in-memory fallback
│   │   ├── auth.py                   # JWT helpers
│   │   └── audit.py                  # Audit log writer
│   ├── validation/validator.py       # Answer confidence scoring
│   ├── vectorstore/service.py        # ChromaDB + BM25 hybrid
│   ├── websocket/chat_socket.py      # Streaming WebSocket
│   └── main.py                       # FastAPI app entry point
│
├── frontend/src/
│   ├── components/
│   │   ├── AppShell.jsx              # Sidebar + nav + mobile drawer
│   │   └── SkillsMenu.jsx            # Domain-filtered skill picker
│   ├── context/AppContext.jsx        # Auth + theme + inactivity timer
│   ├── pages/
│   │   ├── LoginPage.jsx
│   │   ├── RegisterPage.jsx
│   │   ├── HomePage.jsx              # Dashboard + chatbot cards
│   │   ├── CreateChatbotPage.jsx     # 2-step create + progress bar
│   │   ├── ChatPage.jsx              # Full chat UI
│   │   ├── FilesPage.jsx             # Document management
│   │   ├── AdminPage.jsx             # Stats + controls
│   │   └── SettingsPage.jsx
│   ├── store.js                      # Zustand state
│   ├── api.js                        # Fetch wrapper + JWT
│   └── styles.css                    # Token-based CSS design system
│
├── .env.example
├── requirements.txt
├── start.bat
└── README.md
```

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend framework | FastAPI | Async-native, WebSocket support, fast |
| ORM | SQLAlchemy (async) + aiosqlite | Non-blocking database access |
| Vector store | ChromaDB | Lightweight, local, no infra overhead |
| Keyword search | rank-bm25 | Classic sparse retrieval, zero dependencies |
| Embeddings | sentence-transformers | Local, no API key, good multilingual support |
| LLM runtime | Ollama | Run any open model locally (llama3.2, mistral, etc.) |
| Web scraping | trafilatura | Best-in-class HTML content extraction |
| Auth | python-jose + passlib | JWT + bcrypt, standard stack |
| Frontend | React 18 + Vite | Fast builds, component-based |
| State | Zustand | Minimal, no boilerplate |
| Animations | Framer Motion | Smooth UI transitions |
| Styling | Vanilla CSS (token system) | No build-time dependencies, full control |
| Export | fpdf2 + python-docx | PDF and DOCX generation |
| Real-time | WebSocket (FastAPI) | Token streaming without SSE complexity |
| Cache | Redis (optional) + in-memory fallback | Query deduplication, session cache |

---

## RAG Pipeline — How It Works

```
User Query
    │
    ├─ [Safety] PII masking + injection detection
    │
    ├─ [Refinement] Rewrite ambiguous/short queries
    │      e.g. "fees?" → "What are the course fees for B.Tech programs?"
    │
    ├─ [Retrieval — Hybrid]
    │      Dense:  ChromaDB cosine similarity (top-k × 2)
    │      Sparse: BM25 term frequency (top-k × 2)
    │      Fusion: Reciprocal Rank Fusion → top-k final chunks
    │
    ├─ [Profile] Load domain behavior profile
    │      Sets: persona, tone, restrictions, starter instructions
    │
    ├─ [Prompt Assembly]
    │      system_prompt = profile instructions
    │      context      = retrieved chunks (with source metadata)
    │      history      = last N messages
    │      user_message = refined query
    │
    ├─ [Generation] Ollama streams tokens
    │
    ├─ [Validation] Confidence score against retrieved chunks
    │      Low confidence → graceful fallback message
    │
    └─ [Output Safety] Strip instruction leakage
           → Stream to frontend via WebSocket
```

**Chunk strategy:** 512 tokens with 64-token overlap. Overlap preserves sentence continuity across chunk boundaries, which materially improves retrieval on structured content (tables, lists, numbered items).

---

## Domain Intelligence

TiO classifies each ingested website into one of 8 domains based on keyword signals in the scraped content:

| Domain | Signals | Behavior Profile |
|--------|---------|-----------------|
| `education` | courses, admission, faculty, syllabus | Academic advisor tone, structured guidance |
| `medical` | symptoms, doctor, hospital, appointment | Cautious, factual, always recommends professional consultation |
| `tourism` | hotel, travel, itinerary, attraction | Enthusiastic, practical, itinerary-oriented |
| `developer` | API, documentation, SDK, endpoint | Technical, code-snippet-ready, precise |
| `ecommerce` | product, price, cart, shipping | Sales-aware, helpful, feature-comparison capable |
| `realestate` | property, rent, mortgage, listing | Neutral, detail-oriented, comparison-ready |
| `legal` | law, contract, compliance, regulation | Conservative, always recommends legal counsel |
| `general` | (default) | Balanced, informational, neutral |

Each profile is a structured dictionary defining: persona description, response tone, prohibited topics, fallback message, and skill eligibility.

---

## Skills System

Skills are **bounded workflow helpers** — not autonomous agents. They execute a structured prompt against retrieved context to produce a structured output for a specific user workflow.

| Skill | Domain | Input | Output |
|-------|--------|-------|--------|
| `tourism_planner` | tourism | Destination name | Day-by-day itinerary |
| `course_finder` | education | Career goal | Matching courses + requirements |
| `dept_navigator` | medical | Symptom description | Department recommendation |
| `api_assistant` | developer | Integration goal | Code snippet + explanation |
| `doc_summarizer` | all | (none — uses all docs) | Key points synthesis |

Skills are invoked explicitly by the user via the `+` menu in the chat interface. Each skill call is saved to conversation history and supports the same streaming pipeline as regular chat.

---

## Security & Safe Ingestion

### Input Validation
- Only `PDF`, `DOCX`, `TXT`, and `MD` file types are accepted
- MIME type validated against allowlist (extension alone is not trusted)
- Maximum file size: **25MB**
- Files downloaded to an isolated temp directory, cleaned after parsing

### Crawling Limits
- Maximum pages per site: **50**
- Maximum crawl depth: **2 levels**
- Only internal links followed (no cross-domain crawling)
- Timeout enforced on each fetch

### Prompt Safety
- PII patterns detected and masked before entering the model: email, phone, SSN (US), credit card (Luhn-compatible regex)
- Injection patterns blocked: "ignore previous", "you are now", "disregard your instructions", etc.
- System prompt content is not echoed in outputs (output sanitizer strips known leakage phrases)

---

## API Reference

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/register` | Create account |
| `POST` | `/api/auth/login` | Get JWT token |
| `GET` | `/api/auth/me` | Get current user |

### Chatbots
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/chatbots` | List all chatbots |
| `POST` | `/api/chatbots` | Create + trigger ingestion |
| `GET` | `/api/chatbots/{id}` | Get chatbot details |
| `DELETE` | `/api/chatbots/{id}` | Delete chatbot + vectors |
| `POST` | `/api/chatbots/{id}/upload` | Upload document |
| `GET` | `/api/chatbots/{id}/files` | List documents |

### Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat` | HTTP chat (fallback) |
| `GET` | `/api/chat/history/{session_id}` | Load conversation history |
| `GET` | `/api/chat/export/{session_id}?format=pdf\|md\|docx` | Export conversation |
| `WS` | `/ws/chat/{session_id}?token=...` | Streaming chat |

### Skills
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/skills/execute` | Run a domain skill |

### Admin
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/admin/stats` | System-wide metrics |
| `GET` | `/api/admin/documents` | All documents |
| `DELETE` | `/api/admin/documents/{id}` | Delete document |
| `POST` | `/api/admin/cleanup/all` | Purge all data |
| `GET/POST` | `/api/admin/config/{key}` | System config |

---

## Example Use Cases

**University website** — Students ask about admission requirements, fees, course offerings. The chatbot pulls from crawled department pages and linked PDFs, answers with citations, and uses the Course Finder skill to map career goals to programs.

**Hospital portal** — Patients describe symptoms. The Department Navigator skill routes them to the correct department. The chatbot answers from the hospital's actual service descriptions, not from general medical knowledge.

**Tourism operator** — Visitors ask about packages, activities, and pricing. The Tourism Planner skill generates a full itinerary using the site's offerings combined with a web search for reviews.

**SaaS documentation** — Developers ask API integration questions. The API Assistant skill generates working code snippets grounded in the product's actual documentation.

---

## Current MVP Scope

The current build is a functional MVP focused on:

- ✅ Single-user chatbot creation from a URL
- ✅ Hybrid RAG with domain awareness
- ✅ 5 domain skills
- ✅ Local inference (Ollama)
- ✅ JWT auth with per-user session isolation
- ✅ Admin controls and chat export
- ✅ Production build (zero compile errors)

---

## Honest Limitations

- **Dynamic websites** — JavaScript-rendered sites (SPAs, React apps) are not fully supported. Trafilatura fetches raw HTML; content that requires JS execution will not be scraped. Playwright integration is on the roadmap.
- **Domain detection is heuristic** — It works on keyword frequency in crawled content. Low-content pages or unusual domain language may be misclassified.
- **Retrieval quality follows source quality** — If the website has thin, vague, or poorly structured content, the chatbot's answers will reflect that. Garbage in, garbage out.
- **Local LLM capability ceiling** — Responses are bounded by the capability of the locally running model. Larger models produce better results but require more VRAM/RAM.
- **No real-time data** — The chatbot answers from the ingestion snapshot. If the website changes, the chatbot won't know until re-ingested.
- **Not a decision-making system** — TiO is a conversational information retrieval tool. It is not designed to take actions, make purchases, book appointments, or execute external API calls autonomously.

---

## Local Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- [Ollama](https://ollama.com/) installed and running

```bash
# Pull a model (llama3.2 recommended for balance of speed + quality)
ollama pull llama3.2
ollama serve
```

### Backend Setup

```bash
# Clone the repository
git clone https://github.com/your-username/tio.git
cd tio

# Create virtual environment
python -m venv venv
source venv/bin/activate      # Linux/macOS
venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment config
cp .env.example .env
# Edit .env with your values
```

### Frontend Setup

```bash
cd frontend
npm install
npm run build     # Production
# or
npm run dev       # Development (hot reload on port 5173)
```

### Run the Server

```bash
# From project root
uvicorn backend.main:app --host 0.0.0.0 --port 8888 --reload
```

Open `http://localhost:8888`

### Windows Quick Start

```bat
.\start.bat
```

---

## Environment Variables

Copy `.env.example` to `.env` and set:

```env
# LLM
OLLAMA_MODEL=llama3.2
OLLAMA_BASE_URL=http://localhost:11434

# Auth
JWT_SECRET=your-secret-key-change-this
JWT_EXPIRE_MINUTES=1440

# Database
DATABASE_URL=sqlite+aiosqlite:///./data/tio.db

# Vector Store
CHROMA_DIR=./data/chroma

# File Storage
UPLOAD_DIR=./data/uploads
MAX_FILE_SIZE_MB=25

# Cache (optional — falls back to in-memory if Redis not running)
REDIS_URL=redis://localhost:6379
```

> **Never commit `.env` to version control.** It is listed in `.gitignore`.

---

## Future Improvements

Ordered by priority and realistic feasibility:

1. **Intent-based skill routing** — classify query intent to auto-invoke the right skill without manual selection
2. **Playwright scraper** — replace trafilatura with a headless browser for JS-rendered sites
3. **Embeddable widget** — `<script>` tag / iframe deployment for external websites
4. **Scheduled re-ingestion** — background cron to keep the knowledge base current
5. **Multi-language support** — multilingual embeddings + language-aware prompting
6. **Analytics** — query volume, confidence trends, unanswered question tracking
7. **LoRA fine-tuning pipeline** — use conversation data to fine-tune domain adapters
8. **Multi-user workspaces** — admin / editor / viewer roles per chatbot
9. **Public API layer** — API key auth for programmatic access to chatbots
10. **Federated knowledge** — link multiple websites to a single chatbot

---

## Deployment Notes

- The backend serves the built frontend from `frontend/dist/` — a single process handles both
- SQLite is suitable for single-server deployments with low to medium traffic
- For higher load: swap SQLite for PostgreSQL (change `DATABASE_URL`; schema is compatible)
- ChromaDB data lives in `data/chroma/` — back this up if you care about persistence
- The `data/` directory (DB + uploads + vectors) is excluded from git; set up persistent storage in production
- CORS is configured permissively for local development; restrict `allow_origins` in `main.py` before deploying publicly

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make changes — keep them focused (one feature or fix per PR)
4. Ensure the backend starts without errors and the frontend builds cleanly
5. Open a pull request with a clear description of what changed and why

**Code style:**
- Python: follow PEP 8, async throughout, type hints where practical
- JavaScript: functional components, no class components, Zustand for shared state
- CSS: use existing CSS variable tokens, no inline styles for design values

---

## License

MIT License — see `LICENSE` file.

You are free to use, modify, and distribute this project. If you build something with it, a credit or a star is appreciated but not required.

---

## Product Vision

TiO's goal is to be the simplest, most honest path from a website URL to a working, grounded, domain-aware chatbot — without cloud dependencies, without training, and without prompt engineering by the end user.

The long-term direction is a platform where any organisation — a university, a clinic, a local tourism board — can deploy a trustworthy conversational interface over their own content, running entirely on their own infrastructure, with full data ownership.

That's the problem worth solving. This is the starting point.

---

<div align="center">
  Built with FastAPI · ChromaDB · Ollama · React · sentence-transformers
</div>
