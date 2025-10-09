from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Zoho Configuration
    zoho_client_id: str
    zoho_client_secret: str
    zoho_refresh_token: str
    zoho_org_id: str
    zoho_base: str = "https://www.zohoapis.eu"

    # OpenAI Configuration
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"

    # Application Configuration
    app_env: str = "dev"
    port: int = 8000
    database_url: str = "sqlite+aiosqlite:///./data/app.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Global settings instance
settings = Settings()
