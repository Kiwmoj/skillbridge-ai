"""Authenticated HTTP API for the native SkillBridge desktop client.

Run locally with ``uvicorn backend.main:app`` and deploy behind HTTPS in production.
Only this process reads Gemini and live-search credentials.
"""
from __future__ import annotations

import json
import re
import smtplib
import time
from contextlib import asynccontextmanager
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from uuid import uuid4

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import Settings
from backend.database import Base, database_factory
from backend.models import (AIUsage, AuthSession, PasswordResetToken, SavedOpportunity,
                            User, UserProfile, UserRecord, utcnow)
from backend.schemas import (AIRequest, AuthResponse, LoginRequest, OpportunitySaveRequest,
                             OpportunitySearchRequest, OpportunityStatusRequest,
                             PasswordResetConfirm, PasswordResetRequest, ProfileRequest,
                             RegisterRequest, UserResponse)
from backend.security import (DUMMY_PASSWORD_HASH, decode_token, hash_password,
                              hash_reset_token, issue_token, new_reset_token,
                              verify_password)
from backend.services.gemini_provider import GeminiProvider, GeminiRequestError
from backend.services.opportunity_service import OpportunitySearch


EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
RECORD_KINDS = {"assessment", "roadmap", "activity", "project", "portfolio", "setting"}


class WindowLimiter:
    """Small single-process guard; put a shared rate limiter at the edge when scaling."""
    def __init__(self):
        self.events: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, period: int) -> None:
        now = time.monotonic()
        bucket = self.events[key]
        while bucket and bucket[0] <= now - period:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(429, "Too many requests. Wait a little and try again.")
        bucket.append(now)


def _user_response(user: User) -> UserResponse:
    return UserResponse(id=user.id, email=user.email, display_name=user.display_name)


def create_app(settings: Settings | None = None, provider=None, opportunity_search=None,
               create_schema: bool = False) -> FastAPI:
    config = settings or Settings.from_environment()
    if config.database_url.startswith("sqlite:"):
        from pathlib import Path
        sqlite_path = config.database_url.removeprefix("sqlite:///")
        Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    engine, session_factory = database_factory(config.database_url)
    if create_schema:
        Base.metadata.create_all(engine)
    gemini = provider or GeminiProvider(config.gemini_api_key, config.gemini_model)
    searcher = opportunity_search or OpportunitySearch(config.brave_search_api_key)
    limiter = WindowLimiter()

    @asynccontextmanager
    async def lifespan(_app):
        yield
        engine.dispose()

    app = FastAPI(title="SkillBridge AI API", version="1.0.0", docs_url="/docs", redoc_url=None, lifespan=lifespan)
    app.state.config = config
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.gemini = gemini
    app.state.searcher = searcher
    app.state.limiter = limiter

    def get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def ensure_secret() -> None:
        if len(config.secret_key) < 32:
            raise HTTPException(503, "The service owner must configure SKILLBRIDGE_SECRET_KEY before accounts can be used.")

    def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
        ensure_secret()
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(401, "Sign in to continue.", headers={"WWW-Authenticate": "Bearer"})
        token = authorization[7:].strip()
        try:
            claims = decode_token(token, config.secret_key)
        except jwt.PyJWTError:
            raise HTTPException(401, "Your session is invalid or expired. Sign in again.", headers={"WWW-Authenticate": "Bearer"}) from None
        session = db.get(AuthSession, claims["jti"])
        if not session or session.revoked_at or session.expires_at.replace(tzinfo=timezone.utc) <= utcnow():
            raise HTTPException(401, "Your session has expired. Sign in again.", headers={"WWW-Authenticate": "Bearer"})
        user = db.get(User, claims["sub"])
        if not user:
            raise HTTPException(401, "The account for this session no longer exists.")
        return user

    def issue_auth(user: User, db: Session) -> AuthResponse:
        ensure_secret()
        token, session_id, expires = issue_token(user.id, config.secret_key)
        db.add(AuthSession(id=session_id, user_id=user.id, expires_at=expires))
        db.commit()
        return AuthResponse(access_token=token, expires_at=expires, user=_user_response(user))

    def rate(request: Request, action: str, count: int, period: int):
        host = request.client.host if request.client else "unknown"
        limiter.check(f"{action}:{host}", count, period)

    @app.get("/health")
    def health():
        return {"status": "ok", "ai_configured": bool(gemini.enabled), "live_search_configured": bool(searcher.enabled)}

    @app.post("/auth/register", response_model=AuthResponse, status_code=201)
    def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
        ensure_secret()
        rate(request, "register", 5, 3600)
        email = payload.email.strip().lower()
        if not EMAIL_RE.fullmatch(email):
            raise HTTPException(422, "Enter a valid email address.")
        if db.scalar(select(User.id).where(User.email == email)):
            raise HTTPException(409, "An account with that email already exists.")
        user = User(id=str(uuid4()), email=email, display_name=payload.display_name.strip(), password_hash=hash_password(payload.password))
        db.add(user)
        db.add(UserProfile(user_id=user.id, payload="{}"))
        db.commit()
        return issue_auth(user, db)

    @app.post("/auth/login", response_model=AuthResponse)
    def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
        ensure_secret()
        rate(request, "login", 10, 60)
        email = payload.email.strip().lower()
        user = db.scalar(select(User).where(User.email == email))
        valid = verify_password(payload.password, user.password_hash if user else DUMMY_PASSWORD_HASH)
        if not user or not valid:
            raise HTTPException(401, "Email or password is incorrect.")
        return issue_auth(user, db)

    @app.get("/auth/me", response_model=UserResponse)
    def me(user: User = Depends(current_user)):
        return _user_response(user)

    @app.post("/auth/logout", status_code=204)
    def logout(authorization: str | None = Header(default=None), db: Session = Depends(get_db), user: User = Depends(current_user)):
        claims = decode_token(authorization[7:].strip(), config.secret_key)
        session = db.get(AuthSession, claims["jti"])
        if session and session.user_id == user.id:
            session.revoked_at = utcnow()
            db.commit()
        return None

    @app.delete("/auth/me", status_code=204)
    def delete_account(payload: LoginRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
        if payload.email.strip().lower() != user.email or not verify_password(payload.password, user.password_hash):
            raise HTTPException(401, "Confirm account email and password to delete this account.")
        db.delete(user)
        db.commit()
        return None

    @app.post("/auth/password-reset/request", status_code=202)
    def request_password_reset(payload: PasswordResetRequest, request: Request, db: Session = Depends(get_db)):
        rate(request, "password_reset", 3, 3600)
        if not (config.smtp_host and config.smtp_sender):
            raise HTTPException(503, "Password recovery email is not configured on this SkillBridge service.")
        user = db.scalar(select(User).where(User.email == payload.email.strip().lower()))
        if user:
            code = new_reset_token()
            db.add(PasswordResetToken(id=str(uuid4()), user_id=user.id, token_hash=hash_reset_token(code),
                                      expires_at=utcnow() + timedelta(minutes=30)))
            db.commit()
            message = EmailMessage()
            message["Subject"] = "SkillBridge AI password reset"
            message["From"] = config.smtp_sender
            message["To"] = user.email
            message.set_content(f"Your password reset code is:\n\n{code}\n\nIt expires in 30 minutes. If you did not request this, ignore this email.")
            try:
                with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15) as smtp:
                    smtp.starttls()
                    if config.smtp_username:
                        smtp.login(config.smtp_username, config.smtp_password)
                    smtp.send_message(message)
            except Exception:
                db.rollback()
                raise HTTPException(502, "The recovery email could not be sent. Try again later.") from None
        return {"message": "If that account exists, a password reset code has been sent."}

    @app.post("/auth/password-reset/confirm", status_code=204)
    def reset_password(payload: PasswordResetConfirm, db: Session = Depends(get_db)):
        token_hash = hash_reset_token(payload.token)
        reset = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash))
        if not reset or reset.used_at or reset.expires_at.replace(tzinfo=timezone.utc) <= utcnow():
            raise HTTPException(400, "That reset code is invalid or expired.")
        user = db.get(User, reset.user_id)
        if not user:
            raise HTTPException(400, "That reset code is invalid or expired.")
        user.password_hash = hash_password(payload.new_password)
        reset.used_at = utcnow()
        db.query(AuthSession).filter(AuthSession.user_id == user.id).update({AuthSession.revoked_at: utcnow()})
        db.commit()
        return None

    @app.get("/profiles/me")
    def get_profile(user: User = Depends(current_user), db: Session = Depends(get_db)):
        row = db.get(UserProfile, user.id)
        return {"profile": json.loads(row.payload) if row else {}}

    @app.put("/profiles/me")
    def save_profile(payload: ProfileRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
        if len(json.dumps(payload.profile, ensure_ascii=False)) > 40000:
            raise HTTPException(413, "The profile is too large.")
        row = db.get(UserProfile, user.id)
        if not row:
            row = UserProfile(user_id=user.id, payload="{}")
            db.add(row)
        row.payload = json.dumps(payload.profile, ensure_ascii=False)
        row.updated_at = utcnow()
        db.commit()
        return {"profile": payload.profile}

    def use_ai_quota(user: User, db: Session):
        today = utcnow().date().isoformat()
        row = db.scalar(select(AIUsage).where(AIUsage.user_id == user.id, AIUsage.usage_day == today))
        if row and row.request_count >= config.ai_daily_limit:
            raise HTTPException(429, f"Your daily AI request limit ({config.ai_daily_limit}) has been reached. Try again tomorrow.")
        if row:
            row.request_count += 1
        else:
            db.add(AIUsage(user_id=user.id, usage_day=today, request_count=1))
        db.commit()

    def generate(payload: AIRequest, request: Request, user: User, db: Session):
        rate(request, "ai", 12, 60)
        if not gemini.enabled:
            raise HTTPException(503, "The SkillBridge service owner has not configured Gemini. No AI response was generated.")
        if len(json.dumps(payload.response_schema)) > 20000:
            raise HTTPException(422, "The requested response format is too large.")
        if payload.image_base64:
            if not payload.image_mime_type:
                raise HTTPException(422, "An image MIME type is required when sending an image.")
            if len(payload.image_base64) > 8_000_000:
                raise HTTPException(413, "Portfolio images must be 6 MB or smaller.")
            import base64, binascii
            try:
                decoded = base64.b64decode(payload.image_base64, validate=True)
            except (ValueError, binascii.Error):
                raise HTTPException(422, "The uploaded image data is invalid.") from None
            if len(decoded) > 6_000_000:
                raise HTTPException(413, "Portfolio images must be 6 MB or smaller.")
        use_ai_quota(user, db)
        try:
            return gemini.generate_json(payload.prompt, payload.response_schema, payload.image_base64, payload.image_mime_type)
        except GeminiRequestError as exc:
            raise HTTPException(502, str(exc)) from None
        except Exception:
            raise HTTPException(502, "Gemini could not complete this request. Check service configuration and try again.") from None

    @app.post("/ai/generate")
    def ai_generate(payload: AIRequest, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
        return generate(payload, request, user, db)

    @app.post("/ai/test")
    def ai_test(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
        probe = AIRequest(prompt='Return exactly {"connected": true}.', response_schema={
            "type": "object", "properties": {"connected": {"type": "boolean"}}, "required": ["connected"]})
        result = generate(probe, request, user, db)
        if result.get("connected") is not True:
            raise HTTPException(502, "Gemini responded, but the connection check was invalid.")
        return {"connected": True, "message": "Gemini returned a live response."}

    @app.post("/opportunities/search")
    def search_opportunities(payload: OpportunitySearchRequest, request: Request,
                             user: User = Depends(current_user)):
        rate(request, "opportunity_search", 20, 60)
        if not searcher.enabled:
            raise HTTPException(503, "Live opportunity search is not configured. No opportunities were fabricated.")
        try:
            return {"results": searcher.search(payload.query, payload.career, payload.category,
                                                 payload.location, payload.education_level, payload.limit)}
        except RuntimeError as exc:
            raise HTTPException(502, str(exc)) from None
        except Exception:
            raise HTTPException(502, "Live opportunity search is temporarily unavailable.") from None

    @app.get("/opportunities/saved")
    def list_saved_opportunities(user: User = Depends(current_user), db: Session = Depends(get_db)):
        rows = db.scalars(select(SavedOpportunity).where(SavedOpportunity.user_id == user.id)
                          .order_by(SavedOpportunity.retrieved_at.desc())).all()
        return {"results": [{"id": row.id, "title": row.title, "source_url": row.source_url,
                              "source_name": row.source_name, "category": row.category, "location": row.location,
                              "deadline": row.deadline, "eligibility": row.eligibility,
                              "retrieved_at": row.retrieved_at.isoformat(), "application_status": row.application_status}
                             for row in rows]}

    @app.post("/opportunities/saved", status_code=201)
    def save_opportunity(payload: OpportunitySaveRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
        if not payload.source_url.startswith("https://"):
            raise HTTPException(422, "Only secure HTTPS opportunity links can be saved.")
        existing = db.scalar(select(SavedOpportunity).where(SavedOpportunity.user_id == user.id,
                                                             SavedOpportunity.source_url == payload.source_url))
        if existing:
            return {"id": existing.id, "saved": True}
        row = SavedOpportunity(id=str(uuid4()), user_id=user.id, title=payload.title,
                               source_url=payload.source_url, source_name=payload.source_name,
                               category=payload.category, location=payload.location, deadline=payload.deadline,
                               eligibility=payload.eligibility,
                               retrieved_at=payload.retrieved_at or utcnow())
        db.add(row)
        db.commit()
        return {"id": row.id, "saved": True}

    @app.patch("/opportunities/saved/{opportunity_id}")
    def update_saved_opportunity(opportunity_id: str, payload: OpportunityStatusRequest,
                                 user: User = Depends(current_user), db: Session = Depends(get_db)):
        row = db.scalar(select(SavedOpportunity).where(SavedOpportunity.id == opportunity_id,
                                                        SavedOpportunity.user_id == user.id))
        if not row:
            raise HTTPException(404, "Saved opportunity was not found.")
        row.application_status = payload.application_status
        db.commit()
        return {"id": row.id, "application_status": row.application_status}

    @app.delete("/opportunities/saved/{opportunity_id}", status_code=204)
    def delete_saved_opportunity(opportunity_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
        row = db.scalar(select(SavedOpportunity).where(SavedOpportunity.id == opportunity_id,
                                                        SavedOpportunity.user_id == user.id))
        if not row:
            raise HTTPException(404, "Saved opportunity was not found.")
        db.delete(row)
        db.commit()
        return None

    @app.get("/records/{kind}")
    def list_records(kind: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
        if kind not in RECORD_KINDS:
            raise HTTPException(404, "Record type was not found.")
        rows = db.scalars(select(UserRecord).where(UserRecord.user_id == user.id, UserRecord.kind == kind)
                          .order_by(UserRecord.updated_at.desc())).all()
        return {"records": [{"key": row.record_key, "payload": json.loads(row.payload),
                              "updated_at": row.updated_at.isoformat()} for row in rows]}

    @app.put("/records/{kind}/{record_key}")
    def save_record(kind: str, record_key: str, payload: dict,
                    user: User = Depends(current_user), db: Session = Depends(get_db)):
        if kind not in RECORD_KINDS or len(record_key) > 120:
            raise HTTPException(422, "The record type or key is invalid.")
        if len(json.dumps(payload, ensure_ascii=False)) > 100_000:
            raise HTTPException(413, "The record is too large.")
        row = db.scalar(select(UserRecord).where(UserRecord.user_id == user.id,
                                                 UserRecord.kind == kind, UserRecord.record_key == record_key))
        if row:
            row.payload = json.dumps(payload, ensure_ascii=False)
            row.updated_at = utcnow()
        else:
            row = UserRecord(id=str(uuid4()), user_id=user.id, kind=kind, record_key=record_key,
                             payload=json.dumps(payload, ensure_ascii=False))
            db.add(row)
        db.commit()
        return {"key": row.record_key, "payload": payload}

    @app.delete("/records/{kind}/{record_key}", status_code=204)
    def delete_record(kind: str, record_key: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
        row = db.scalar(select(UserRecord).where(UserRecord.user_id == user.id,
                                                 UserRecord.kind == kind, UserRecord.record_key == record_key))
        if not row:
            raise HTTPException(404, "Record was not found.")
        db.delete(row)
        db.commit()
        return None

    return app


app = create_app()
