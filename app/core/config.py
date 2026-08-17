from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AegisAI"
    environment: str = "development"

    database_url: str = (
        "postgresql+asyncpg://aegis:aegis_dev_password@localhost:55432/aegis"
    )

    redis_url: str = "redis://localhost:6379/0"

    celery_broker_url: str = "redis://localhost:6379/1"

    celery_result_backend: str = "redis://localhost:6379/2"

    cors_origins: str = "http://localhost:5173"

    github_token: str | None = None
    github_api_url: str = "https://api.github.com"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
