"""Load Gemini credentials from local configuration or the OS credential store."""
from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KEYRING_SERVICE = "SkillBridge AI"
KEYRING_USERNAME = "gemini-api-key"
SECURE_BACKEND_PREFIXES = (
    "keyring.backends.Windows",
    "keyring.backends.macOS",
    "keyring.backends.SecretService",
    "keyring.backends.kwallet",
    "keyring.backends.libsecret",
)


class CredentialStorageError(RuntimeError):
    """Raised when a credential cannot be saved securely."""


def load_local_environment() -> None:
    """Load only this project's .env file; never depend on the launch directory."""
    try:
        from dotenv import dotenv_values
    except ImportError:
        return
    try:
        values = dotenv_values(PROJECT_ROOT / ".env")
    except Exception:
        return
    for name, value in values.items():
        if value is not None and not os.getenv(name, "").strip():
            os.environ[name] = value


def read_gemini_api_key() -> str:
    """Return a configured key without exposing its value to UI or logs."""
    load_local_environment()
    # Match the Google Gen AI SDK's documented precedence when both are set.
    for name in ("GOOGLE_API_KEY", "GEMINI_API_KEY"):
        value = os.getenv(name, "").strip()
        if value:
            return value

    try:
        import keyring
        return (keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME) or "").strip()
    except Exception:
        # Credential-store access can fail on locked or unsupported desktops.
        # Environment and .env configuration remain usable in that case.
        return ""


def save_gemini_api_key(value: str) -> None:
    """Save a key once in the platform credential store, never in project files."""
    api_key = value.strip()
    if not api_key:
        raise CredentialStorageError("Enter a Gemini API key before saving.")

    try:
        import keyring
        backend = keyring.get_keyring()
        priority = getattr(backend, "priority", 0)
        backend_module = type(backend).__module__
        if (not isinstance(priority, (int, float)) or priority <= 0
                or not backend_module.startswith(SECURE_BACKEND_PREFIXES)):
            raise CredentialStorageError(
                "The system secure credential store is unavailable. Configure GEMINI_API_KEY or GOOGLE_API_KEY in your environment instead."
            )
        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, api_key)
        saved = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
        if saved != api_key:
            raise CredentialStorageError("The system credential store did not confirm the saved Gemini credential.")
    except CredentialStorageError:
        raise
    except Exception:
        # Do not include backend exceptions: some implementations can echo
        # request details, and credential material must never reach the UI/logs.
        raise CredentialStorageError(
            "Could not save the Gemini credential to the system credential store. Configure GEMINI_API_KEY or GOOGLE_API_KEY in your environment instead."
        ) from None
