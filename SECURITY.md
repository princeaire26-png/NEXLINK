# NEXLINK Current Architecture

NEXLINK application runtime is Python-only: FastAPI backend, PyQt6 desktop client, bundled Python device agent, Python AI policy/planning, and integrated Windows Network Guard.

Security-critical controls include Ed25519 device authentication, signed enrollment, JWT user authentication, approved-device gating, revocation, WebSocket heartbeats, server-enforced Network Guard policy, and fail-closed remote blocking.

See `README.md`, `BUILD_WINDOWS.md`, and `docs/PYTHON_MIGRATION_COMPLETE.md`.
