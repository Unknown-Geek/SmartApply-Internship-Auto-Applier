"""backend/app/core/config.py — Centralised settings via pydantic-settings."""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Ollama / LLM
    ollama_host: str = "http://ollama:11434"
    llm_model: str = "qwen2.5-coder:7b"
    llm_context_size: int = 8192
    llm_temperature: float = 0.1

    # Context Mode
    context_mode_url: str = "http://context-mode:3100"

    # Agent behaviour
    agent_max_steps: int = 20
    agent_timeout_seconds: int = 300

    # Data paths
    identity_csv_path: str = "/app/data/identity/identity.csv"
    resume_pdf_path: str = "/app/data/identity/resume.pdf"
    sessions_dir: str = "/app/data/sessions"

    # App
    secret_key: str = "change-me-in-production"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
