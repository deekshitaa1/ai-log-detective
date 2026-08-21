from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AegisAI"
    environment: str = "development"

    database_url: str = (
        "postgresql+asyncpg://aegis:aegis_dev_password@127.0.0.1:55432/aegis"
    )

    redis_url: str = "redis://127.0.0.1:6379/0"

    github_token: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
