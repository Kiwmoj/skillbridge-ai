import json
from types import SimpleNamespace

import pytest

from backend.services.gemini_provider import GeminiProvider, GeminiRequestError


class FakeInteractions:
    def __init__(self, text=None, error=None):
        self.text = text
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(output_text=self.text)


def test_provider_makes_structured_live_sdk_call_and_validates_result():
    schema = {"type": "object", "properties": {"connected": {"type": "boolean"}}, "required": ["connected"]}
    interactions = FakeInteractions(json.dumps({"connected": True}))
    keys = []
    provider = GeminiProvider(api_key="private-test-key", model="test-model",
                              client_factory=lambda key: (keys.append(key) or SimpleNamespace(interactions=interactions)))
    assert provider.generate_json("live request", schema) == {"connected": True}
    assert keys == ["private-test-key"]
    assert interactions.calls[0]["model"] == "test-model"
    assert interactions.calls[0]["store"] is False
    assert interactions.calls[0]["response_format"]["schema"] == schema


def test_provider_never_returns_fake_content_for_missing_auth_or_bad_responses():
    schema = {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]}
    with pytest.raises(GeminiRequestError, match="has not configured Gemini"):
        GeminiProvider(api_key="").generate_json("request", schema)
    provider = GeminiProvider(api_key="private-test-key", client_factory=lambda _key:
                              SimpleNamespace(interactions=FakeInteractions("not-json")))
    with pytest.raises(GeminiRequestError, match="did not match"):
        provider.generate_json("request", schema)


def test_provider_sanitizes_authentication_errors():
    error = RuntimeError("access denied for private-test-key")
    error.status_code = 403
    provider = GeminiProvider(api_key="private-test-key", client_factory=lambda _key:
                              SimpleNamespace(interactions=FakeInteractions(error=error)))
    with pytest.raises(GeminiRequestError) as captured:
        provider.generate_json("request", {"type": "object", "properties": {}, "required": []})
    assert "private-test-key" not in str(captured.value)
    assert "credential was rejected" in str(captured.value)
