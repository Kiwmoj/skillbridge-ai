"""Small HTTPS client for the SkillBridge service; tokens stay out of logs."""
from __future__ import annotations

import os
import json
from pathlib import Path
from urllib.parse import urlparse

import requests


APP_ROOT = Path(__file__).resolve().parent.parent


def configured_api_url() -> str:
    value = os.getenv("SKILLBRIDGE_API_URL", "").strip()
    if not value:
        try:
            settings_path = APP_ROOT / "data" / "desktop-settings.json"
            value = str(json.loads(settings_path.read_text(encoding="utf-8")).get("api_url") or "").strip()
        except (OSError, ValueError, AttributeError):
            value = ""
    if not value:
        try:
            from dotenv import dotenv_values
            value = str(dotenv_values(APP_ROOT / ".env").get("SKILLBRIDGE_API_URL") or "").strip()
        except Exception:
            value = ""
    return value.rstrip("/")


class ApiError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ApiClient:
    def __init__(self, base_url: str | None = None, token: str = "", http=requests):
        self.base_url = (base_url if base_url is not None else configured_api_url()).strip().rstrip("/")
        self.token = token.strip()
        self.http = http

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    @property
    def authenticated(self) -> bool:
        return self.configured and bool(self.token)

    @staticmethod
    def validate_url(url: str) -> str:
        url = url.strip().rstrip("/")
        parsed = urlparse(url)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc or parsed.username or parsed.password:
            raise ApiError("Enter a valid SkillBridge service URL.")
        hostname = (parsed.hostname or "").lower()
        if parsed.scheme != "https" and hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ApiError("SkillBridge requires HTTPS except for a local development server.")
        return url

    def set_base_url(self, url: str):
        self.base_url = self.validate_url(url)

    def save_base_url(self, url: str):
        self.set_base_url(url)
        settings_path = APP_ROOT / "data" / "desktop-settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps({"api_url": self.base_url}, indent=2), encoding="utf-8")

    def request(self, method: str, path: str, *, auth: bool = True, **kwargs):
        if not self.configured:
            raise ApiError("No SkillBridge service URL is configured. Contact the service owner.")
        self.base_url = self.validate_url(self.base_url)
        headers = dict(kwargs.pop("headers", {}) or {})
        if auth:
            if not self.token:
                raise ApiError("Sign in to your SkillBridge account before using this feature.", 401)
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            response = self.http.request(method, f"{self.base_url}{path}", headers=headers, timeout=(5, 95), **kwargs)
        except requests.Timeout:
            raise ApiError("The SkillBridge service took too long to respond. Try again.") from None
        except requests.RequestException:
            raise ApiError("Could not reach the SkillBridge service. Check the service URL and network.") from None
        if not response.ok:
            try:
                detail = response.json().get("detail", "")
            except (ValueError, AttributeError):
                detail = ""
            safe = str(detail).strip() if detail else ""
            if len(safe) > 300:
                safe = safe[:300]
            raise ApiError(safe or f"SkillBridge service returned HTTP {response.status_code}.", response.status_code)
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            raise ApiError("The SkillBridge service returned an unreadable response.") from None

    def health(self):
        return self.request("GET", "/health", auth=False)

    def register(self, email: str, display_name: str, password: str):
        return self.request("POST", "/auth/register", auth=False,
                            json={"email": email, "display_name": display_name, "password": password})

    def login(self, email: str, password: str):
        return self.request("POST", "/auth/login", auth=False, json={"email": email, "password": password})

    def me(self):
        return self.request("GET", "/auth/me")

    def logout(self):
        return self.request("POST", "/auth/logout")

    def delete_account(self, email: str, password: str):
        return self.request("DELETE", "/auth/me", json={"email": email, "password": password})

    def save_profile(self, profile: dict):
        return self.request("PUT", "/profiles/me", json={"profile": profile})

    def get_profile(self):
        return self.request("GET", "/profiles/me").get("profile", {})

    def generate(self, prompt: str, schema: dict, image_base64: str | None = None,
                 image_mime_type: str | None = None):
        return self.request("POST", "/ai/generate", json={"prompt": prompt, "response_schema": schema,
                            "image_base64": image_base64, "image_mime_type": image_mime_type})

    def test_ai(self):
        return self.request("POST", "/ai/test")

    def request_password_reset(self, email: str):
        return self.request("POST", "/auth/password-reset/request", auth=False, json={"email": email})

    def confirm_password_reset(self, token: str, new_password: str):
        return self.request("POST", "/auth/password-reset/confirm", auth=False,
                            json={"token": token, "new_password": new_password})

    def search_opportunities(self, **filters):
        return self.request("POST", "/opportunities/search", json=filters)

    def save_opportunity(self, opportunity: dict):
        allowed = {key: opportunity.get(key) for key in (
            "title", "source_url", "source_name", "category", "location", "deadline", "eligibility", "retrieved_at")}
        return self.request("POST", "/opportunities/saved", json=allowed)

    def saved_opportunities(self):
        return self.request("GET", "/opportunities/saved").get("results", [])

    def update_saved_opportunity(self, opportunity_id: str, application_status: str):
        return self.request("PATCH", f"/opportunities/saved/{opportunity_id}",
                            json={"application_status": application_status})

    def delete_saved_opportunity(self, opportunity_id: str):
        return self.request("DELETE", f"/opportunities/saved/{opportunity_id}")

    def save_record(self, kind: str, record_key: str, payload: dict):
        return self.request("PUT", f"/records/{kind}/{record_key}", json=payload)

