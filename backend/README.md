# NEXLINK Backend — Python/FastAPI

This is the **active NEXLINK backend**.

## Current status

Foundation implementation is substantially complete but still requires full runtime integration verification.

Implemented in this backend:

- FastAPI application
- PostgreSQL/SQLAlchemy async data layer
- User authentication and persistent sessions
- Refresh-token rotation and logout revocation
- Device enrollment and approval
- Ed25519 verification
- WebSocket device authentication
- Heartbeat and metric ingestion
- Device monitoring APIs
- Audit logging

Remote Desktop endpoints are intentionally not registered yet.

## Run locally

```bash
cd backend
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# Linux/macOS
# source .venv/bin/activate
pip install -r requirements.txt
```

Start PostgreSQL and Redis, then initialize the schema using the SQL files under:

```text
backend/migrations/postgres/
```

For Docker development:

```bash
docker compose down -v
docker compose up -d --build
```

Run the API directly:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Health endpoints:

```text
GET /health
GET /api/v1/health/ready
```

## Tests

```bash
pytest -q
ruff check app tests
python -m compileall -q app tests
```

The test suite requires the dependencies in `requirements.txt` and PostgreSQL for database-backed tests.

## Structure

```text
backend/
├── app/
│   ├── api/               # Active REST API routes
│   ├── core/              # Configuration/logging
│   ├── crypto/            # Ed25519 implementation
│   ├── database/          # Async SQLAlchemy engine/session
│   ├── main.py            # FastAPI entrypoint
│   ├── models.py          # PostgreSQL models
│   ├── schemas.py         # API schemas
│   ├── security.py        # Password/JWT/session security
│   └── websocket.py       # Agent transport/authentication
├── migrations/postgres/   # Active PostgreSQL initialization SQL
├── tests/
├── Dockerfile
├── requirements.txt
└── pyproject.toml
```

## Database ownership

The FastAPI process does **not** call `Base.metadata.create_all()` during application startup.

The checked-in PostgreSQL SQL files own the schema for the current Docker deployment model. This avoids silently mutating a deployed database at runtime.

## Security notes

- Use a strong random `JWT_SECRET_KEY` outside local development.
- Use HTTPS/WSS in production.
- Device authentication uses Ed25519 signatures.
- Enrollment tokens are stored in PostgreSQL and expire.
- Refresh tokens are hashed and stored server-side.
- Logout and refresh rotation revoke server-side sessions.
- Never log passwords, private keys, or refresh tokens.
