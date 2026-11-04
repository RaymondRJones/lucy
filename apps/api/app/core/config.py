"""Typed application settings."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="GREEN_CARD_PACKET_",
        extra="ignore",
    )

    app_name: str = "Lucy API"
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:3002",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
            "http://127.0.0.1:3002",
        ]
    )
    database_url: str = f"sqlite:///{(REPO_ROOT / 'storage' / 'app.db').as_posix()}"
    upload_dir: Path = REPO_ROOT / "storage" / "uploads"
    generated_dir: Path = REPO_ROOT / "storage" / "generated"
    g1450_template_path: Path = REPO_ROOT / "blank-immigration-documents" / "g-1450.pdf"
    g1650_template_path: Path = REPO_ROOT / "blank-immigration-documents" / "g-1650.pdf"
    max_upload_size_mb: int = 100


settings = Settings()
