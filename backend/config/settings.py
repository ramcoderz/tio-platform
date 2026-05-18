from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "TiO"
    host: str = "0.0.0.0"  # Bind to all interfaces for production
    port: int = 8000
    public_backend_url: str = ""  # Public URL for the backend
    allowed_origins: list[str] = Field(default_factory=lambda: ["*"])
    
    sqlite_url: str = "sqlite+aiosqlite:///./tio.db"
    upload_dir: str = "data/uploads"
    chroma_dir: str = "data/chroma"
    embedding_model: str = "all-MiniLM-L6-v2"
    top_k: int = 3
    chunk_size: int = 2200    # ~550 tokens target (section-aware chunking)
    chunk_overlap: int = 320  # ~80 tokens overlap
    llm_provider: str = "ollama"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b-instruct"
    primary_model: str = "llama3.2:3b-instruct"
    fallback_model: str = "phi3:mini"
    summary_model: str = "qwen2.5:7b-instruct"
    fast_model: str = "phi3:mini"
    openrouter_model: str = "meta-llama/llama-3.1-8b-instruct"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    gemini_model: str = "gemini-1.5-flash"
    gemini_api_key: str = ""
    tavily_api_key: str | None = None
    hf_token: str = ""
    confidence_threshold: float = 0.65
    # Web search augmentation (Task 19)
    web_search_enabled: bool = False                  # set to False to disable during stabilization
    web_search_min_confidence: float = 0.25          # trigger web search below this
    # DEPRECATED: use allowed_origins
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    
    # Stabilization Flags
    local_inference_only: bool = True
    stabilization_mode: bool = True
    max_concurrent_llm_requests: int = 1
    debug_timing: bool = False

    # Feature Flags (Path B Stabilization)
    enable_pdf_parsing: bool = True
    enable_docx_parsing: bool = True
    enable_entity_extraction: bool = True
    enable_reranking: bool = True
    enable_tavily: bool = True
    enable_gemini_search: bool = False
    enable_profile_intelligence: bool = True
    enable_article_summarization: bool = True
    enable_section_aware_chunking: bool = True

    # Phase 12B — Adaptive Retrieval & Knowledge Expansion
    enable_adaptive_retrieval: bool = True
    enable_incremental_ingestion: bool = True
    enable_dynamic_doc_discovery: bool = True

    # Demo Mode — prioritise preloaded embeddings, reduce live crawl dependency
    demo_mode: bool = False
    demo_knowledgebases: list[str] = Field(default_factory=lambda: ["mvit", "nasa", "pondicherry_tourism", "fastapi_docs", "ollama_docs"])

    # Adaptive retrieval thresholds
    adaptive_min_chunks: int = 2          # Trigger expansion below this chunk count
    adaptive_min_rerank_score: float = 0.5  # Trigger expansion below this avg rerank score

    # Security
    jwt_secret_key: str = "super-secret-key-change-this-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours

    # Redis (for semantic caching)
    redis_url: str = "redis://localhost:6379/0"

    # Document Lifecycle
    auto_delete_hours: int = 4


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
