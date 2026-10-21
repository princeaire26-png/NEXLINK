# NEXLINK Windows Build

## Requirements

- Windows 10/11 x64
- Python 3.12 x64 for building only
- Docker Desktop for automatic local PostgreSQL/Redis startup, or compatible PostgreSQL and Redis services already running
- Internet access during the build to install Python dependencies

## Build

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\BUILD_NEXLINK_WINDOWS.ps1
```

The script installs only the Windows runtime/build dependencies, compiles the source tree, creates onedir PyInstaller bundles, and runs both packaged self-tests. End users do not need Python.

## Result

```text
dist\NEXLINK-Server\NEXLINK-Server.exe
dist\NEXLINK-Client\NEXLINK-Client.exe
dist\NEXLINK-Client-Windows.zip
dist\NEXLINK-Server-Windows.zip
dist\NEXLINK-Windows-Bundle.zip
```

The combined ZIP expands to `NEXLINK-Windows\Client`, `NEXLINK-Windows\Server`, and `README.txt`. Each app folder keeps its executable beside `_internal`, plus `assets\` and a `config\README.txt` that contains no secrets.

Keep each executable with its adjacent `_internal` folder; do not copy an `.exe` out of its bundle. The client contains the authenticated agent, existing screen/input/file-transfer code, RMM features and Network Guard. The server contains the FastAPI control plane, desktop management UI, migrations, and Compose configuration. There is no separate InternetGuard executable.

The server executable does not bundle Docker Desktop, PostgreSQL, or Redis. Its automatic infrastructure option uses an installed Docker Desktop; alternatively, configure and start compatible local database/cache services before launching NEXLINK Server.

## First Windows verification

1. Run `NEXLINK-Server.exe` from its bundle folder.
2. Confirm PostgreSQL/Redis become reachable.
3. Open `NEXLINK-Client.exe` as Administrator.
4. Create an enrollment token and enroll a second Windows PC.
5. Approve the device.
6. Verify ONLINE status and real CPU/RAM/disk metrics.
7. Open Devices / Remote and verify screen capture and input.
8. Verify Network Guard blocks Internet while the NEXLINK LAN connection remains available.

The packaged `--self-test` checks run automatically during a build. They initialize both Qt windows, load the application configuration, check embedded icons/Qt libraries, and import the FastAPI and remote-control modules without pretending that PostgreSQL/Redis are running. They do not replace a two-PC, Windows Firewall, Docker, and remote-control integration test.
