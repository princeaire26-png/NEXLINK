# NEXLINK Windows 2.1

## What changed

- Fixed the packaged Client crash caused by `nexlink_agent.service` not being collected by PyInstaller.
- Explicitly collects all NEXLINK Agent/Guard/AI submodules and package data.
- Fixed the endpoint Agent's missing `subprocess` import, which previously broke authorized restart/service/software actions.
- Normalized endpoint Server addresses so `192.168.1.20:8000`, `http://...`, and `ws://.../ws` all work.
- Server now validates a real PostgreSQL connection rather than only checking whether port 5432 is open.
- Server starts installed PostgreSQL Windows services when possible.
- If local PostgreSQL is unavailable and Docker Desktop exists, NEXLINK can start Docker Desktop and an isolated NEXLINK PostgreSQL/Redis stack.
- Docker PostgreSQL uses port 55432 and Redis uses 56379 so it does not collide with a local PostgreSQL installation on 5432.
- Server automatically provisions the NEXLINK PostgreSQL schema and records migrations.
- Existing older NEXLINK databases are recognized without replaying the initial non-idempotent migration.
- Added first-owner account creation to the Server Command Center login screen.
- Added a native Inno Setup installer definition with Start Menu shortcuts and optional Windows startup.

## Deployment model

### Existing PostgreSQL

NEXLINK first tries the configured PostgreSQL connection. If it works, Docker is not required.

### Docker Desktop

If PostgreSQL cannot be used and Docker Desktop is installed, NEXLINK attempts to start Docker Desktop and then starts its own PostgreSQL/Redis containers.

### Neither installed

NEXLINK reports a setup error with the exact missing prerequisite. It does not silently fail as the old build did.

NEXLINK does not redistribute third-party Docker Desktop or PostgreSQL installers. Install either PostgreSQL 16+ or Docker Desktop before first use when the computer has neither.
