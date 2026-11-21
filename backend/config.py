"""Server configuration. Desktop clients must never import server secrets."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent
APP_ROOT = BACKEND_ROOT.parent


def _load_server_environment() -> None:
    """Load backend/.env only; the desktop's .env never contains server keys."""
    try:
        from dotenv import dotenv_values
        values = dotenv_values(BACKEND_ROOT / ".env")
    except Exception:
        return
    for name, value in values.items():
        if value is not None and not os.getenv(name, "").strip():
            os.environ[name] = value


def _read_server_gemini_credential() -> str:
    """Read an existing OS credential for local service-owner deployments only.

    Environment/private server configuration takes precedence. The desktop never
    imports this helper and never receives the credential.
    """
    configured = (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()
    if configured:
        return configured
    try:
        import keyring
        return (keyring.get_password("SkillBridge AI", "gemini-api-key") or "").strip()
    except Exception:
        # Locked/unavailable host credential stores are equivalent to an
        # unconfigured service; never echo backend errors to the app or logs.
        return ""


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str
    gemini_api_key: str
    gemini_model: str
    ai_daily_limit: int
    brave_search_api_key: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_sender: str
    allowed_origins: tuple[str, ...]

    @classmethod
    def from_environment(cls) -> "Settings":
        _load_server_environment()
        return cls(
            database_url=os.getenv("SKILLBRIDGE_SERVER_DATABASE_URL", f"sqlite:///{APP_ROOT / 'data' / 'server.sqlite3'}"),
            secret_key=os.getenv("SKILLBRIDGE_SECRET_KEY", "").strip(),
            gemini_api_key=_read_server_gemini_credential(),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip(),
            ai_daily_limit=max(1, int(os.getenv("SKILLBRIDGE_AI_DAILY_LIMIT", "40"))),
            brave_search_api_key=os.getenv("BRAVE_SEARCH_API_KEY", "").strip(),
            smtp_host=os.getenv("SKILLBRIDGE_SMTP_HOST", "").strip(),
            smtp_port=max(1, int(os.getenv("SKILLBRIDGE_SMTP_PORT", "587"))),
            smtp_username=os.getenv("SKILLBRIDGE_SMTP_USERNAME", "").strip(),
            smtp_password=os.getenv("SKILLBRIDGE_SMTP_PASSWORD", ""),
            smtp_sender=os.getenv("SKILLBRIDGE_SMTP_SENDER", "").strip(),
            allowed_origins=tuple(x.strip() for x in os.getenv("SKILLBRIDGE_ALLOWED_ORIGINS", "").split(",") if x.strip()),
        )
