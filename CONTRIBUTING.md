# Contributing to NEXLINK

## Development

NEXLINK application runtime is Python-only.

Install:

```powershell
python -m pip install -r backend/requirements.txt
python -m pip install -r client/windows/requirements.txt
```

Run the backend:

```powershell
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Run the desktop client:

```powershell
python client/windows/nexlink_client.py
```

Build Windows executables:

```powershell
.\BUILD_NEXLINK_WINDOWS.ps1
```

## Structure

- `backend/` — FastAPI control plane
- `client/windows/` — PyQt6 desktop client and integrated Network Guard
- `nexlink_agent/` — authenticated Python device agent
- `nexlink_ai/` — Python AI policy/planning abstractions
- `migrations/` — PostgreSQL schema
- `docs/` — architecture/build documentation

SQL, YAML, PowerShell and PyInstaller spec files are infrastructure/build artifacts; application runtime code is Python.
