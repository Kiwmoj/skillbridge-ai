"""Desktop facade that sends all AI requests to the authenticated service."""
from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from services.api_client import ApiClient, ApiError
from services.gemini_schemas import (CAREER_SCHEMA, PORTFOLIO_SCHEMA, PROJECTS_SCHEMA,
                                     ROADMAP_SCHEMA, SKILL_GAP_SCHEMA)


class GeminiService:
    """Compatibility facade for existing feature services; no Gemini key lives here."""
    def __init__(self, api_client: ApiClient | None = None) -> None:
        self.api_client = api_client or ApiClient()
        self.model = "Managed by the SkillBridge service"

    @property
    def enabled(self) -> bool:
        return self.api_client.authenticated

    def test_connection(self) -> bool:
        if not self.enabled:
            raise ApiError("Connect to the SkillBridge service and sign in before testing Gemini.")
        response = self.api_client.test_ai()
        if response.get("connected") is not True:
            raise ApiError("The service did not confirm a live Gemini response.")
        return True

    def generate_json(self, prompt: str, schema: dict[str, Any], image_path: str | None = None,
                      image_base64: str | None = None, image_mime_type: str | None = None) -> dict[str, Any]:
        if not self.enabled:
            raise ApiError("Sign in to a configured SkillBridge service to use Gemini features.")
        if image_path:
            path = Path(image_path)
            content_type = mimetypes.guess_type(path.name)[0]
            if content_type not in {"image/png", "image/jpeg"}:
                raise ValueError("Please choose a PNG, JPG, or JPEG image.")
            raw = path.read_bytes()
            if not raw or len(raw) > 6_000_000:
                raise ValueError("Portfolio images must be between 1 byte and 6 MB.")
            image_base64 = base64.b64encode(raw).decode("ascii")
            image_mime_type = content_type
        return self.api_client.generate(prompt, schema, image_base64, image_mime_type)
