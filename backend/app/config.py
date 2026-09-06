from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


_BASE_DIR = Path(__file__).resolve().parent.parent.parent

# On Render with mounted disk, use absolute path for SQLite
_render_data = Path("/app/data")
if _render_data.exists():
    _data_dir = _render_data
else:
    _data_dir = _BASE_DIR / "backend" / "data"

_data_dir.mkdir(parents=True, exist_ok=True)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SALAR_", env_file=str(_BASE_DIR / ".env"), extra="ignore")

    environment: str = "development"
    database_url: str = f"sqlite:///{_data_dir / 'salar.db'}"
    jwt_secret: str = "change-this-development-secret-before-deployment"
    token_minutes: int = 720
    supabase_url: Optional[str] = None
    supabase_jwt_secret: Optional[str] = None
    supabase_audience: str = "authenticated"
    admin_emails: List[str] = Field(default_factory=list)
    bootstrap_email: str = "owner@salar.local"
    bootstrap_password: str = "ChangeMeImmediately!"
    allowed_origins: List[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:4173", "http://localhost:4173", "http://127.0.0.1:5173", "http://localhost:5173", "tauri://localhost", "https://tauri.localhost"]
    )
    storage_dir: Path = _data_dir / "uploads"
    max_upload_mb: int = 25
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-3.1-flash-lite"
    gemini_live_model: str = "gemini-3.1-flash-live-preview"
    openai_api_key: Optional[str] = None
    openai_realtime_model: str = "gpt-realtime"
    public_api_url: str = "https://api.salar.example.com"
    bridge_url: str = "http://127.0.0.1:3100"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_default_model: str = "salar-tuned"

    # NVIDIA NIM (OpenAI-compatible, server-side only)
    nim_api_key: Optional[str] = None
    nim_base_url: str = "https://integrate.api.nvidia.com/v1"
    nim_enabled: bool = True # auto-disabled if no key
    nim_default_model: str = "nvidia/nemotron-3-super-120b-a12b"

    stripe_secret_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None
    stripe_price_pro: Optional[str] = None
    stripe_price_team: Optional[str] = None
    paypal_client_id: Optional[str] = None
    paypal_secret: Optional[str] = None
    payment_wallet_address: str = "0x0000000000000000000000000000000000000000"
    free_monthly_quota: int = 500
    pro_monthly_quota: int = 5000

    intel_email_watch_interval_seconds: int = 900
    intel_morning_brief_hour: int = 7
    intel_email_watch_limit: int = 50

    log_level: str = "INFO"
    cors_allow_origin_regex: Optional[str] = None
    rate_limit_default: str = "60/minute"
