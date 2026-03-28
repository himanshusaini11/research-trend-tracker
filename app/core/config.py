from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # App
    # -------------------------------------------------------------------------
    app_env: Literal["development", "staging", "production"] = "development"
    app_name: str = "Research Trend Tracker"
    debug: bool = False

    # -------------------------------------------------------------------------
    # PostgreSQL
    # -------------------------------------------------------------------------
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "rtt"
    postgres_password: str = Field(..., description="PostgreSQL password — required")
    postgres_db: str = "rtt"

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def postgres_dsn_sync(self) -> str:
        """Sync DSN for Alembic migrations."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # -------------------------------------------------------------------------
    # Redis
    # -------------------------------------------------------------------------
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str | None = None
    redis_db: int = 0

    @property
    def redis_dsn(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # -------------------------------------------------------------------------
    # JWT
    # -------------------------------------------------------------------------
    jwt_secret: str = Field(..., description="JWT signing secret — required")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # -------------------------------------------------------------------------
    # API keys (alternative auth)
    # -------------------------------------------------------------------------
    api_key_header: str = "X-API-Key"

    # -------------------------------------------------------------------------
    # Ollama / LLM
    # -------------------------------------------------------------------------
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    ollama_predict_model: str = "llama3.2"   # fast model for prediction endpoints
    ollama_request_timeout_seconds: int = 120

    # -------------------------------------------------------------------------
    # arXiv ingestion
    # -------------------------------------------------------------------------
    arxiv_categories: list[str] = Field(
        default=["cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.NE", "stat.ML", "cs.IR", "eess.SP", "eess.IV"],
        description="arXiv category filters for ingestion",
    )
    arxiv_max_results_per_fetch: int = 1000
    arxiv_fetch_delay_seconds: float = 3.0  # respect arXiv rate limits

    # -------------------------------------------------------------------------
    # Semantic Scholar API
    # -------------------------------------------------------------------------
    semantic_scholar_api_key: str | None = Field(
        default=None, description="Optional — raises rate limit from 100 to 1000 req/5 min"
    )
    semantic_scholar_base_url: str = "https://api.semanticscholar.org/graph/v1"
    semantic_scholar_fetch_delay_seconds: float = 3.0  # ~100 req/5 min = 1 req/3s

    # -------------------------------------------------------------------------
    # LLM extraction backend
    # -------------------------------------------------------------------------
    extraction_backend: str = "ollama"  # ollama | anthropic-haiku | anthropic-sonnet
    anthropic_api_key: str | None = None
    anthropic_batch_poll_interval_seconds: int = 30

    # -------------------------------------------------------------------------
    # Graph analysis
    # -------------------------------------------------------------------------
    graph_top_n_concepts: int = 200
    graph_centrality_k_samples: int = 200

    # -------------------------------------------------------------------------
    # Rate limiting (Token Bucket via Redis)
    # -------------------------------------------------------------------------
    rate_limit_requests: int = 60       # tokens per window
    rate_limit_window_seconds: int = 60  # refill window
    rate_limit_burst: int = 10          # max burst above steady rate

    # -------------------------------------------------------------------------
    # User paper uploads (Feature 4)
    # -------------------------------------------------------------------------
    upload_dir: str = "/app/uploads"
    max_upload_size_mb: int = 20
    max_user_storage_mb: int = 100
    max_user_files: int = 10
    max_user_lifetime_uploads: int = 30
    user_data_expiry_days: int = 30
    storage_backend: str = "local"  # 'local' | 's3' (future)


settings = Settings()  # type: ignore[call-arg]
