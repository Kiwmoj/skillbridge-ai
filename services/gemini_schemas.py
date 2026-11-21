"""Structured JSON schemas shared by the desktop prompts and backend."""
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
        "materials": {"type": "array", "items": {"type": "string"}},
        "learning_objectives": {"type": "array", "items": {"type": "string"}},
        "stages": {"type": "array", "items": {"type": "string"}},
        "software": {"type": "string"}, "difficulty": {"type": "string"},
        "duration": {"type": "string"}, "deliverable": {"type": "string"},
        "portfolio_value": {"type": "string"},
    },
    "required": ["title", "concept", "problem", "description", "skills", "materials", "learning_objectives", "stages", "software", "difficulty", "duration", "deliverable", "portfolio_value"],
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
