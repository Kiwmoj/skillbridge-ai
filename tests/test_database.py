import json
import tempfile
import unittest
from pathlib import Path

from database.db_manager import Database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "skillbridge.sqlite3"

    def tearDown(self):
        self.temp.cleanup()

    def test_first_run_is_empty_and_profile_progress_persists(self):
        db = Database(self.path)
        self.assertFalse(db.has_profile())
        self.assertEqual(db.get_profile().career_goal, "")
        self.assertEqual(db.get_skills(), [])
        self.assertEqual(db.get_activities(), [])
        self.assertEqual(db.get_projects(), [])
        self.assertEqual(db.get_reviews(), [])

        db.save_profile("Riley", "Custom Materials Engineer", "College", "Beginner", ["Research", "CAD"], "Science")
        self.assertEqual([s.name for s in db.get_skills()], ["CAD", "Research"])
        db.save_skill("CAD", 45, 80, "Essential", "Model components", "Build a simple part")
        activity_id = db.add_activity({"stage":"Beginner", "title":"Material comparison", "description":"Compare fictional samples", "learning_objective":"Practice evidence-based material selection", "skills":["Research"], "duration":"1 week", "difficulty":"Beginner", "outcome":"A comparison table", "career_goal":"Custom Materials Engineer"})
        db.update_activity_status(activity_id, "Completed")
        project_id = db.add_project({"title":"Bridge study", "description":"Compare fictional structural options", "category":"Custom Materials Engineer", "skills":["CAD"], "details":{"deliverable":"Study"}})
        db.update_project_status(project_id, "Completed")
        db.add_review("Study", "work.png", {"source_mode":"LIVE GEMINI IMAGE REVIEW"})
        db.add_recommendation("Custom Materials Engineer", "Science", "career_reality_check", {"overview":"Generated"})

        reopened = Database(self.path)
        self.assertTrue(reopened.has_profile())
        self.assertEqual(reopened.get_profile().education_level, "College")
        self.assertEqual(reopened.get_profile().existing_skills, ["Research", "CAD"])
        self.assertEqual(reopened.get_skills()[0].proficiency, 45)
        self.assertEqual(reopened.get_activities()[0].learning_objective, "Practice evidence-based material selection")
        self.assertEqual(reopened.get_activities()[0].status, "Completed")
        self.assertEqual(reopened.get_projects()[0].status, "Completed")
        self.assertEqual(reopened.analytics()["review_count"], 1)
        self.assertEqual(reopened.get_recommendations(kind="career_reality_check")[0]["source_mode"], "LIVE GEMINI API")

    def test_custom_profile_is_not_cleared_by_seed_migration(self):
        db = Database(self.path)
        db.save_profile("Alex Morgan", "Custom Engineer", "College", "Beginner", ["Testing"], "Technology")
        with db.connect() as con:
            con.execute("UPDATE profiles SET demo_mode=1 WHERE id=1")
        reopened = Database(self.path)
        self.assertTrue(reopened.has_profile())
        self.assertEqual(reopened.get_profile().career_goal, "Custom Engineer")

    def test_known_seed_profile_and_sample_records_are_removed(self):
        db = Database(self.path)
        with db.connect() as con:
            con.execute("INSERT INTO profiles(id,name,career_goal,experience,interests,demo_mode,industry) VALUES(1,?,?,?,?,1,?)", ("Alex Morgan", "Explore careers", "Beginner", json.dumps(["Problem solving", "Creative thinking", "Research"]), "Other / custom"))
            con.execute("INSERT INTO career_skills(career_goal,name,proficiency,target) VALUES('Explore careers','Sample skill',30,70)")
            con.execute("INSERT INTO activity_log(message) VALUES('sample activity')")
        reopened = Database(self.path)
        self.assertFalse(reopened.has_profile())
        self.assertEqual(reopened.get_skills(), [])
        self.assertEqual(reopened.get_recent_activity(), [])


if __name__ == "__main__":
    unittest.main()
