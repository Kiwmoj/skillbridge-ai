"""Small typed records used by the persistence and service layers."""
from dataclasses import dataclass
from typing import Any


@dataclass
class Profile:
    name: str
    career_goal: str
    experience: str
    interests: list[str]
    industry: str = "Other / custom"
    education_level: str = ""
    existing_skills: list[str] | None = None
    age_range: str = ""
    institution: str = ""
    country: str = ""
    region: str = ""
    career_interests: list[str] | None = None
    areas_to_improve: list[str] | None = None
    learning_preferences: str = ""
    weekly_availability: str = ""
    short_term_goal: str = ""
    long_term_goal: str = ""


@dataclass
class Skill:
    name: str
    proficiency: int | None
    target: int | None
    importance: str
    explanation: str = ""
    exercise: str = ""


@dataclass
class Activity:
    id: int
    stage: str
    title: str
    description: str
    skills: list[str]
    duration: str
    difficulty: str
    outcome: str
    status: str
    rationale: str = ""
    career_goal: str = ""
    learning_objective: str = ""
    notes: str = ""
    sort_order: int = 0


@dataclass
class Project:
    id: int
    title: str
    description: str
    category: str
    software: str
    skills: list[str]
    status: str
    details: dict[str, Any]


@dataclass
class Review:
    id: int
    project_name: str
    created_at: str
    report: dict[str, Any]
    image_path: str = ""
    career_goal: str = ""
