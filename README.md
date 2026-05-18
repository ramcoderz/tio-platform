# TiO — Context-Aware Chatbot Intelligence

**TiO** (Technical Intelligence Orchestrator) is a professional, context-aware chatbot builder designed to transform websites, documents, and technical documentation into grounded conversational copilots. 

By leveraging **Hybrid RAG**, **Semantic Retrieval**, and **Domain-Aware Intent Routing**, TiO provides high-fidelity responses that are strictly bounded by your provided data, eliminating robotic placeholders and AI hallucinations.

![TiO Dashboard Placeholder](https://via.placeholder.com/1200x600?text=TiO+System+Intelligence+Dashboard)

## 🌟 Core Features

- **Domain-Aware Orchestration**: Automatically detects the context (Tourism, Education, Medical, Developer, Ecommerce) and applies specialized behavior profiles.
- **Hybrid RAG Pipeline**: Combines semantic vector search with keyword-based grounding for maximum retrieval accuracy.
- **Unified Skill System**: Execute specialized workflows (summarization, itinerary planning, API guidance) via intuitive slash commands (`/`).
- **Administrative Intelligence**: Real-time monitoring of system health, ingestion pipelines, and server logs through a premium admin dashboard.
- **Privacy-First Inference**: Support for local inference via Ollama, ensuring your data never leaves your infrastructure.
- **Seamless Integration**: A premium, embeddable React widget that can be dropped into any website in minutes.

## 🏗️ Architecture Overview

TiO is built on a modern, scalable stack designed for reliability and speed:

- **Frontend**: React (Vite) with Framer Motion for premium animations and Lucide-React for iconography.
- **Backend**: FastAPI (Python) with asynchronous database handling and WebSocket streaming.
- **Intelligence**: LangChain-inspired orchestrator with support for local (Ollama) and cloud (Gemini/OpenAI) models.
- **Vector Store**: ChromaDB for high-performance semantic retrieval.
- **Database**: SQLAlchemy with SQLite/PostgreSQL support for session and preference persistence.

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- [Ollama](https://ollama.ai/) (for local inference)

### Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/ramcoderz/tio-platform.git
   cd tio-platform
   ```

2. **Backend Setup**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # venv\Scripts\activate on Windows
   pip install -r requirements.txt
   cp .env.example .env
   ```

3. **Frontend Setup**
   ```bash
   cd ../frontend
   npm install
   ```

4. **Run the Application**
   ```bash
   # From the root directory
   ./start.bat  # Windows
   # OR run separately:
   # Backend: uvicorn backend.main:app --reload
   # Frontend: npm run dev
   ```

## 📂 Repository Structure

- `frontend/`: React application, components, and design system.
- `backend/`: FastAPI application, ingestion service, and orchestrator.
- `docs/`: Technical reports and architecture deep-dives.
- `scripts/`: Utility scripts for database seeding and cleanup.
- `public/`: Static assets and widget distribution files.

## 🛡️ Administrative Security

Access the **System Intelligence Dashboard** at `/admin`. This area is restricted to users with the `admin` role and provides:
- Live streaming server logs.
- Document ingestion monitoring.
- Resource usage and latency tracking.

## 🗺️ Supported Domains

TiO currently includes specialized intelligence for:
- 🏖️ **Tourism**: Itinerary planning and attraction recommendations.
- 🎓 **Education**: Admission guidance and course summaries.
- 🏥 **Medical**: Department navigation and appointment assistance.
- 💻 **Developer**: API documentation and SDK integration support.
- 🛒 **Ecommerce**: Product comparisons and shopping guidance.

## 📝 Roadmap & Future Improvements

- [ ] Multi-tenant organization support.
- [ ] Advanced citation visualization (PDF highlight mapping).
- [ ] Automated A/B testing for retrieval chunking strategies.
- [ ] Native integration with Slack and Discord.

## ⚖️ License & Contributions

This project is licensed under the MIT License. Contributions are welcome! Please read our [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

**Positioning**: TiO is a tool for building grounded conversational copilots. It is not an autonomous general-purpose agent or an AGI system. It is designed to be a reliable partner for document and website grounding.
