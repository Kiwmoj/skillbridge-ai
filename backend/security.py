"""Password hashing and revocable HS256 bearer tokens."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from pwdlib import PasswordHash

password_hasher = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = password_hasher.hash("not-a-real-user-password")


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    try:
        return password_hasher.verify(password, encoded)
    except Exception:
        return False


def issue_token(user_id: str, secret_key: str, ttl_hours: int = 12) -> tuple[str, str, datetime]:
    now = datetime.now(timezone.utc)
    session_id = str(uuid4())
    expires = now + timedelta(hours=ttl_hours)
    token = jwt.encode({"sub": user_id, "jti": session_id, "iat": now, "exp": expires}, secret_key, algorithm="HS256")
    return token, session_id, expires


def decode_token(token: str, secret_key: str) -> dict:
    return jwt.decode(token, secret_key, algorithms=["HS256"], options={"require": ["sub", "jti", "exp"]})


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_reset_token() -> str:
    return secrets.token_urlsafe(32)
