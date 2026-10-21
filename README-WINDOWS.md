# NEXLINK Windows Applications

Build the two self-contained application folders with `BUILD_NEXLINK_WINDOWS.ps1` on Windows 10/11 x64 using Python 3.12. End users do not need Python.

The repository-level `NEXLINK Windows Build` workflow runs backend tests with real PostgreSQL/Redis services, creates a Python virtual environment on `windows-latest`, builds and smoke-tests both applications, and uploads three downloadable ZIP artifacts.

The artifacts are `NEXLINK-Client-Windows.zip`, `NEXLINK-Server-Windows.zip`, and `NEXLINK-Windows-Bundle.zip`. The first two contain the complete corresponding onedir bundle, not a lone executable.

- `dist\NEXLINK-Server\NEXLINK-Server.exe`
- `dist\NEXLINK-Client\NEXLINK-Client.exe`
- `dist\NEXLINK-Windows-Bundle.zip`

Keep each executable beside its `_internal` folder. The client bundles the authenticated Python agent and remote-control implementation. The server uses Docker Desktop for automatic local PostgreSQL/Redis startup, or can use those services when already running.


## Desktop windows

`NEXLINK-Server.exe` opens the NEXLINK Server control panel and runs FastAPI/Uvicorn in the background. `NEXLINK-Client.exe` opens the PyQt6 client dashboard. Both run without a console window and request Windows administrator access.
