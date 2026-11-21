"""Live Gemini career analysis, skill-gap coaching, comparisons, and projects."""
from __future__ import annotations

import json
from typing import Any

from services.gemini_service import CAREER_SCHEMA, PROJECTS_SCHEMA, SKILL_GAP_SCHEMA, GeminiService


class CareerService:
    def __init__(self, gemini: GeminiService):
        self.gemini = gemini

    def analyze(self, profile: dict[str, Any], skills: list[dict[str, Any]]) -> dict[str, Any]:
        prompt = f"""Analyze this student's selected career using only the profile and self-reported skills below.
Student profile: {json.dumps(profile, ensure_ascii=False)}
Student-reported skills and optional self-ratings: {json.dumps(skills, ensure_ascii=False)}
Return a profession-specific description, essential and optional skills with reasons, relevant tools, education paths, strengths grounded in the supplied profile, development areas, and concrete next steps. Do not infer skills, qualifications, or scores that are not in the input. For regulated or safety-sensitive careers, tell the student to verify local requirements and keep practice simulated or supervised. Do not invent citations or claim to have checked job postings. Return a concise JSON object matching the schema."""
        result = self.gemini.generate_json(prompt, CAREER_SCHEMA)
        result["career"] = profile.get("career_goal", result.get("career", ""))
        result["industry"] = profile.get("industry", result.get("industry", ""))
        result["source_mode"] = "LIVE GEMINI API"
        return result

    def analyze_skills(self, profile: dict[str, Any], skills: list[dict[str, Any]]) -> dict[str, Any]:
        prompt = f"""Create a live skill-gap analysis for the career in this student profile.
Student profile: {json.dumps(profile, ensure_ascii=False)}
Student-reported skills and optional self-ratings: {json.dumps(skills, ensure_ascii=False)}
Identify skills relevant to this profession, state whether each came from the student's input or is a suggested skill to assess, describe current status only from supplied self-ratings (otherwise say Not rated), and provide development priority, explanation, and a practical exercise. Do not assign or change numeric scores. Do not claim a suggested skill is already possessed. Respect professional licensing and safety boundaries. Return JSON matching the schema."""
        result = self.gemini.generate_json(prompt, SKILL_GAP_SCHEMA)
        result["source_mode"] = "LIVE GEMINI API"
        return result

    def compare_careers(self, career_a: str, career_b: str, industry_a: str = "", industry_b: str = "") -> dict[str, Any]:
        prompt = f"""Compare the following two student-selected paths using profession-specific information: {career_a!r} ({industry_a}) and {career_b!r} ({industry_b}). Explain typical responsibilities, relevant skills, tools, and suitable work evidence for each separately. Do not assume requirements, salaries, or local licensing rules. Set mode to 'LIVE GEMINI API'. Return JSON matching the schema."""
        result = self.gemini.generate_json(prompt, comparison_schema())
        result["mode"] = "LIVE GEMINI API"
        return result

    def generate_projects(self, profile: dict[str, Any], skills: list[dict[str, Any]], completed_projects: list[dict[str, Any]], reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
        prompt = f"""Generate two practical project or work-sample ideas using this student's actual profile, career, experience, and self-reported skills.
Student profile: {json.dumps(profile, ensure_ascii=False)}
Skills and self-ratings: {json.dumps(skills, ensure_ascii=False)}
Previously completed projects: {json.dumps(completed_projects, ensure_ascii=False)}
Previous portfolio evaluations: {json.dumps(reviews, ensure_ascii=False)}
Make both ideas specific to the actual profession and experience level. Build on stated skills or completed work, do not claim the student has skills they did not report, and avoid repeating completed projects. For roles where a portfolio is not customary, recommend a suitable case study, simulation, or supervised exercise. Never request real patient/client records or live system access. Return JSON matching the schema."""
        result = self.gemini.generate_json(prompt, PROJECTS_SCHEMA)
        return result["projects"]


def comparison_schema() -> dict[str, Any]:
    career_schema = {"type":"object","properties":{
        "career":{"type":"string"},"industry":{"type":"string"},"overview":{"type":"string"},
        "responsibilities":{"type":"array","items":{"type":"string"}},"skills":{"type":"array","items":{"type":"string"}},
        "tools":{"type":"array","items":{"type":"string"}},"portfolio":{"type":"string"},"related":{"type":"array","items":{"type":"string"}},
    },"required":["career","industry","overview","responsibilities","skills","tools","portfolio","related"]}
    return {"type":"object","properties":{"career_a":career_schema,"career_b":career_schema,"mode":{"type":"string"}},"required":["career_a","career_b","mode"]}
