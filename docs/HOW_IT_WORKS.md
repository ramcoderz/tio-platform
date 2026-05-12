# How TiO Works — Technical Deep Dive

TiO (Technical Intelligence Orchestrator) is a sophisticated RAG (Retrieval-Augmented Generation) system designed for high-fidelity grounding. This document explains the lifecycle of a message within the platform.

## 1. Knowledge Ingestion Phase
When a website URL or document is added to TiO:
- **Scraping/Parsing**: The system uses specialized loaders to extract clean text from HTML or files (PDF, TXT, MD).
- **Chunking**: Text is split into semantically meaningful blocks using recursive character splitting, ensuring context is preserved across boundaries.
- **Vectorization**: Chunks are converted into high-dimensional embeddings using a local embedding model (or cloud API).
- **Persistence**: Embeddings are stored in **ChromaDB** with metadata linking back to the original source.

## 2. Intent Detection & Routing
When a user sends a message:
- **Domain Detection**: The `DomainDetector` analyzes the initial site context to classify the bot's expertise (e.g., Medical, Tourism).
- **Intent Analysis**: The **Orchestrator Agent** evaluates the user's query to determine if it's a general question, a request for a specific skill (via slash commands), or a retrieval-heavy query.

## 3. Hybrid Retrieval Process
TiO does not rely on simple vector search alone:
- **Semantic Search**: Finds chunks that are conceptually related to the query.
- **Keyword Filtering**: Ensures proper nouns and specific entities from the query are present in the results.
- **Re-ranking**: The most relevant context is prioritized to fit within the LLM's context window.

## 4. Grounded Generation (The Orchestrator)
The LLM (Gemini 3 / Llama 3) receives a strictly formatted prompt:
- **Behavior Profile**: Applies the tone and rules for the detected domain.
- **Context Blocks**: The retrieved document snippets are provided as "Ground Truth."
- **Entity Rules**: Strictly forbids placeholders like `[Location]` and enforces the use of actual names found in the context.

## 5. Streaming & Feedback
- **WebSocket Delivery**: Responses are streamed token-by-token to the UI for low perceived latency.
- **Citations**: Sources are automatically mapped to the response, allowing users to verify the information.
- **Monitoring**: The event is logged in the **Admin Intelligence** collector for real-time performance tracking.
