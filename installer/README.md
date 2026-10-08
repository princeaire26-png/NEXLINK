# NEXLINK Windows Installer

Build the two PyInstaller executables first, then compile `NEXLINK-Setup.iss` with Inno Setup 6.

The installer creates Start Menu entries for **NEXLINK Server** and **NEXLINK Client**.

Server startup behavior:

1. Use an already-working local PostgreSQL installation when available.
2. If local PostgreSQL cannot be used and Docker Desktop is installed, NEXLINK starts Docker Desktop and its isolated PostgreSQL/Redis containers.
3. Docker PostgreSQL uses port `55432` and Redis uses `56379`, so a local PostgreSQL installation on `5432` is never overwritten.
4. NEXLINK provisions its schema automatically on first successful database connection.
5. Redis is optional for the current core runtime.

NEXLINK does not redistribute Docker Desktop or PostgreSQL installers. If neither is installed, install PostgreSQL 16+ or Docker Desktop before first launch.
