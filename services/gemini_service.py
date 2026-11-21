"""Live Gemini API adapter with structured response validation."""
from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any

from services.gemini_credentials import read_gemini_api_key


class GeminiService:
    def __init__(self) -> None:
        self.api_key = read_gemini_api_key()
        self.model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()

    def reload_credentials(self) -> None:
        """Reload the environment or system credential store after setup."""
        self.api_key = read_gemini_api_key()

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def test_connection(self) -> bool:
        """Make a small real Gemini request to verify configured authentication."""
        result = self.generate_json(
            'Return the JSON object {"connected": true}.',
            {"type": "object", "properties": {"connected": {"type": "boolean"}}, "required": ["connected"]},
        )
        if result.get("connected") is not True:
            raise RuntimeError("Gemini responded, but the connection check did not confirm success.")
        return True

    def generate_json(self, prompt: str, schema: dict[str, Any], image_path: str | None = None) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("Gemini authentication is required. Save a key once from Gemini Setup, or configure GEMINI_API_KEY / GOOGLE_API_KEY in the environment or project .env file.")
        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError("Install the Gemini SDK with: pip install google-genai") from exc

        if image_path:
            path = Path(image_path)
            mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
            image = base64.b64encode(path.read_bytes()).decode("ascii")
            request_input: Any = [
                {"type": "text", "text": prompt},
                {"type": "image", "data": image, "mime_type": mime},
            ]
        else:
            request_input = prompt
        try:
            client = genai.Client(api_key=self.api_key)
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
            raise RuntimeError(f"Gemini returned an invalid structured response: {exc}") from exc
        except Exception as exc:
            status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
            message = self._redact_provider_message(str(exc))
            if status == 429 or "429" in message or "RESOURCE_EXHAUSTED" in message:
                explanation = "Gemini rate limit reached. Wait before trying again or review the project's API quota."
            elif status in {401, 403} or "UNAUTHENTICATED" in message or "PERMISSION_DENIED" in message:
                explanation = "Gemini rejected the credentials. Check the API key and its access in Google AI Studio."
            elif str(status).isdigit() and int(status) >= 500:
                explanation = "Gemini is temporarily unavailable. Try again shortly."
            else:
                explanation = f"Gemini request failed: {message}"
            # Avoid leaking SDK request details via exception chaining if a
            # caller later logs a traceback.
            raise RuntimeError(explanation) from None

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
