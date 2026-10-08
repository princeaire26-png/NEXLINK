# NEXLINK Windows Build

## Requirements

- Windows 10/11
- Python 3.12+
- Docker Desktop (recommended for bundled PostgreSQL/Redis)

## Build

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\BUILD_NEXLINK_WINDOWS.ps1
```

The script installs declared Python dependencies, compiles the source tree, builds both PyInstaller applications and runs both package self-tests.

## Result

```text
dist\NEXLINK-Server.exe
dist\client\NEXLINK-Client.exe
```

The Python agent, remote-access implementation, RMM features, AI policy layer and Network Guard are bundled into the two applications. There is no separate InternetGuard executable.

## First Windows verification

1. Run `NEXLINK-Server.exe --auto-infra`.
2. Confirm PostgreSQL/Redis become reachable.
3. Open `NEXLINK-Client.exe` as Administrator.
4. Create an enrollment token and enroll a second Windows PC.
5. Approve the device.
6. Verify ONLINE status and real CPU/RAM/disk metrics.
7. Open Devices / Remote and verify screen capture and input.
8. Verify Network Guard blocks Internet while the NEXLINK LAN connection remains available.
