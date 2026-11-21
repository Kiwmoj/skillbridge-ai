"""Persist only short-lived account tokens in the OS credential store."""
from __future__ import annotations

import json
import uuid


class SessionStore:
    SERVICE = "SkillBridge AI Account Session"
    ACCOUNT = "desktop-session"

    def __init__(self):
        self._memory_token = ""
        self._memory_user = None

    def load(self):
        try:
            import keyring
            raw = keyring.get_password(self.SERVICE, self.ACCOUNT)
            if raw:
                data = json.loads(raw)
                return data.get("token", ""), data.get("user")
        except Exception:
            pass
        return self._memory_token, self._memory_user

    def save(self, token: str, user: dict):
        self._memory_token, self._memory_user = token, user
        try:
            import keyring
            keyring.set_password(self.SERVICE, self.ACCOUNT,
                                 json.dumps({"token": token, "user": user}, separators=(",", ":")))
        except Exception:
            # The session remains active until exit; do not move it to a plain file.
            pass

    def clear(self):
        self._memory_token, self._memory_user = "", None
        try:
            import keyring
            keyring.delete_password(self.SERVICE, self.ACCOUNT)
        except Exception:
            pass
