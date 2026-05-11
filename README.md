# TiO — Context-Aware Chatbot Builder

A fast, realistic MVP for building domain-adaptive chatbots from website URLs and documents. TiO focuses on retrieval quality, conversational UX, and privacy-first local orchestration.

## Features
- **URL Ingestion**: Automatically scrape and process website content using semantic extraction.
- **Document Support**: Upload and index PDF, Docx, and TXT files for grounding.
- **Hybrid RAG**: Combined Dense (Vector) and Sparse (Keyword) retrieval for maximum accuracy.
- **Domain Adaptation**: Automatically detects business domains and adapts the assistant's behavior/tone.
- **Local-First**: Powered by Ollama for private, high-speed local inference.
- **Real-time Streaming**: WebSocket-based chat with live citations and source previews.

## 🚀 Quick Start
For a detailed step-by-step guide, see **[RUN_GUIDE.md](file:///d:/Cursor/tio/tio/RUN_GUIDE.md)**.

1. **One-Click (Windows)**: Run `start.bat`
2. **Manual**:
   - `pip install -r requirements.txt`
   - `cd frontend && npm install && npm run build && cd ..`
   - `python main.py`

## Tech Stack
- **Backend**: FastAPI, SQLAlchemy (SQLite), FAISS, BM25, Trafilatura.
- **Frontend**: React, Vite, Framer Motion, Lucide Icons.
- **Intelligence**: SentenceTransformers (Embeddings), Ollama (Inference).

## Sanitization Status
All complex abstractions (GraphRAG, multi-agent flows, marketplaces) have been removed to ensure the platform remains lightweight, stable, and focused on the core RAG value proposition.
