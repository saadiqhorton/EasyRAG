"""Application configuration via Pydantic Settings with env var loading."""

from pydantic_settings import BaseSettings

QDRANT_COLLECTION_NAME = "rag_kb_chunks"

_settings: Settings | None = None


class Settings(BaseSettings):
    """Central configuration loaded from environment variables.

    Required vars with no default will raise ValidationError on startup
    if not set. All secrets come from env, never hardcoded.
    """

    postgres_url: str
    qdrant_url: str
    qdrant_api_key: str | None = None
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimensions: int = 384
    reranker_model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    answer_llm_base_url: str
    answer_llm_model: str
    answer_llm_api_key: str | None = None
    max_upload_size_mb: int = 50
    storage_path: str = "/data/storage"
    worker_poll_interval: float = 2.0
    abstention_score_threshold: float = 0.3
    ocr_confidence_threshold: float = 0.5
    cors_origins: str = "http://localhost:3000"
    chunk_max_tokens: int = 500
    chunk_overlap_tokens: int = 150

    model_config = {"env_file": ".env", "extra": "ignore"}


def get_settings() -> Settings:
    """Return a cached Settings instance. Created once on first call."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings