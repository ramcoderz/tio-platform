from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "TiO"
    host: str = "127.0.0.1"
    port: int = 8000
    sqlite_url: str = "sqlite+aiosqlite:///./tio.db"
    upload_dir: str = "data/uploads"
    chroma_dir: str = "data/chroma"
    embedding_model: str = "all-MiniLM-L6-v2"
    top_k: int = 5
    chunk_size: int = 1000
    chunk_overlap: int = 150
    llm_provider: str = "ollama"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    openrouter_model: str = "meta-llama/llama-3.1-8b-instruct"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    gemini_model: str = "gemini-1.5-flash"
    gemini_api_key: str = ""
    confidence_threshold: float = 0.65
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

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
