from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Zoho Configuration (optional - required only for Zoho sync features)
    zoho_client_id: str = ""
    zoho_client_secret: str = ""
    zoho_refresh_token: str = ""
    zoho_org_id: str = ""
    zoho_base: str = "https://www.zohoapis.eu"

    # OpenAI Configuration (optional - required only for AI analysis features)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Application Configuration
    app_env: str = "dev"
    port: int = 8000
    database_url: str = "sqlite+aiosqlite:///./data/app.db"

    # Authentication Configuration (optional - if not set, auth is disabled)
    auth_username: str = ""
    auth_password: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Global settings instance
settings = Settings()
