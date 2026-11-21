import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from database.db_manager import Database
from services.api_client import ApiError
from services.career_service import CareerService
from services.gemini_schemas import (CAREER_SCHEMA, PORTFOLIO_SCHEMA, PROJECTS_SCHEMA,
                                     ROADMAP_SCHEMA, SKILL_GAP_SCHEMA)
from services.gemini_service import GeminiService
from services.portfolio_service import PortfolioService
from services.roadmap_service import RoadmapService


def sample_for_schema(schema, path=""):
    kind = schema.get("type")
    if kind == "object":
        return {name: sample_for_schema(schema.get("properties", {}).get(name, {}), f"{path}.{name}")
                for name in schema.get("required", [])}
    if kind == "array":
        if path.endswith(".recommendations") or path.endswith(".projects"):
            return [sample_for_schema(schema.get("items", {}), path + "[]")]
        return []
    if kind == "string": return "Career-specific guidance returned by the test transport"
    if kind == "integer": return 1
    if kind == "number": return 1
    if kind == "boolean": return False
    return None


class FakeApiClient:
    authenticated = True

    def __init__(self):
        self.calls = []

    def generate(self, prompt, schema, image_base64=None, image_mime_type=None):
        self.calls.append({"prompt": prompt, "schema": schema,
                           "image_base64": image_base64, "image_mime_type": image_mime_type})
        return sample_for_schema(schema)

    def test_ai(self):
        self.calls.append({"path": "/ai/test"})
        return {"connected": True}


class GeminiServiceTests(unittest.TestCase):
    def test_desktop_service_only_uses_authenticated_api_transport(self):
        fake = FakeApiClient()
        service = GeminiService(fake)
        self.assertTrue(service.enabled)
        self.assertTrue(service.test_connection())
        response = service.generate_json("profession request", CAREER_SCHEMA)
        self.assertIn("overview", response)
        self.assertEqual(fake.calls[-1]["prompt"], "profession request")

    def test_missing_service_auth_raises_without_sample_data(self):
        class Unauthenticated:
            authenticated = False
        service = GeminiService(Unauthenticated())
        self.assertFalse(service.enabled)
        with self.assertRaisesRegex(ApiError, "Sign in"):
            service.generate_json("career request", CAREER_SCHEMA)

    def test_multiple_profession_workflows_send_actual_profile_and_image_to_api(self):
        careers = [
            ("Software Engineer", "Technology"),
            ("Graphic Designer", "Creative Industries"),
            ("Marketing Manager", "Business"),
            ("Environmental Scientist", "Science"),
            ("Nurse", "Healthcare"),
            ("Marine Biologist", "Other / custom"),
        ]
        with tempfile.TemporaryDirectory() as temp:
            db = Database(Path(temp) / "workflow.sqlite3")
            image_path = Path(temp) / "student-work.png"
            Image.new("RGB", (8, 8), "white").save(image_path)
            api = FakeApiClient()
            gemini = GeminiService(api)
            career = CareerService(gemini)
            roadmap = RoadmapService(gemini)
            portfolio = PortfolioService(gemini)
            for index, (title, industry) in enumerate(careers):
                db.save_profile(f"Student {index}", title, "College", "Beginner", ["Research", "Communication"], industry)
                profile = db.get_profile()
                skills = [skill.__dict__ for skill in db.get_skills()]
                report = career.analyze(profile.__dict__, skills)
                gap = career.analyze_skills(profile.__dict__, skills)
                projects = career.generate_projects(profile.__dict__, skills, [], [])
                steps = roadmap.generate(profile, skills, report, gap)
                review = portfolio.review(str(image_path), {"profile": profile.__dict__, "category": title,
                    "name": "Student work", "description": "A learning sample", "skills": ["Research"]})
                self.assertEqual(report["career"], title)
                self.assertEqual(report["source_mode"], "LIVE GEMINI API")
                self.assertTrue(gap["summary"])
                self.assertEqual(len(projects), 1)
                self.assertEqual(steps[0]["career_goal"], title)
                self.assertTrue(review["source_mode"].startswith("LIVE GEMINI"))
                db.add_recommendation(title, industry, "career_reality_check", report)
                db.add_recommendation(title, industry, "skill_gap_analysis", gap)
                db.add_recommendation(title, industry, "learning_roadmap", steps)
                self.assertIn(title, api.calls[-2]["prompt"])
                self.assertIsNotNone(api.calls[-1]["image_base64"])
                self.assertEqual(api.calls[-1]["image_mime_type"], "image/png")
            self.assertEqual(len(careers), 6)
            self.assertEqual(len(db.get_recommendations(kind="career_reality_check")), 6)


if __name__ == "__main__":
    unittest.main()
