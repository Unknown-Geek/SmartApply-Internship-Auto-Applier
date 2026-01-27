# =============================================================================
# SmartApply Web Agent - Configuration Module
# =============================================================================
# Centralized configuration management using pydantic-settings.
# Loads environment variables from .env file and provides type-safe settings.
# =============================================================================

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Usage:
        from app.config import get_settings
        settings = get_settings()
        api_key = settings.google_api_key
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
    # Google Gemini API Settings
    # -------------------------------------------------------------------------
    google_api_key: str = ""  # Required: Your Google Gemini API key
    
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
    headless: bool = True         # Run browser in headless mode
    browser_timeout: int = 30000  # Browser operation timeout (ms)
    
    # -------------------------------------------------------------------------
    # Computed Properties
    # -------------------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
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
