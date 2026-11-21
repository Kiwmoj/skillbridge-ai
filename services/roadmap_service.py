"""Gemini-only career roadmaps and progress-aware suggestions."""
from __future__ import annotations

import json
from typing import Any

from services.gemini_service import GeminiService, ROADMAP_SCHEMA


class RoadmapService:
    def __init__(self, gemini: GeminiService):
        self.gemini = gemini

    @staticmethod
    def _profile_dict(profile: Any, industry: str = "") -> dict[str, Any]:
        if isinstance(profile, dict): return profile
        return {"career_goal": profile.career_goal, "industry": profile.industry, "name": profile.name,
                "education_level": profile.education_level, "experience": profile.experience,
                "existing_skills": profile.existing_skills or [], "interests": profile.interests,
                "age_range": profile.age_range, "institution": profile.institution,
                "country": profile.country, "region": profile.region,
                "career_interests": profile.career_interests or [],
                "areas_to_improve": profile.areas_to_improve or [],
                "learning_preferences": profile.learning_preferences,
                "weekly_availability": profile.weekly_availability,
                "short_term_goal": profile.short_term_goal, "long_term_goal": profile.long_term_goal}

    @staticmethod
    def _attach_career(items: list[dict[str, Any]], career: str) -> list[dict[str, Any]]:
        stages = ("Beginner", "Intermediate", "Advanced")
        for index, item in enumerate(items):
            if item.get("stage") not in stages:
                item["stage"] = stages[min(index, len(stages) - 1)]
            item["career_goal"] = career
        return items

    def generate(self, profile: Any, skills: list[dict[str, Any]], career_analysis: dict[str, Any] | None = None,
                 skill_gap: dict[str, Any] | None = None,
                 activities: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        data = self._profile_dict(profile)
        prompt = f"""Create a progressive, career-specific learning roadmap for this student. Use the actual career description and skill requirements if supplied. Adapt the recommendations to the student's actual skill assessments, goals, and prior roadmap activity. Treat completion only as stated in the prior records; never invent progress. Each activity must include a clear learning objective, title, description, relevant skills, duration, difficulty, and observable outcome. Include beginner, intermediate, and advanced stages. Use only self-reported skills as student facts. For roles where portfolios are not appropriate, recommend case studies, simulations, or supervised learning. Regulated and safety-sensitive work must use fictional or supervised exercises only.
Student profile: {json.dumps(data, ensure_ascii=False)}
Current skill assessments: {json.dumps(skills, ensure_ascii=False)}
Career analysis: {json.dumps(career_analysis or {}, ensure_ascii=False)}
Skill gap analysis: {json.dumps(skill_gap or {}, ensure_ascii=False)}
Existing roadmap activities and statuses: {json.dumps(activities or [], ensure_ascii=False)}
Return exactly three recommendations, one for each stage, matching the supplied JSON schema."""
        result = self.gemini.generate_json(prompt, ROADMAP_SCHEMA)["recommendations"]
        return self._attach_career(result, data["career_goal"])

    def suggest(self, profile: Any, skills: list[dict[str, Any]], activities: list[dict[str, Any]],
                reviews: list[dict[str, Any]], career_analysis: dict[str, Any] | None = None,
                skill_gap: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        data = self._profile_dict(profile)
        prompt = f"""Suggest one or two NEW learning activities based on this student's current career, skills, career analysis, skill-gap report, completed roadmap activities, completed projects, and portfolio feedback. Make recommendations appropriate to this profession and current stage. Do not repeat completed work. Keep all existing progress intact. Do not invent skill ratings. For regulated or safety-sensitive roles, use fictional or supervised exercises only. Each recommendation must include a learning objective, duration, difficulty, and observable outcome.
Student profile: {json.dumps(data, ensure_ascii=False)}
Skill assessments: {json.dumps(skills, ensure_ascii=False)}
Career analysis: {json.dumps(career_analysis or {}, ensure_ascii=False)}
Skill gap analysis: {json.dumps(skill_gap or {}, ensure_ascii=False)}
Existing roadmap activities: {json.dumps(activities, ensure_ascii=False)}
Portfolio reviews: {json.dumps(reviews, ensure_ascii=False)}
Return JSON matching the supplied schema."""
        result = self.gemini.generate_json(prompt, ROADMAP_SCHEMA)["recommendations"]
        return self._attach_career(result, data["career_goal"])
