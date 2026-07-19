from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SALAR_", env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite:///./data/salar.db"
    jwt_secret: str = "change-this-development-secret-before-deployment"
    token_minutes: int = 720
    bootstrap_email: str = "owner@salar.local"
    bootstrap_password: str = "ChangeMeImmediately!"
    allowed_origins: List[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:4173", "http://localhost:4173", "tauri://localhost"]
    )
    storage_dir: Path = Path("./data/uploads")
    max_upload_mb: int = 25
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:3b"
    public_api_url: str = "https://api.salar.example.com"

