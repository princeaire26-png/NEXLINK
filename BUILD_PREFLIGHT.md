# NEXLINK Windows Build Preflight

This package is the source to rebuild the Windows executables.

## Required on the Windows build machine
- Windows 10/11 x64
- Python 3.12 x64
- Internet access for the first dependency install, or a prepared wheel cache
- The build script installs PyInstaller and all application runtime dependencies from `requirements-windows-build.txt`

## Build
Run PowerShell from the extracted package root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\BUILD_NEXLINK_WINDOWS.ps1
```

Expected outputs:
- `dist\\NEXLINK-Server\\NEXLINK-Server.exe`
- `dist\\NEXLINK-Client\\NEXLINK-Client.exe`
- `dist\\NEXLINK-Windows\\Server\\NEXLINK-Server.exe`
- `dist\\NEXLINK-Windows\\Client\\NEXLINK-Client.exe`
- `dist\\NEXLINK-Windows-Bundle.zip`

The executables are onedir bundles. Keep each `.exe` beside its `_internal` folder; do not copy an executable by itself.

## Runtime prerequisites
- PostgreSQL 16+ may be installed locally; NEXLINK tries it first.
- If local PostgreSQL is unavailable and Docker Desktop is installed, NEXLINK can start its isolated PostgreSQL fallback on port 55432.
- Redis is optional for the current core runtime.
- NEXLINK Server requires Windows Firewall access for TCP 8000 and UDP 39501 on Private/Domain networks.
- NEXLINK Client runs elevated because Network Guard manages Windows firewall policy.

## Acceptance checks after build
1. Run `dist\\NEXLINK-Server\\NEXLINK-Server.exe`.
2. Confirm the Command Center opens and PostgreSQL/API setup succeeds.
3. Run `dist\\NEXLINK-Client\\NEXLINK-Client.exe` on the same LAN.
4. Confirm the setup dialog finds the Server over UDP 39501.
5. Confirm the Server's "Clients detected on this LAN" table shows the Client.
6. Enroll/approve the device.
7. Confirm the device becomes ONLINE.
8. Test Network Guard, telemetry and remote-session functions.
