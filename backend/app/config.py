from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/repoiq"
    github_token: str | None = None
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    llm_provider: str = "openai"
    clone_base_dir: str = "/tmp/repoiq"
    enable_async_jobs: bool = False

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
    )


settings = Settings()