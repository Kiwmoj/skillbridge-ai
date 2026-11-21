import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from services import gemini_credentials


class GeminiCredentialTests(unittest.TestCase):
    def test_google_api_key_precedes_gemini_api_key(self):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "google-test-key", "GEMINI_API_KEY": "gemini-test-key"}), \
                patch.object(gemini_credentials, "load_local_environment"), \
                patch.dict(sys.modules, {"keyring": None}):
            self.assertEqual(gemini_credentials.read_gemini_api_key(), "google-test-key")

    def test_system_credential_is_loaded_when_environment_is_empty(self):
        fake_keyring = types.SimpleNamespace(
            get_password=lambda service, username: "stored-test-key"
        )
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "", "GEMINI_API_KEY": ""}), \
                patch.object(gemini_credentials, "load_local_environment"), \
                patch.dict(sys.modules, {"keyring": fake_keyring}):
            self.assertEqual(gemini_credentials.read_gemini_api_key(), "stored-test-key")

    def test_project_env_is_loaded_from_the_app_path_without_overriding_real_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, ".env").write_text("GEMINI_API_KEY=project-test-key\nGEMINI_MODEL=gemini-test-model\n", encoding="utf-8")
            with patch.object(gemini_credentials, "PROJECT_ROOT", Path(temp)), \
                    patch.dict(os.environ, {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": "", "GEMINI_MODEL": ""}):
                self.assertEqual(gemini_credentials.read_gemini_api_key(), "project-test-key")
                self.assertEqual(os.environ["GEMINI_MODEL"], "gemini-test-model")

    def test_key_is_saved_and_verified_through_secure_backend(self):
        saved = {}

        class SecureBackend:
            priority = 1

        SecureBackend.__module__ = "keyring.backends.Windows"

        fake_keyring = types.SimpleNamespace(
            get_keyring=lambda: SecureBackend(),
            set_password=lambda service, username, value: saved.update({(service, username): value}),
            get_password=lambda service, username: saved.get((service, username)),
        )
        with patch.dict(sys.modules, {"keyring": fake_keyring}):
            gemini_credentials.save_gemini_api_key(" one-time-test-key ")
        self.assertEqual(len(saved), 1)
        self.assertEqual(next(iter(saved.values())), "one-time-test-key")

    def test_insecure_or_unavailable_backend_is_rejected(self):
        set_called = []
        fake_keyring = types.SimpleNamespace(
            get_keyring=lambda: types.SimpleNamespace(priority=0),
            set_password=lambda *args: set_called.append(args),
        )
        with patch.dict(sys.modules, {"keyring": fake_keyring}):
            with self.assertRaisesRegex(gemini_credentials.CredentialStorageError, "secure credential store"):
                gemini_credentials.save_gemini_api_key("one-time-test-key")
        self.assertEqual(set_called, [])


if __name__ == "__main__":
    unittest.main()
