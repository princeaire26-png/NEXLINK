"""Command line entry point for the bundled Python NEXLINK agent."""
from __future__ import annotations
import argparse, os, platform, sys, time, logging, httpx
from .config import AgentConfig, identity_path, app_dir
from .identity import DeviceIdentity
from .service import AgentService

def server_http(url:str)->str:
    return url.replace("wss://","https://").replace("ws://","http://").removesuffix("/ws")

def enroll(config,identity,token):
    ts=int(time.time()); payload={"enrollment_token":token,"device_id":identity.device_id,"public_key":identity.public_key_hex,
      "signature":identity.sign(f"{identity.device_id}:{ts}".encode()).hex(),"os_type":"windows" if platform.system()=="Windows" else platform.system().lower(),
      "os_version":platform.version(),"agent_version":config.agent_version,"timestamp":ts}
    r=httpx.post(server_http(config.server_url)+"/api/v1/enrollment/enroll",json=payload,timeout=20)
    r.raise_for_status(); config.enrolled=True; config.save(); return r.json()

def main():
    ap=argparse.ArgumentParser(prog="NEXLINK")
    ap.add_argument("--enroll"); ap.add_argument("--status",action="store_true"); ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args(); config=AgentConfig.load()
    if a.self_test:
        print("NEXLINK Python client/agent OK"); return 0
    if not config.server_url:
        print("Configure NEXLINK_SERVER_URL or launch the desktop client first."); return 2
    identity=DeviceIdentity.load_or_create(identity_path(),config.identity_passphrase or os.environ.get("NEXLINK_IDENTITY_PASSPHRASE","nexlink-local"))
    if a.enroll:
        print(enroll(config,identity,a.enroll)); return 0
    svc=AgentService(config,identity); svc.start()
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt: svc.stop()
    return 0
if __name__=="__main__": raise SystemExit(main())
