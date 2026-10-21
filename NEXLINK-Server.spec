# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPEC).resolve().parent
SERVER_ICON = ROOT / "assets" / "icons" / "nexlink-server.ico"

a = Analysis(
    [str(ROOT / 'server_gui.py')],
    pathex=[str(ROOT), str(ROOT / 'backend')],
    hiddenimports=(
        collect_submodules('app')
        + collect_submodules('nexlink_ai')
        + collect_submodules('PyQt6')
        + collect_submodules('uvicorn')
        + collect_submodules('websockets')
        + collect_submodules('asyncpg')
        + collect_submodules('redis')
        + [
            'PyQt6.sip',
            'uvicorn.logging',
            'uvicorn.loops.auto',
            'uvicorn.protocols.http.auto',
            'uvicorn.protocols.websockets.auto',
            'sqlalchemy.dialects.postgresql.asyncpg',
        ]
    ),
    datas=[
        (str(ROOT / 'deployment-compose.server.yml'), '.'),
        (str(ROOT / 'backend' / 'migrations' / 'postgres'), 'backend/migrations/postgres'),
        (str(SERVER_ICON), 'assets/icons'),
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
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NEXLINK-Server',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    uac_admin=True,
    icon=str(SERVER_ICON),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='NEXLINK-Server',
)
