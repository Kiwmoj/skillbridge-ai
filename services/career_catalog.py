"""Career names and industry inference for the searchable student career picker."""

CAREERS_BY_INDUSTRY = {
    "Technology": ["Software Engineer", "AI Engineer", "Data Scientist", "Cybersecurity Analyst", "Robotics Engineer", "Electrical Engineer", "Mechanical Engineer"],
    "Creative Industries": ["Video Game Animator", "3D Character Artist", "Game Developer", "Graphic Designer", "UI/UX Designer", "Film Editor", "VFX Artist", "Architect"],
    "Business": ["Entrepreneur", "Marketing Manager", "Financial Analyst", "Business Analyst", "Project Manager"],
    "Science": ["Biomedical Engineer", "Aerospace Engineer", "Environmental Scientist", "Research Scientist"],
    "Healthcare": ["Pharmacist", "Nurse", "Physical Therapist", "Medical Researcher"],
}

INDUSTRIES = list(CAREERS_BY_INDUSTRY) + ["Other / custom"]
CAREER_NAMES = [career for roles in CAREERS_BY_INDUSTRY.values() for career in roles]
_CAREER_INDUSTRY = {career.casefold(): industry for industry, roles in CAREERS_BY_INDUSTRY.items() for career in roles}


def infer_industry(career: str, selected: str = "") -> str:
    return _CAREER_INDUSTRY.get(career.strip().casefold(), selected if selected in INDUSTRIES else "Other / custom")
