# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPEC).resolve().parent.parent.parent
CLIENT = Path(SPEC).resolve().parent
CLIENT_ICON = ROOT / 'assets' / 'icons' / 'nexlink-client.ico'

a = Analysis(
    [str(CLIENT / 'nexlink_client.py')],
    pathex=[str(CLIENT), str(ROOT)],
    binaries=[],
    datas=[
        (str(CLIENT / 'nexlink_guard' / 'icon.ico'), 'nexlink_guard'),
        (str(CLIENT / 'nexlink_guard' / 'icon.png'), 'nexlink_guard'),
        (str(CLIENT_ICON), 'assets/icons'),
    ],
    hiddenimports=(
        collect_submodules('nexlink_guard')
        + collect_submodules('nexlink_agent')
        + collect_submodules('PyQt6')
        + collect_submodules('websockets')
        + collect_submodules('PIL')
        + collect_submodules('pyautogui')
        + [
            'PyQt6.sip',
            'PIL.ImageGrab',
            'pyperclip',
            'psutil',
        ]
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['rust', 'node', 'vite', 'react'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NEXLINK-Client',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    uac_admin=True,
    icon=str(CLIENT_ICON),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='NEXLINK-Client',
)
