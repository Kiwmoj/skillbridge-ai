# SkillBridge AI

SkillBridge AI is a native Python/PyQt6 career-development application. It stores student work in SQLite and sends AI requests through an authenticated SkillBridge service. The service is the only component that holds a Gemini credential.

## Implemented workflows

- Searchable career picker with custom career entry and shared profile career across the existing explorer, reality check, skill gap, roadmap, portfolio, and project workflows.
- Account registration, sign-in, sign-out, password reset email, account deletion API, and hashed passwords.
- Per-user local SQLite files and owner-scoped service profiles, generated records, saved opportunities, and request quotas.
- Central structured Gemini API with image input for portfolio review, input validation, timeouts, quota messages, and no sample response fallback.
- Live opportunity search through a configured web-search provider. Results show the source URL and retrieval time; deadlines, eligibility, and locations are explicitly unverified. Search returns no invented results when not configured.
- Local analytics continue to use actual saved records. Generated guidance and profile updates are also synchronized to the service when the account is connected.

The existing desktop pages remain native PyQt6. The service API uses FastAPI and SQLAlchemy. This repository is a working development foundation, not a deployed multi-region production service: a service host, Gemini credential, email sender, live-search credential, TLS endpoint, and production database must be configured by the project owner.

## Desktop setup

1. Install Python 3.11 or newer.
2. Create and activate a virtual environment.
3. Install dependencies: `python -m pip install -r requirements.txt`.
4. Configure the service URL in `SKILLBRIDGE_API_URL`, in the root `.env`, or from **Service & account** in the app. Use HTTPS for hosted services. Local development may use `http://127.0.0.1:8000`.
5. Run `python main.py`, connect, create an account or sign in, then create or edit the student profile.

The access token is stored in the operating system credential store when available. If that store is unavailable, the app keeps the token in memory until it closes. The app does not store a Gemini key. Each signed-in account gets its own local SQLite database under `data/accounts/`. The first account on an existing installation claims the prior unscoped local database; later accounts receive separate files.

## Backend setup

1. Copy `backend/.env.example` to `backend/.env` on the service host. This file is ignored by Git.
2. Set `GEMINI_API_KEY` to the service owner's Gemini credential and choose a supported model in `GEMINI_MODEL`. Students never enter this value.
3. Generate an authentication signing secret (this is not a Gemini credential) with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Put it in `SKILLBRIDGE_SECRET_KEY`.
4. Keep SQLite for local development. For a hosted multi-user deployment, set `SKILLBRIDGE_SERVER_DATABASE_URL` to a managed PostgreSQL URL and install the included PostgreSQL driver.
5. From the repository root, run `alembic upgrade head`, then start the service with `uvicorn backend.main:app --host 127.0.0.1 --port 8000`.
6. Put a production service behind a TLS reverse proxy and expose only HTTPS to desktop clients. Use a shared edge rate limiter when running multiple service workers.

The API exposes `/health` for non-secret service capability status and `/docs` for development API documentation. The desktop **Test live Gemini connection** action makes a real authenticated Gemini request. A missing or rejected service credential produces an error; the app does not switch to canned guidance.

### Optional services

- Set `BRAVE_SEARCH_API_KEY` on the backend to enable live opportunity search. Without a configured search credential, the service returns an explicit unavailable message.
- Set the `SKILLBRIDGE_SMTP_*` variables to enable password-reset email. Password reset remains unavailable until SMTP is configured.
- `SKILLBRIDGE_AI_DAILY_LIMIT` defaults to 40 requests per account per UTC day.

## Configuration and privacy

- Desktop URL: root `.env` or `data/desktop-settings.json` (the app writes only the service URL).
- Server credentials: backend process environment or private `backend/.env` only.
- SQLite databases and account settings: `data/`, ignored by Git.
- Gemini keys, passwords, and bearer tokens are not written to application logs. The backend sanitizes provider errors before returning them.
- Image uploads are size and MIME-type checked and sent to the server only when the student starts portfolio review. This implementation does not retain the image on the service.

## Run tests

```powershell
python -m pytest -q
```

Tests cover career-specific local feature flows, account security and isolation, service failures, rate limits, opportunities, and desktop service setup. A real Gemini request can only be tested when a valid backend credential and network access are configured. Automated tests use a fake transport/provider for deterministic checks and do not represent live Gemini responses.

## Limitations to resolve before public student deployment

- This repository does not include a hosted backend URL or server-owned Gemini/search/SMTP credentials. Configure those privately before expecting live AI, opportunity search, or account recovery.
- Production deployment still needs TLS, a managed database, backups, shared rate limiting, monitoring, and an operational email provider.
- Desktop feature records are kept in per-account local SQLite and mirrored to owner-scoped server records. The app does not currently download a full cross-device history to reconstruct roadmap progress on a new device.
- Search results are sourced from a web index and are not independently verified. Official links and current details must be checked before applying.
- Do not enter personal medical, client, or other protected records into portfolio review.
