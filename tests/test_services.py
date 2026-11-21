import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from database.db_manager import Database
from services.career_service import CareerService
from services.gemini_service import CAREER_SCHEMA, GeminiService, PORTFOLIO_SCHEMA, ROADMAP_SCHEMA, SKILL_GAP_SCHEMA
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
    if kind == "string": return "Career-specific practice recommendation"
    if kind == "integer": return 1
    if kind == "number": return 1
    if kind == "boolean": return False
    return None


class FakeInteractions:
    def __init__(self): self.calls = []
    def create(self, **kwargs):
        self.calls.append(kwargs)
        schema = kwargs["response_format"]["schema"]
        return types.SimpleNamespace(output_text=json.dumps(sample_for_schema(schema)))


class FailingInteractions:
    def __init__(self, error): self.error = error
    def create(self, **kwargs): raise self.error


class GeminiServiceTests(unittest.TestCase):
    def test_missing_key_raises_instead_of_returning_substitute_content(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY":""}):
            gemini = GeminiService()
            gemini.api_key = ""
            with self.assertRaisesRegex(RuntimeError, "GEMINI_API_KEY"):
                gemini.generate_json("Prompt", CAREER_SCHEMA)

    def test_rate_limit_and_invalid_responses_are_reported(self):
        fake_genai = types.ModuleType("google.genai")
        fake_google = types.ModuleType("google")
        fake_google.genai = fake_genai
        with patch.dict(os.environ, {"GEMINI_API_KEY":"unit-test-key"}), patch.dict(sys.modules, {"google":fake_google, "google.genai":fake_genai}):
            gemini = GeminiService()
            quota_error = RuntimeError("quota")
            quota_error.status_code = 429
            fake_genai.Client = lambda **kwargs: types.SimpleNamespace(interactions=FailingInteractions(quota_error))
            with self.assertRaisesRegex(RuntimeError, "rate limit"):
                gemini.generate_json("Prompt", CAREER_SCHEMA)
            fake_genai.Client = lambda **kwargs: types.SimpleNamespace(interactions=types.SimpleNamespace(create=lambda **kwargs: types.SimpleNamespace(output_text="not json")))
            with self.assertRaisesRegex(RuntimeError, "invalid structured response"):
                gemini.generate_json("Prompt", CAREER_SCHEMA)

    def test_connection_check_makes_a_gemini_request_and_redacts_keys_from_errors(self):
        fake_genai = types.ModuleType("google.genai")
        fake_google = types.ModuleType("google")
        fake_google.genai = fake_genai
        class ConnectionInteractions:
            def __init__(self): self.calls = []
            def create(self, **kwargs):
                self.calls.append(kwargs)
                return types.SimpleNamespace(output_text='{"connected":true}')

        interactions = ConnectionInteractions()
        with patch.dict(os.environ, {"GEMINI_API_KEY": "unit-test-key"}), \
                patch.dict(sys.modules, {"google": fake_google, "google.genai": fake_genai}):
            gemini = GeminiService()
            fake_genai.Client = lambda **kwargs: types.SimpleNamespace(interactions=interactions)
            self.assertTrue(gemini.test_connection())
            self.assertEqual(len(interactions.calls), 1)
            self.assertEqual(interactions.calls[0]["input"], 'Return the JSON object {"connected": true}.')

            class SecretErrorInteractions:
                def create(self, **kwargs):
                    raise RuntimeError("request failed with key=unit-test-key")

            fake_genai.Client = lambda **kwargs: types.SimpleNamespace(interactions=SecretErrorInteractions())
            with self.assertRaises(RuntimeError) as captured:
                gemini.generate_json("Prompt", CAREER_SCHEMA)
            self.assertNotIn("unit-test-key", str(captured.exception))
            self.assertIsNone(captured.exception.__cause__)

    def test_five_professions_run_through_profile_to_portfolio_workflow(self):
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
            interactions = FakeInteractions()
            fake_genai = types.ModuleType("google.genai")
            fake_genai.Client = lambda **kwargs: types.SimpleNamespace(interactions=interactions)
            fake_google = types.ModuleType("google")
            fake_google.genai = fake_genai
            with patch.dict(os.environ, {"GEMINI_API_KEY":"unit-test-key"}), patch.dict(sys.modules, {"google":fake_google, "google.genai":fake_genai}):
                gemini = GeminiService()
                career = CareerService(gemini)
                roadmap = RoadmapService(gemini)
                portfolio = PortfolioService(gemini)
                for index, (title, industry) in enumerate(careers):
                    db.save_profile(f"Student {index}", title, "College", "Beginner", ["Research", "Communication"], industry)
                    profile = db.get_profile()
                    skills = [skill.__dict__ for skill in db.get_skills()]
                    report = career.analyze(profile.__dict__, skills)
                    gap = career.analyze_skills(profile.__dict__, skills)
                    comparison = career.compare_careers(title, "Research Scientist", industry, "Science")
                    project_ideas = career.generate_projects(profile.__dict__, skills, [], [])
                    steps = roadmap.generate(profile, skills, report, gap)
                    image_report = portfolio.review(str(image_path), {"profile":profile.__dict__, "category":title, "name":"Student work", "description":"A learning sample", "skills":["Research"]})

                    self.assertEqual(report["source_mode"], "LIVE GEMINI API")
                    self.assertTrue(project_ideas)
                    self.assertTrue(steps[0]["learning_objective"])
                    self.assertTrue(image_report["source_mode"].startswith("LIVE GEMINI"))
                    db.add_recommendation(title, industry, "career_reality_check", report)
                    db.add_recommendation(title, industry, "skill_gap_analysis", gap)
                    db.add_recommendation(title, industry, "career_comparison", comparison)
                    db.add_recommendation(title, industry, "project_ideas", project_ideas)
                    db.add_recommendation(title, industry, "learning_roadmap", steps)
                    activity = db.add_activity(steps[0])
                    db.update_activity_status(activity, "Completed")
                    suggestions = roadmap.suggest(profile, skills, [item.__dict__ for item in db.get_activities()], [], report, gap)
                    self.assertTrue(suggestions)
                    self.assertIn(title, interactions.calls[-1]["input"])
                    db.add_recommendation(title, industry, "roadmap_suggestions", suggestions)
                    project = project_ideas[0]
                    project_id = db.add_project({"title":project["title"], "description":project["description"], "category":title, "details":project})
                    db.update_project_status(project_id, "Completed")
                    db.add_review("Student work", str(image_path), image_report)

                    self.assertEqual(db.analytics()["completed"], 1)
                    self.assertEqual(db.analytics()["completed_projects"], 1)
                    self.assertEqual(db.analytics()["review_count"], 1)
                    prompt_calls = [call for call in interactions.calls if isinstance(call["input"], str)]
                    career_calls = [call for call in prompt_calls if title in call["input"]]
                    self.assertGreaterEqual(len(career_calls), 4)
                    multimodal = next(call["input"] for call in interactions.calls if isinstance(call["input"], list))
                    self.assertEqual(multimodal[1]["type"], "image")


if __name__ == "__main__":
    unittest.main()
