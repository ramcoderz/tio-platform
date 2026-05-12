# TiO System Architecture

This document provides a high-level overview of the TiO system architecture, illustrating the flow of data from user input to grounded response.

## System Workflow Diagram

```mermaid
graph TD
    User((User))
    Widget[React Widget / App]
    FastAPI[FastAPI Backend]
    Orchestrator[Orchestrator Agent]
    Detector[Domain Detector]
    Chroma[ChromaDB Vector Store]
    Ollama[Ollama / Gemini 3]
    DB[(SQLite / Postgres)]

    User -->|Message| Widget
    Widget -->|WebSocket / API| FastAPI
    FastAPI -->|Check Context| DB
    FastAPI -->|Initialize| Orchestrator
    
    Orchestrator -->|Analyze Site| Detector
    Detector -->|Classification| Orchestrator
    
    Orchestrator -->|Semantic Query| Chroma
    Chroma -->|Grounded Chunks| Orchestrator
    
    Orchestrator -->|Prompt + Context| Ollama
    Ollama -->|Stream Response| Orchestrator
    
    Orchestrator -->|Final Response| FastAPI
    FastAPI -->|Streaming Tokens| Widget
    Widget -->|Display| User
```

## Core Components

### 1. The Orchestrator
The central brain of the system. It handles conversation state, memory retrieval, and LLM prompting. It is designed to be "domain-aware," meaning it adjusts its logic based on the type of website it is currently serving.

### 2. Domain Intelligence
A specialized utility that classifies the input data into one of several predefined domains (Tourism, Medical, etc.). This classification determines the **Behavior Profile** used by the LLM, ensuring the tone and constraints match the industry standards.

### 3. Vector Retrieval (RAG)
Uses **ChromaDB** to store and retrieve document embeddings. The retrieval process includes filtering and re-ranking to ensure only the most relevant "ground truth" is used for generation.

### 4. Admin Intelligence
A separate monitoring layer that captures logs and system stats without interrupting the main chat flow. It provides a real-time window into the system's operational health.
