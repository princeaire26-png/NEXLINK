# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPEC).resolve().parent.parent.parent
CLIENT = Path(SPEC).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(CLIENT))

agent_datas, agent_binaries, agent_hidden = collect_all('nexlink_agent')
guard_datas, guard_binaries, guard_hidden = collect_all('nexlink_guard')
ai_datas, ai_binaries, ai_hidden = collect_all('nexlink_ai')

hidden = sorted(set(
    collect_submodules('nexlink_agent')
    + collect_submodules('nexlink_guard')
    + collect_submodules('nexlink_ai')
    + agent_hidden + guard_hidden + ai_hidden
    + [
        'nexlink_agent.service', 'nexlink_agent.main', 'nexlink_agent.remote',
        'nexlink_agent.network_guard', 'nexlink_agent.inventory',
        'nexlink_agent.monitor', 'nexlink_agent.diagnostics', 'nexlink_agent.identity',
        'PyQt6.sip', 'websockets', 'httpx', 'PIL', 'pyautogui', 'pyperclip',
        'nexlink_discovery',
    ]
))

a = Analysis(
    [str(CLIENT / 'nexlink_client.py')],
    pathex=[str(CLIENT), str(ROOT)],
    binaries=agent_binaries + guard_binaries + ai_binaries,
    datas=agent_datas + guard_datas + ai_datas + [
        (str(CLIENT / 'nexlink_guard' / 'icon.ico'), 'nexlink_guard'),
        (str(CLIENT / 'nexlink_guard' / 'icon.png'), 'nexlink_guard'),
        (str(CLIENT / 'nexlink_ui.py'), '.'),
    ],
    hiddenimports=hidden,
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=['rust','node','vite','react'], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='NEXLINK-Client', debug=False, strip=False, upx=True,
    console=False, uac_admin=True,
)
