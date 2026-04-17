"""Application configuration via Pydantic Settings with env var loading."""

from pydantic_settings import BaseSettings

QDRANT_COLLECTION_NAME = "rag_kb_chunks"

_settings: any = None


class Settings(BaseSettings):
    """Central configuration loaded from environment variables.

    Supports both PostgreSQL and SQLite via the DATABASE_URL variable:
    - PostgreSQL: postgresql+asyncpg://user:pass@host/db
    - SQLite:    sqlite+aiosqlite:///path/to/easyrag.db

    For backward compatibility, POSTGRES_URL is also accepted.
    """

    # Database — supports PostgreSQL and SQLite
    # DATABASE_URL takes priority; POSTGRES_URL is a fallback alias
    database_url: str = ""
    postgres_url: str = ""

    # Vector store
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None

    # Authentication (optional for local dev, required for production)
    api_key: str | None = None

    # LLM provider configuration
    llm_provider: str = "ollama"
    answer_llm_base_url: str = "http://localhost:11434/v1"
    answer_llm_model: str = "llama3.2"
    answer_llm_api_key: str | None = None

    # Embedding and reranker models
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimensions: int = 384
    reranker_model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Storage and limits
    max_upload_size_mb: int = 50
    storage_path: str = "/data/storage"

    # Worker configuration
    worker_poll_interval: float = 2.0

    # Retrieval thresholds
    abstention_score_threshold: float = 0.3
    ocr_confidence_threshold: float = 0.5

    # CORS origins (comma-separated)
    cors_origins: str = "http://localhost:3000"

    # Chunking configuration
    chunk_max_tokens: int = 500
    chunk_overlap_tokens: int = 150

    # Autoscaler configuration
    autoscaler_enabled: bool = False
    autoscaler_min_workers: int = 3
    autoscaler_max_workers: int = 6
    autoscaler_check_interval_seconds: int = 60
    autoscaler_scale_up_queue_threshold: int = 5
    autoscaler_scale_up_duration_seconds: int = 600
    autoscaler_scale_up_cooldown_seconds: int = 600
    autoscaler_scale_down_queue_threshold: int = 2
    autoscaler_scale_down_duration_seconds: int = 1800
    autoscaler_scale_down_cooldown_seconds: int = 1800
    autoscaler_emergency_queue_threshold: int = 10

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def effective_database_url(self) -> str:
        """Return the effective database URL.

        Priority: DATABASE_URL > POSTGRES_URL > default SQLite path.
        """
        if self.database_url:
            return self.database_url
        if self.postgres_url:
            return self.postgres_url
        # Default: SQLite in the storage directory
        return f"sqlite+aiosqlite:///./easyrag.db"


def get_settings() -> Settings:
    """Return a cached Settings instance. Created once on first call."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
