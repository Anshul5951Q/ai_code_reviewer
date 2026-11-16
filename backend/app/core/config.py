from typing import Any, List, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_env: str = "development"
    app_name: str = "AI Code Reviewer"
    app_version: str = "1.0.0"
    api_prefix: str = "/api"

    # Database — PostgreSQL
    database_url: str = "postgresql://postgres:password@localhost:5432/ai_code_reviewer"

    # GitHub Integration & OAuth
    github_token: str | None = None
    github_api_base_url: str = "https://api.github.com"
    github_client_id: str | None = None
    github_client_secret: str | None = None
    github_redirect_uri: str = "http://localhost:8000/api/github/callback"
    github_token_encryption_key: str | None = None
    frontend_url: str = "http://localhost:3000"
    session_cookie_name: str = "acr_session_id"
    oauth_state_ttl_seconds: int = 600  # 10 minutes

    # CORS origins — parsed from comma-separated string, JSON list, or array
    cors_origins: Union[List[str], str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            v_stripped = v.strip()
            if v_stripped.startswith("[") and v_stripped.endswith("]"):
                import json
                try:
                    return json.loads(v_stripped)
                except Exception:
                    pass
            return [x.strip() for x in v_stripped.split(",") if x.strip()]
        if isinstance(v, list):
            return [str(x) for x in v]
        return v

    # Redis — for analysis job queue persistence
    redis_url: str = "redis://localhost:6379/0"

    # Analysis pipeline
    max_file_size_bytes: int = 1_048_576  # 1 MB
    max_concurrent_ingestion_jobs: int = 2
    worker_poll_interval_seconds: float = 0.5

    # LLM Provider Configuration
    llm_provider: str = "ollama"

    # Ollama Local LLM Provider (Phase 7)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5-coder:7b"
    ollama_timeout_seconds: float = 120.0
    ollama_max_concurrent: int = 1
    ollama_context_size: int = 8192
    ollama_temperature: float = 0.1
    ollama_keep_alive: str = "15m"
    ollama_max_retries: int = 2

    @property
    def async_database_url(self) -> str:
        """Convert standard database URL to async driver dialect if needed."""
        url = self.database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        if url.startswith("sqlite://") and not url.startswith("sqlite+aiosqlite://"):
            return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
        return url

    @property
    def sync_database_url(self) -> str:
        """Get synchronous URL for Alembic migrations."""
        url = self.database_url
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql://", 1)
        if url.startswith("sqlite+aiosqlite://"):
            return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
        return url

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


settings = Settings()
