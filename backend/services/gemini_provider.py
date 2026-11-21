"""Live Gemini API adapter with structured response validation."""
from __future__ import annotations

import json
import os
import re
from typing import Any


class GeminiRequestError(RuntimeError):
    """Sanitized Gemini error safe for display to an authenticated student."""


class GeminiProvider:
    """Server-only Gemini client. The API key is read from server process env."""

    def __init__(self, api_key: str | None = None, model: str | None = None, client_factory=None) -> None:
        self.api_key = (api_key if api_key is not None else (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", ""))).strip()
        self.model = (model or os.getenv("GEMINI_MODEL", "gemini-3.8-flash")).strip()
        self.client_factory = client_factory

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def generate_json(self, prompt: str, schema: dict[str, Any], image_base64: str | None = None,
                      image_mime_type: str | None = None) -> dict[str, Any]:
        if not self.enabled:
            raise GeminiRequestError("The SkillBridge backend owner has not configured Gemini. No AI result was generated.")
        try:
            if self.client_factory:
                client = self.client_factory(self.api_key)
            else:
                from google import genai
                client = genai.Client(api_key=self.api_key)
        except ImportError as exc:
            raise GeminiRequestError("The SkillBridge service is missing its Gemini SDK installation.") from None
        except Exception:
            raise GeminiRequestError("The SkillBridge service could not initialize its Gemini client.") from None

        if image_base64:
            request_input: Any = [
                {"type": "text", "text": prompt},
                {"type": "image", "data": image_base64, "mime_type": image_mime_type or "image/png"},
            ]
        else:
            request_input = prompt
        try:
            interaction = client.interactions.create(
                model=self.model,
                input=request_input,
                store=False,
                response_format={"type": "text", "mime_type": "application/json", "schema": schema},
                timeout=90,
            )
            raw = interaction.output_text or ""
            data = json.loads(raw)
            self._validate_json(data, schema)
            return data
        except (ValueError, TypeError, KeyError) as exc:
            raise GeminiRequestError("Gemini returned a response that did not match the requested format. Try again.") from None
        except Exception as exc:
            status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
            message = self._redact_provider_message(str(exc))
            if status == 429 or "429" in message or "RESOURCE_EXHAUSTED" in message:
                explanation = "Gemini rate limit reached. Wait before trying again or review the project's API quota."
            elif status in {401, 403} or "UNAUTHENTICATED" in message or "PERMISSION_DENIED" in message:
                explanation = "The backend Gemini credential was rejected. The service owner must check its server configuration."
            elif str(status).isdigit() and int(status) >= 500:
                explanation = "Gemini is temporarily unavailable. Try again shortly."
            else:
                explanation = "The Gemini request failed. Check backend logs and provider configuration."
            # Avoid leaking SDK request details via exception chaining if a
            # caller later logs a traceback.
            raise GeminiRequestError(explanation) from None

    def _redact_provider_message(self, message: str) -> str:
        if self.api_key:
            message = message.replace(self.api_key, "[redacted]")
        message = re.sub(r"AIza[0-9A-Za-z_-]{20,}", "[redacted]", message)
        message = re.sub(r"(?i)([?&](?:key|api[_-]?key)=)[^&\s'\"<>]+", r"\1[redacted]", message)
        return message

    @classmethod
    def _validate_json(cls, value: Any, schema: dict[str, Any], path: str = "response") -> None:
        expected = schema.get("type")
        type_map = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float), "boolean": bool}
        expected_python = type_map.get(expected)
        if expected_python and (not isinstance(value, expected_python) or (expected == "integer" and isinstance(value, bool))):
            raise ValueError(f"{path} must be {expected}")
        if expected == "object":
            for key in schema.get("required", []):
                if key not in value:
                    raise ValueError(f"{path}.{key} is required")
            for key, child_schema in schema.get("properties", {}).items():
                if key in value:
                    cls._validate_json(value[key], child_schema, f"{path}.{key}")
        elif expected == "array":
            for index, item in enumerate(value):
                cls._validate_json(item, schema.get("items", {}), f"{path}[{index}]")


CAREER_SCHEMA = {
    "type": "object", "properties": {
        "career": {"type": "string"}, "industry": {"type": "string"},
        "overview": {"type": "string"}, "essential_skills": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "why": {"type": "string"}}, "required": ["name", "why"]}},
        "optional_skills": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "why": {"type": "string"}}, "required": ["name", "why"]}},
        "common_tools": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "why": {"type": "string"}}, "required": ["name", "why"]}},
        "portfolio_expectations": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "why": {"type": "string"}}, "required": ["name", "why"]}},
        "education_paths": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "why": {"type": "string"}}, "required": ["name", "why"]}},
        "strengths": {"type": "array", "items": {"type": "string"}}, "growth_areas": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "why": {"type": "string"}}, "required": ["name", "why"]}},
        "next_steps": {"type": "array", "items": {"type": "string"}}, "sources_note": {"type": "string"}
    }, "required": ["career", "industry", "overview", "essential_skills", "optional_skills", "common_tools", "portfolio_expectations", "education_paths", "strengths", "growth_areas", "next_steps", "sources_note"]
}

SKILL_GAP_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "skill_guidance": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"}, "source": {"type": "string"}, "importance": {"type": "string"},
            "current_assessment": {"type": "string"}, "development_priority": {"type": "string"},
            "explanation": {"type": "string"}, "exercise": {"type": "string"},
        }, "required": ["name", "source", "importance", "current_assessment", "development_priority", "explanation", "exercise"]}},
    },
    "required": ["summary", "skill_guidance"],
}

PORTFOLIO_SCHEMA = {
    "type": "object", "properties": {
        "presentation": {"type": "array", "items": {"type": "string"}}, "technical_observations": {"type": "array", "items": {"type": "string"}},
        "observed_strengths": {"type": "array", "items": {"type": "string"}}, "improvements": {"type": "array", "items": {"type": "string"}},
        "skills_demonstrated": {"type": "array", "items": {"type": "string"}}, "missing_information": {"type": "array", "items": {"type": "string"}},
        "recommended_next_steps": {"type": "array", "items": {"type": "string"}}, "next_project": {"type": "string"},
        "portfolio_tips": {"type": "array", "items": {"type": "string"}}, "limitations": {"type": "string"}
    }, "required": ["presentation", "technical_observations", "observed_strengths", "improvements", "skills_demonstrated", "missing_information", "recommended_next_steps", "next_project", "portfolio_tips", "limitations"]
}

PROJECT_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"}, "concept": {"type": "string"},
        "problem": {"type": "string"}, "description": {"type": "string"},
        "skills": {"type": "array", "items": {"type": "string"}},
        "software": {"type": "string"}, "difficulty": {"type": "string"},
        "duration": {"type": "string"}, "deliverable": {"type": "string"},
        "portfolio_value": {"type": "string"},
    },
    "required": ["title", "concept", "problem", "description", "skills", "software", "difficulty", "duration", "deliverable", "portfolio_value"],
}
PROJECTS_SCHEMA = {
    "type": "object",
    "properties": {"projects": {"type": "array", "items": PROJECT_ITEM_SCHEMA}},
    "required": ["projects"],
}

ROADMAP_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "stage": {"type": "string"}, "title": {"type": "string"},
        "description": {"type": "string"},
        "skills": {"type": "array", "items": {"type": "string"}},
        "duration": {"type": "string"}, "difficulty": {"type": "string"},
        "learning_objective": {"type": "string"}, "outcome": {"type": "string"}, "rationale": {"type": "string"},
    },
    "required": ["stage", "title", "description", "learning_objective", "skills", "duration", "difficulty", "outcome", "rationale"],
}
ROADMAP_SCHEMA = {
    "type": "object",
    "properties": {"recommendations": {"type": "array", "items": ROADMAP_ITEM_SCHEMA}},
    "required": ["recommendations"],
}
