# NEXLINK Windows Build Report

## Application entry points

- **Client:** `client/windows/nexlink_client.py` — PyQt6 command center with the existing authenticated device agent.
- **Server desktop application:** `server_gui.py` — PyQt6 control panel that launches the FastAPI/Uvicorn server.
- **Server launcher and API:** `server_launcher.py` and `backend/app/main.py`.

## Packaging inputs

- **PyInstaller specifications:** `client/windows/NEXLINK-Client.spec` and `NEXLINK-Server.spec`.
- **Python requirement:** `backend/pyproject.toml` declares Python `>=3.12`; the reproducible Windows builder uses Python 3.12 x64.
- **Windows runtime dependencies:** `requirements-windows.txt`.
- **Windows build tools:** `requirements-windows-build.txt` (runtime dependencies plus PyInstaller).
- **Automated build:** `.github/workflows/build-windows.yml` runs backend tests against real PostgreSQL/Redis services, then builds and uploads three ZIP artifacts from a Windows 10/11 x64 runner.
- **Icons:** `assets/icons/nexlink-client.ico` and `assets/icons/nexlink-server.ico`. The existing Network Guard icon remains bundled for its existing UI.
- **Server runtime data:** Compose configuration and PostgreSQL migrations are included in the server bundle. Runtime configuration and generated signing secrets remain external to the executable.
- **Required runtime packages:** PyQt6, FastAPI, Uvicorn, SQLAlchemy, asyncpg, Alembic, Pydantic/email, pydantic-settings, python-jose, passlib/bcrypt, PyNaCl, Redis client, python-multipart, python-dotenv, structlog, httpx, websockets, psutil, cryptography, Pillow, PyAutoGUI, and pyperclip. PyInstaller is build-only.

## Existing remote-control implementation

The build continues to package the original agent and server WebSocket paths. The agent includes screen capture, mouse/keyboard input, clipboard synchronization, and file transfer. Server-side session creation, authorization, device approval, WebSocket authentication, and session audit records remain in the source. No mock remote-control implementation was introduced.

## Build issues found and changes made

- The prior PyInstaller specifications produced one-file builds. Both now produce onedir bundles so Qt/runtime files and application assets stay beside each named executable. The server spec is now explicitly named `NEXLINK-Server.spec`.
- Only the legacy Network Guard icon existed. Added related NEXLINK client/server icons and configured both Windows executables to use them.
- The old server spec included client-only remote-agent and desktop-input packages. Reduced its hidden-import collection to the server's FastAPI, PyQt6, Uvicorn, WebSocket, SQLAlchemy/asyncpg and NEXLINK AI modules.
- The old build script installed backend development/test tools, did not compile every runtime package, and checked one compile result after later commands had overwritten the exit status. It now uses a dedicated runtime/build requirements set, checks each command immediately, builds both onedir bundles, and runs each packaged self-test.
- The source's declared runtime floor is Python 3.12, but the old build notes allowed unspecified newer interpreters. The Windows build and CI now select Python 3.12 x64 explicitly.
- The Windows workflows previously expected one-file output paths. They now upload the complete onedir bundles and generated ZIP.
- The client setup prompt accepted a bare `host:port`, but enrollment and the background agent did not normalize it to HTTP/WebSocket URLs. A shared URL normalizer now supports bare addresses and HTTP(S)/WS(S) URLs for setup, API calls, and agent connections.
- Device identity code called a `public_key_bytes` property as a function during identity creation. It now uses the property correctly, and the packaged client self-test performs an encrypted identity save/load round trip.
- Added automated tests for accepted/rejected server addresses and encrypted device-identity round trips; these run with the existing backend pytest suite in CI.

## Verification and limits

- **Windows packaging:** must run on Windows 10/11 x64; this Linux workspace cannot produce or certify Windows `.exe` files.
- **Database services:** the server executable does not bundle Docker Desktop, PostgreSQL, or Redis. Automatic local service startup requires Docker Desktop; alternatively, use compatible PostgreSQL and Redis services already running.
- **Runtime verification:** packaged self-tests initialize both Qt windows, load configuration, check icons/Qt DLLs, and import FastAPI, AI, and remote-control modules. They deliberately do not start fake PostgreSQL/Redis services. Two-PC enrollment, Windows Firewall behavior, screen capture/input, and file transfer still require a real deployment test.
- **Existing security defaults:** first-run client identity setup still uses the source's `nexlink-local` passphrase default, and a bare server address selects unencrypted HTTP/WS. These were left unchanged to avoid altering the existing identity/configuration model; use a protected network and configure HTTPS/WSS for deployments that need transport confidentiality.
