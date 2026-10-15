from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/repoiq"
    github_token: str | None = None
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    openrouter_api_key: str | None = None
    openrouter_model: str = "google/gemma-4-31b-it:free"
    gemini_model: str = "gemini-2.5-flash"
    gemini_input_token_budget: int = 100_000
    context_token_budget: int = 80_000
    context_batch_files: int = 12
    context_batch_token_budget: int = 16_000
    context_per_file_token_budget: int = 12_000
    context_max_file_bytes: int = 150_000
    provider_timeout_seconds: int = 45
    provider_retry_count: int = 1
    discovery_relevance_weight: float = 0.65
    discovery_analyzability_weight: float = 0.35
    llm_provider: str = "gemini"
    clone_base_dir: str = "/tmp/repoiq"
    enable_async_jobs: bool = False
    analysis_debug_logging: bool = False
    analysis_debug_preview_chars: int = 12_000

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
    )


settings = Settings()
