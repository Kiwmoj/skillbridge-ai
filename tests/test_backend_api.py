from dataclasses import replace
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app
from backend.services.gemini_provider import GeminiProvider


class FakeGemini:
    enabled = True

    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def generate_json(self, prompt, schema, image_base64=None, image_mime_type=None):
        self.calls.append((prompt, schema, image_base64, image_mime_type))
        if self.error:
            raise self.error
        if "connected" in schema.get("properties", {}):
            return {"connected": True}
        return {key: ("live provider result" if value.get("type") == "string" else [])
                for key, value in schema.get("properties", {}).items() if key in schema.get("required", [])}


class FakeSearch:
    enabled = True

    def search(self, query, career="", category="other", location="", education_level="", limit=10):
        return [{"title": "Verified provider result", "source_url": "https://example.org/program",
                 "source_name": "example.org", "snippet": "Provider supplied summary.",
                 "category": category, "location": location or "Not listed",
                 "deadline": "Not verified; check the source.",
                 "eligibility": "Not verified; check the source.",
                 "retrieved_at": "2026-11-20T12:00:00+00:00",
                 "verification": "Search result; details are not independently verified."}]


def settings_for(path: Path, limit: int = 10):
    return Settings(database_url=f"sqlite:///{path.as_posix()}", secret_key="test-session-signing-secret-at-least-32-bytes",
                    gemini_api_key="", gemini_model="test-model", ai_daily_limit=limit,
                    brave_search_api_key="", smtp_host="", smtp_port=587, smtp_username="",
                    smtp_password="", smtp_sender="", allowed_origins=())


def register(client: TestClient, email: str):
    response = client.post("/auth/register", json={"email": email, "display_name": email.split("@")[0],
                                                   "password": "Safe-test-password-123"})
    assert response.status_code == 201, response.text
    return response.json()


def headers(auth):
    return {"Authorization": f"Bearer {auth['access_token']}"}


def test_registration_login_profile_logout_and_password_hashing():
    with tempfile.TemporaryDirectory() as temp:
        app = create_app(settings_for(Path(temp) / "server.sqlite3"), provider=FakeGemini(), create_schema=True)
        client = TestClient(app)
        auth = register(client, "First@example.org")
        assert auth["user"]["email"] == "first@example.org"
        assert client.get("/auth/me", headers=headers(auth)).status_code == 200
        saved = client.put("/profiles/me", headers=headers(auth), json={"profile": {
            "name": "First", "career_goal": "Biomedical Engineer", "education_level": "College"}})
        assert saved.status_code == 200
        assert client.get("/profiles/me", headers=headers(auth)).json()["profile"]["career_goal"] == "Biomedical Engineer"
        login = client.post("/auth/login", json={"email": "first@example.org", "password": "Safe-test-password-123"})
        assert login.status_code == 200
        assert client.post("/auth/login", json={"email": "first@example.org", "password": "wrong"}).status_code == 401
        assert client.post("/auth/logout", headers=headers(auth)).status_code == 204
        assert client.get("/auth/me", headers=headers(auth)).status_code == 401
        client.close(); app.state.engine.dispose()


def test_user_data_isolation_records_and_saved_opportunities():
    with tempfile.TemporaryDirectory() as temp:
        app = create_app(settings_for(Path(temp) / "server.sqlite3"), provider=FakeGemini(),
                         opportunity_search=FakeSearch(), create_schema=True)
        client = TestClient(app)
        first = register(client, "one@example.org")
        second = register(client, "two@example.org")
        client.put("/profiles/me", headers=headers(first), json={"profile": {"career_goal": "Architect"}})
        assert client.get("/profiles/me", headers=headers(second)).json()["profile"] == {}
        result = client.put("/records/assessment/one", headers=headers(first), json={"content": "private"})
        assert result.status_code == 200
        assert client.get("/records/assessment", headers=headers(second)).json()["records"] == []
        live = client.post("/opportunities/search", headers=headers(first), json={"query": "summer program",
            "career": "Aerospace Engineer", "category": "college", "limit": 5})
        assert live.status_code == 200
        item = live.json()["results"][0]
        assert item["source_url"].startswith("https://")
        assert "not independently verified" in item["verification"].lower()
        saved = client.post("/opportunities/saved", headers=headers(first), json=item)
        assert saved.status_code == 201
        assert len(client.get("/opportunities/saved", headers=headers(first)).json()["results"]) == 1
        assert client.get("/opportunities/saved", headers=headers(second)).json()["results"] == []
        assert client.patch(f"/opportunities/saved/{saved.json()['id']}", headers=headers(second),
                            json={"application_status": "Applied"}).status_code == 404
        client.close(); app.state.engine.dispose()


def test_ai_uses_configured_provider_reports_quota_and_never_fakes_when_missing():
    with tempfile.TemporaryDirectory() as temp:
        provider = FakeGemini()
        app = create_app(settings_for(Path(temp) / "server.sqlite3", limit=1), provider=provider, create_schema=True)
        client = TestClient(app)
        auth = register(client, "ai@example.org")
        payload = {"prompt": "Career analysis for an aerospace engineer", "response_schema": {
            "type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]}}
        response = client.post("/ai/generate", headers=headers(auth), json=payload)
        assert response.status_code == 200 and response.json()["answer"] == "live provider result"
        assert len(provider.calls) == 1
        assert client.post("/ai/generate", headers=headers(auth), json=payload).status_code == 429
        client.close(); app.state.engine.dispose()

    with tempfile.TemporaryDirectory() as temp:
        app = create_app(settings_for(Path(temp) / "server.sqlite3"), provider=GeminiProvider(api_key=""), create_schema=True)
        client = TestClient(app)
        auth = register(client, "no-ai@example.org")
        response = client.post("/ai/generate", headers=headers(auth), json=payload)
        assert response.status_code == 503
        assert "No AI response was generated" in response.json()["detail"]
        client.close(); app.state.engine.dispose()


def test_ai_error_is_sanitized_and_live_search_missing_is_explicit():
    with tempfile.TemporaryDirectory() as temp:
        provider = FakeGemini(RuntimeError("provider rejected token and secret"))
        app = create_app(settings_for(Path(temp) / "server.sqlite3"), provider=provider,
                         opportunity_search=type("NoSearch", (), {"enabled": False})(), create_schema=True)
        client = TestClient(app)
        auth = register(client, "errors@example.org")
        payload = {"prompt": "test", "response_schema": {"type": "object", "properties": {}, "required": []}}
        error = client.post("/ai/generate", headers=headers(auth), json=payload)
        assert error.status_code == 502
        assert "secret" not in error.text
        search = client.post("/opportunities/search", headers=headers(auth), json={"query": "internship"})
        assert search.status_code == 503
        assert "No opportunities were fabricated" in search.json()["detail"]
        client.close(); app.state.engine.dispose()
