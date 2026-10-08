# NEXLINK Windows Build Preflight

This package is the source to rebuild the Windows executables.

## Required on the Windows build machine
- Windows 10/11 x64
- Python 3.11+
- Internet access for the first dependency install, or a prepared wheel cache
- PyInstaller (the build script installs it)
- PyQt6 and all packages in `backend/requirements.txt` and `client/windows/requirements.txt`
- Inno Setup 6 only if you want `NEXLINK-Setup.exe`

## Build
Run PowerShell from the extracted package root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\BUILD_NEXLINK_WINDOWS.ps1
```

Expected outputs:
- `dist\\NEXLINK-Server.exe`
- `dist\\client\\NEXLINK-Client.exe`
- `installer-output\\NEXLINK-Setup.exe` when Inno Setup is installed

## Runtime prerequisites
- PostgreSQL 16+ may be installed locally; NEXLINK tries it first.
- If local PostgreSQL is unavailable and Docker Desktop is installed, NEXLINK can start its isolated PostgreSQL fallback on port 55432 and Redis on 56379.
- Redis is optional for the current core runtime.
- NEXLINK Server requires Windows Firewall access for TCP 8000 and UDP 39501 on Private/Domain networks.
- NEXLINK Client runs elevated because Network Guard manages Windows firewall policy.

## Acceptance checks after build
1. Run `dist\\NEXLINK-Server.exe`.
2. Confirm the Command Center opens and PostgreSQL/API setup succeeds.
3. Run `dist\\client\\NEXLINK-Client.exe` on the same LAN.
4. Confirm it discovers the Server automatically over UDP 39501.
5. Confirm the Server shows the Client in LAN discovery.
6. Enroll/approve the device.
7. Confirm the device becomes ONLINE.
8. Test Network Guard, telemetry and remote-session functions.
