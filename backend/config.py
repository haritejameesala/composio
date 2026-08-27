"""
Application configuration — reads from .env file via pydantic-settings.
All settings are loaded once at module import time and shared across the app.
COMPOSIO_API_KEY is NEVER serialised or logged.
"""
from __future__ import annotations

import json
from typing import List, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Composio ──────────────────────────────────────────────────────────────
    composio_api_key: str
    default_toolkit_slug: str = "serpapi"
    oauth_callback_url: str = "http://localhost:5173/connections"

    # ── JWT ───────────────────────────────────────────────────────────────────
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./db/app.db"

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: Union[List[str], str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # ── Bootstrap Admin ───────────────────────────────────────────────────────
    admin_username: str = "admin"
    admin_email: str = "admin@example.com"
    admin_password: str = "Admin1234!"

    @field_validator("cors_origins", mode="after")
    @classmethod
    def parse_cors(cls, v: Union[List[str], str]) -> List[str]:
        """Convert string to list if necessary."""
        if isinstance(v, str):
            v_trimmed = v.strip()
            if v_trimmed.startswith("[") and v_trimmed.endswith("]"):
                try:
                    parsed = json.loads(v_trimmed)
                    if isinstance(parsed, list):
                        return [str(x).strip() for x in parsed]
                except Exception:
                    pass
            return [origin.strip() for origin in v_trimmed.split(",") if origin.strip()]
        return v

    def __repr__(self) -> str:
        """Never print the API key in repr."""
        return (
            f"Settings(default_toolkit_slug={self.default_toolkit_slug!r}, "
            f"database_url={self.database_url!r}, "
            f"cors_origins={self.cors_origins!r})"
        )


settings = Settings()  # type: ignore[call-arg]
