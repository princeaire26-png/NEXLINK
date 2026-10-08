# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPEC).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "client" / "windows"))

a = Analysis(
    ['server_gui.py'],
    pathex=[str(ROOT), str(ROOT / 'backend'), str(ROOT / 'client' / 'windows')],
    hiddenimports=collect_submodules('app') + collect_submodules('nexlink_ai') + collect_submodules('nexlink_agent') + collect_submodules('PyQt6') + [
        'asyncpg', 'psutil', 'PIL', 'pyautogui', 'pyperclip', 'structlog', 'uvicorn.logging', 'uvicorn.loops.auto',
        'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets.auto', 'PyQt6.sip'
    ],
    datas=[
        ('backend/app', 'app'),
        ('deployment-compose.server.yml', '.'),
        ('backend/migrations/postgres', 'backend/migrations/postgres'),
        ('client/windows/nexlink_ui.py', 'client/windows'),
        ('client/windows/nexlink_guard', 'client/windows/nexlink_guard'),
        ('client/windows/requirements.txt', 'client/windows'),
    ],
    binaries=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='NEXLINK-Server', debug=False, strip=False, upx=True, console=False,
    uac_admin=True,
)
