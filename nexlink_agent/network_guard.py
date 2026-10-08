"""Windows Network Guard enforcement used by the unified NEXLINK client."""
from __future__ import annotations
import ctypes, json, os, subprocess
from pathlib import Path

RULE="NEXLINK-InternetGuard"
HOSTS=Path(r"C:\Windows\System32\drivers\etc\hosts")
START="# NEXLINK-Blocked-Start"; END="# NEXLINK-Blocked-End"
STATE=Path(os.environ.get("LOCALAPPDATA",str(Path.home())))/"NEXLINK"/"network_policy.json"

def is_admin():
    if os.name!="nt": return os.geteuid()==0 if hasattr(os,"geteuid") else False
    try: return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception: return False

def _ps(command):
    return subprocess.run(["powershell.exe","-NoProfile","-NonInteractive","-ExecutionPolicy","Bypass","-Command",command],capture_output=True,text=True)

def remote_blocked():
    try: return bool(json.loads(STATE.read_text())["remote_block"])
    except Exception: return False

def set_remote_block(value:bool):
    STATE.parent.mkdir(parents=True,exist_ok=True); STATE.write_text(json.dumps({"remote_block":value}),encoding="utf-8")

def block_internet():
    if os.name!="nt": raise RuntimeError("Network Guard firewall enforcement requires Windows")
    r=_ps(f"Remove-NetFirewallRule -DisplayName '{RULE}' -ErrorAction SilentlyContinue; New-NetFirewallRule -DisplayName '{RULE}' -Direction Outbound -Action Block -RemoteAddress Internet -Profile Any | Out-Null")
    if r.returncode: raise RuntimeError(r.stderr.strip() or "Unable to create firewall rule")

def unblock_internet():
    if remote_blocked(): raise RuntimeError("NEXLINK server has enforced an internet block on this device.")
    r=_ps(f"Remove-NetFirewallRule -DisplayName '{RULE}' -ErrorAction SilentlyContinue")
    if r.returncode: raise RuntimeError(r.stderr.strip() or "Unable to remove firewall rule")

def is_blocked():
    if os.name!="nt": return False
    r=_ps(f"@(Get-NetFirewallRule -DisplayName '{RULE}' -ErrorAction SilentlyContinue | Where-Object Enabled -eq 'True').Count")
    try: return int(r.stdout.strip() or "0")>0
    except ValueError: return False

def update_blocked_domains(domains:list[str]):
    if os.name!="nt": raise RuntimeError("Domain blocking is a Windows feature")
    lines=HOSTS.read_text(encoding="utf-8").splitlines(True) if HOSTS.exists() else []
    out=[]; inside=False
    for line in lines:
        if START in line: inside=True; continue
        if END in line: inside=False; continue
        if not inside: out.append(line)
    clean=[]
    for d in domains:
        d=d.strip().lower().replace("https://","").replace("http://","").split("/")[0]
        if d.startswith("www."): d=d[4:]
        if d and d not in clean: clean.append(d)
    if clean:
        out += [f"\n{START}\n"] + [x for d in clean for x in (f"127.0.0.1 {d}\n",f"127.0.0.1 www.{d}\n",f"::1 {d}\n",f"::1 www.{d}\n")] + [f"{END}\n"]
    HOSTS.write_text("".join(out),encoding="utf-8")
    subprocess.run(["ipconfig","/flushdns"],capture_output=True)
