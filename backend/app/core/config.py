from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application configuration, loaded from environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "UDS Diagnostics Assistant"
    APP_ENV: str = "development"
    DEBUG: bool = True

    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: str = "http://localhost:5173"

    DATABASE_URL: str = "sqlite:///./uds_assistant.db"

    VECTOR_DB_PATH: str = "./data/vector_store"
    DOCUMENT_STORAGE_PATH: str = "./data/documents"

    # Chunking (Stage 4)
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100

    # Embeddings (Stage 5). "hash" = deterministic offline provider (default; safe for
    # pilot/tests with no network/model download). "sentence_transformers" = real local
    # embedding model, requires EMBEDDING_MODEL and the sentence-transformers package.
    EMBEDDING_PROVIDER: str = "hash"
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIMENSION: int = 384

    # Retrieval (Stage 6)
    RETRIEVAL_TOP_K: int = 5
    RETRIEVAL_MIN_RELEVANCE: float = 0.15

    # API authentication. Empty = auth disabled (dev default). Set a value to
    # require the X-API-Key header on the UDS API routes.
    API_KEY: str = ""

    # Real authentication (Issue 1 fix). Empty JWT_SECRET = auth disabled (dev
    # default), same posture as API_KEY. Set both to require real login for
    # project-scoped resources.
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    LLM_PROVIDER: str = "mock"
    LLM_MODEL: str = "claude-sonnet-4-6"
    LLM_API_BASE: str = ""
    LLM_API_KEY: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
