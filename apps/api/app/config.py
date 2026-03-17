from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+psycopg://localhost/hill_jobs"
    internal_ingest_token: str = ""
    usajobs_api_key: str | None = None
    usajobs_user_agent_email: str | None = None
    resend_api_key: str = ""
    site_base_url: str = "https://hill-jobs.org"


@lru_cache
def get_settings() -> Settings:
    return Settings()
