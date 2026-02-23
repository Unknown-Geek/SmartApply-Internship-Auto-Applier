# =============================================================================
# SmartApply — Configuration Module
# =============================================================================
# Centralized configuration management using pydantic-settings.
# Loads environment variables from .env file and provides type-safe settings.
# =============================================================================

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root dir (SmartApply repo root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Usage:
        from app.config import get_settings
        settings = get_settings()
        api_key = settings.effective_api_key
    """

    # -------------------------------------------------------------------------
    # Model Configuration
    # -------------------------------------------------------------------------
    model_config = SettingsConfigDict(
        env_file=".env",           # Load from .env file
        env_file_encoding="utf-8",
        case_sensitive=False,       # Allow case-insensitive env vars
        extra="ignore",             # Ignore extra env vars
    )

    # -------------------------------------------------------------------------
    # Cerebras API Settings
    # -------------------------------------------------------------------------
    cerebras_api_key: str = ""                           # Required: Cerebras API key
    cerebras_model: str = "gpt-oss-120b"                 # Model name
    cerebras_temperature: float = 0.3                    # LLM temperature
    cerebras_base_url: str = "https://api.cerebras.ai/v1"  # API base URL

    # -------------------------------------------------------------------------
    # Application Settings
    # -------------------------------------------------------------------------
    app_env: str = "development"  # Environment: development, staging, production
    host: str = "0.0.0.0"         # Server host
    port: int = 8000              # Server port
    debug: bool = True            # Debug mode (auto-reload, verbose logging)

    # -------------------------------------------------------------------------
    # Browser Agent Settings
    # -------------------------------------------------------------------------
    headless: bool = True          # Run browser in headless mode
    browser_timeout: int = 60000   # Browser operation timeout (ms)

    # -------------------------------------------------------------------------
    # Agent Settings
    # -------------------------------------------------------------------------
    max_agent_steps: int = 25
    agent_timeout_seconds: int = 600
    agent_thinking_level: str = "medium"   # off|minimal|low|medium|high

    # -------------------------------------------------------------------------
    # Telegram Bot Settings
    # -------------------------------------------------------------------------
    telegram_bot_token: str = ""           # Bot token from @BotFather
    telegram_chat_id: str = ""             # Authorized user's chat ID

    # -------------------------------------------------------------------------
    # n8n Queue Integration (Optional)
    # -------------------------------------------------------------------------
    smartapply_queue_webhook: str = ""     # n8n webhook URL to queue incoming links

    @property
    def telegram_enabled(self) -> bool:
        """True if Telegram bot is configured."""
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    # -------------------------------------------------------------------------
    # SQLite Database
    # -------------------------------------------------------------------------
    sqlite_db_path: str = str(PROJECT_ROOT / "app" / "db" / "smartapply.db")

    # -------------------------------------------------------------------------
    # Computed Properties
    # -------------------------------------------------------------------------
    @property
    def effective_api_key(self) -> str:
        """Return the Cerebras API key."""
        return self.cerebras_api_key

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached application settings instance.

    Uses LRU cache to avoid re-reading .env file on every access.
    Call get_settings.cache_clear() if you need to reload settings.

    Returns:
        Settings: Application settings instance
    """
    return Settings()
