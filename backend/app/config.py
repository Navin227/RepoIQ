from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/repoiq"
    github_token: str | None = None
    openai_api_key: str | None = None
    grok_api_key: str | None = None
    openrouter_api_key: str | None = None
    openrouter_model: str = "google/gemma-4-31b-it:free"
    grok_model: str = "grok-4.7"
    grok_input_token_budget: int = 100_000
    context_token_budget: int = 80_000
    context_batch_files: int = 12
    context_batch_token_budget: int = 16_000
    context_per_file_token_budget: int = 12_000
    context_max_file_bytes: int = 150_000
    provider_timeout_seconds: int = 45
    provider_retry_count: int = 1
    discovery_readiness_relevance_margin: float = 15.0
    llm_provider: str = "grok"
    clone_base_dir: str = "/tmp/repoiq"
    enable_async_jobs: bool = False
    analysis_debug_logging: bool = False
    analysis_debug_preview_chars: int = 12_000

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
    )


settings = Settings()
