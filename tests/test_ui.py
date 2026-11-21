import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
import unittest
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from database.db_manager import Database
from services.api_client import ApiClient, ApiError
from ui.main_window import MainWindow


class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_first_launch_requires_service_sign_in_and_never_requests_a_gemini_key(self):
        with tempfile.TemporaryDirectory() as temp:
            window = MainWindow(Database(Path(temp) / "db.sqlite3"))
            self.assertEqual(window.stack.currentWidget(), window.pages["Service & account"])
            self.assertFalse(window.sidebar.isVisible())
            self.assertFalse(window.db.has_profile())
            self.assertFalse(window.gemini.enabled)
            self.assertFalse(hasattr(window, "gemini_key_input"))
            self.assertIn("Opportunities & Colleges", window.pages)
            window.close()

    def test_account_session_unlocks_custom_career_profile_and_syncs_to_service(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Database(Path(temp) / "db.sqlite3")
            window = MainWindow(db)
            window.api_client.set_base_url("http://127.0.0.1:8000")
            window.api_client.register = lambda email, name, password: {
                "access_token": "unit-test-token", "user": {"id": "user-one", "email": email, "display_name": name}}
            window.api_client.get_profile = lambda: {}
            synced = []
            window.api_client.save_profile = lambda profile: synced.append(profile)
            window.session_store.save = lambda _token, _user: None
            window.account_name.setText("Taylor")
            window.account_email.setText("taylor@example.org")
            window.account_password.setText("Safe-test-password-123")
            window._account_action(create=True)
            self.assertEqual(window.stack.currentWidget(), window.pages["Student setup"])
            self.assertTrue(window.gemini.enabled)

            window.setup_name.setText("Taylor")
            window.setup_education.setText("Community college")
            window.setup_career.setCurrentText("Marine Biologist")
            window.setup_industry.setCurrentText("Science")
            window.setup_skills.setText("Research, Field observation")
            window._create_profile()
            self.assertEqual(db.get_profile().career_goal, "Marine Biologist")
            self.assertEqual(window.stack.currentWidget(), window.pages["Overview"])
            self.assertEqual(synced[-1]["career_goal"], "Marine Biologist")
            window._apply_career_selection("Urban Planner", "Science")
            self.assertEqual(db.get_profile().career_goal, "Urban Planner")
            self.assertGreaterEqual(len(synced), 2)
            window.close()

    def test_service_url_requires_tls_except_local_development(self):
        self.assertEqual(ApiClient.validate_url("http://localhost:8000"), "http://localhost:8000")
        self.assertEqual(ApiClient.validate_url("https://skillbridge.example.org/"), "https://skillbridge.example.org")
        with self.assertRaisesRegex(ApiError, "requires HTTPS"):
            ApiClient.validate_url("http://skillbridge.example.org")
        with self.assertRaises(ApiError):
            ApiClient.validate_url("https://user:password@example.org")


if __name__ == "__main__":
    unittest.main()
