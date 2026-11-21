import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication, QLineEdit, QLabel

from database.db_manager import Database
from ui.main_window import MainWindow


class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

    def test_first_launch_onboards_custom_career_and_opens_gemini_setup(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"GEMINI_API_KEY":""}):
            db = Database(Path(temp) / "db.sqlite3")
            window = MainWindow(db)
            self.assertEqual(window.stack.currentWidget(), window.pages["Student setup"])
            self.assertFalse(window.sidebar.isVisible())
            self.assertFalse(db.has_profile())
            self.assertEqual(db.get_skills(), [])
            self.assertFalse(window.career_button.isEnabled())
            self.assertIn("Gemini setup", window.pages)

            window.setup_name.setText("Taylor")
            window.setup_education.setText("Community college")
            window.setup_career.setCurrentText("Marine Biologist")
            window.setup_industry.setCurrentText("Science")
            window.setup_skills.setText("Research, Field observation")
            window._create_profile()
            self.assertTrue(db.has_profile())
            self.assertEqual(db.get_profile().career_goal, "Marine Biologist")
            self.assertEqual(db.get_profile().education_level, "Community college")
            self.assertEqual(window.stack.currentWidget(), window.pages["Gemini setup"])
            self.assertIn("GEMINI SETUP REQUIRED", window.mode_label.text())
            self.assertEqual({skill.name for skill in db.get_skills()}, {"Research", "Field observation"})
            window.navigate("Career reality check")
            self.assertEqual(window.career_goal_input.currentText(), "Marine Biologist")
            window.career_goal_input.setCurrentText("Urban Planner")
            window._start_career_analysis()
            self.assertEqual(db.get_profile().career_goal, "Urban Planner")
            self.assertEqual(window.profile_goal.currentText(), "Urban Planner")
            self.assertEqual(window.career_a.currentText(), "Urban Planner")
            self.assertEqual(window.stack.currentWidget(), window.pages["Gemini setup"])
            window.close()

    def test_gemini_setup_masks_and_saves_credential_once(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"GEMINI_API_KEY":"", "GOOGLE_API_KEY":""}), \
                patch("services.gemini_service.read_gemini_api_key", return_value=""), \
                patch("ui.main_window.save_gemini_api_key") as save_key, \
                patch("ui.main_window.MainWindow._test_gemini_connection") as test_connection:
            db = Database(Path(temp) / "db.sqlite3")
            window = MainWindow(db)
            window.navigate("Gemini setup")
            self.assertEqual(window.gemini_key_input.echoMode(), QLineEdit.EchoMode.Password)
            self.assertFalse(window.gemini_test_button.isEnabled())
            window.gemini_key_input.setText("one-time-test-key")
            with patch.object(window.gemini, "reload_credentials", side_effect=lambda: setattr(window.gemini, "api_key", "one-time-test-key")):
                window._save_and_test_gemini()
            save_key.assert_called_once_with("one-time-test-key")
            test_connection.assert_called_once()
            self.assertTrue(window.gemini.enabled)
            self.assertTrue(window.gemini_test_button.isEnabled())
            self.assertEqual(window.mode_label.text(), "LIVE GEMINI API")
            self.assertEqual(window.gemini_key_input.text(), "")
            visible_text = " ".join(label.text() for label in window.findChildren(QLabel))
            self.assertNotIn("one-time-test-key", visible_text)
            window.close()


if __name__ == "__main__": unittest.main()
