"""Authenticated NEXLINK agent service, replacing the former Rust agent."""
from __future__ import annotations
import asyncio, json, os, socket, threading, time, logging, subprocess
import httpx, websockets
from .config import AgentConfig, identity_path, app_dir
from .identity import DeviceIdentity
from .monitor import collect
from .inventory import collect_inventory
from .diagnostics import diagnostic_snapshot
from .remote import capture_frame, apply_input, sync_clipboard, execute_terminal, list_processes, read_file
from . import network_guard

log=logging.getLogger("nexlink.agent")

class AgentService:
    def __init__(self, config:AgentConfig, identity:DeviceIdentity):
        self.config=config; self.identity=identity; self.stop_event=threading.Event(); self.session_token=None
        self.ws=None
        self.remote_tasks: dict[str, asyncio.Task] = {}

    def start(self):
        t=threading.Thread(target=lambda: asyncio.run(self._run()),daemon=True,name="NEXLINK-Agent")
        t.start(); self.thread=t; return t

    def stop(self):
        self.stop_event.set()
        for task in list(self.remote_tasks.values()):
            task.cancel()
        if self.thread and self.thread.is_alive(): self.thread.join(timeout=3)

    async def _run(self):
        if network_guard.remote_blocked():
            try: network_guard.block_internet()
            except Exception: log.exception("Failed to reapply remote network block")
        while not self.stop_event.is_set():
            try: await self._connect_once()
            except Exception as exc: log.warning("Agent connection: %s",exc)
            if not self.stop_event.is_set(): await asyncio.sleep(3)

    async def _connect_once(self):
        url=self.config.ws_url
        if not url: return
        async with websockets.connect(url,ping_interval=None,max_size=16*1024*1024) as ws:
            self.ws=ws
            ts=int(time.time())
            signed=f"{self.identity.device_id}:{self.identity.public_key_hex}:{ts}".encode()
            await ws.send(json.dumps({"type":"hello","device_id":self.identity.device_id,"public_key":self.identity.public_key_hex,
                                      "version":self.config.agent_version,"timestamp":ts,"signature":self.identity.sign(signed).hex()}))
            msg=json.loads(await asyncio.wait_for(ws.recv(),30))
            if msg.get("type")!="auth_challenge": raise RuntimeError(msg.get("reason","Authentication challenge rejected"))
            sig=self.identity.sign(msg["challenge"].encode()).hex()
            await ws.send(json.dumps({"type":"auth_proof","challenge_id":msg["challenge_id"],"signature":sig,"timestamp":int(time.time())}))
            msg=json.loads(await asyncio.wait_for(ws.recv(),30))
            if msg.get("type")!="auth_accepted": raise RuntimeError(msg.get("reason","Authentication rejected"))
            self.session_token=msg.get("session_token")
            await self._authenticated_loop(ws)

    async def _authenticated_loop(self,ws):
        last_metrics=0
        last_inventory=0
        while not self.stop_event.is_set():
            try:
                raw=await asyncio.wait_for(ws.recv(),timeout=30)
                msg=json.loads(raw)
                typ=msg.get("type")
                if typ=="ping": await ws.send(json.dumps({"type":"pong","timestamp":int(time.time())}))
                elif typ=="action_request": await self._action(ws,msg)
            except asyncio.TimeoutError:
                await ws.send(json.dumps({"type":"ping","timestamp":int(time.time())}))
            if time.time()-last_metrics>=15:
                payload=collect(); await ws.send(json.dumps({"type":"metrics_report","payload":payload})); last_metrics=time.time()
            if time.time()-last_inventory>=60:
                try: await ws.send(json.dumps({"type":"inventory_report","payload":collect_inventory()}))
                except Exception: pass
                last_inventory=time.time()

    async def _action(self,ws,msg):
        action=msg.get("action",""); params=msg.get("params") or {}; ok=True; result={}
        try:
            if action=="network.block_all":
                network_guard.set_remote_block(True); network_guard.block_internet(); result={"blocked":True}
            elif action=="network.unblock_all":
                network_guard.set_remote_block(False); network_guard.unblock_internet(); result={"blocked":False}
            elif action=="network.block_domains":
                network_guard.update_blocked_domains(params.get("domains",[])); result={"domains":params.get("domains",[])}
            elif action=="network.status":
                result={"blocked":network_guard.is_blocked(),"remote_block":network_guard.remote_blocked()}
            elif action=="remote.start":
                session_id=str(params.get("session_id", ""))
                if not session_id: raise ValueError("Missing remote session id")
                if session_id not in self.remote_tasks or self.remote_tasks[session_id].done():
                    self.remote_tasks[session_id]=asyncio.create_task(self._stream_remote(ws, session_id, params))
                result={"session_id":session_id,"started":True}
            elif action=="remote.stop":
                session_id=str(params.get("session_id", ""))
                task=self.remote_tasks.pop(session_id, None)
                if task: task.cancel()
                result={"session_id":session_id,"stopped":True}
            elif action=="remote.input":
                result=await asyncio.to_thread(apply_input, params)
            elif action=="remote.clipboard":
                result=await asyncio.to_thread(sync_clipboard, str(params.get("text", "")))
            elif action=="remote.file.download":
                path=os.path.abspath(str(params.get("path", "")))
                if not os.path.isfile(path): raise FileNotFoundError(path)
                size=os.path.getsize(path)
                if size > 50*1024*1024: raise ValueError("File exceeds 50 MB remote transfer limit")
                import base64
                with open(path, "rb") as handle: data=base64.b64encode(handle.read()).decode("ascii")
                await ws.send(json.dumps({"type":"file_transfer_data","payload":{"session_id":params.get("session_id"),"direction":"download","path":path,"size":size,"data_b64":data}}))
                result={"path":path,"size":size}
            elif action=="remote.file.upload":
                if not params.get("_authorized"): raise PermissionError("File upload requires explicit authorization")
                import base64
                data=base64.b64decode(str(params.get("data_b64", "")))
                if len(data)>50*1024*1024: raise ValueError("File exceeds 50 MB remote transfer limit")
                path=os.path.abspath(str(params.get("path", "")))
                with open(path, "wb") as handle: handle.write(data)
                result={"path":path,"size":len(data)}
            elif action=="ai.get_system_info":
                result=await asyncio.to_thread(lambda: diagnostic_snapshot()["system"])
            elif action=="ai.get_cpu_usage":
                result={"cpu_percent":collect().get("cpu_percent")}
            elif action=="ai.get_memory_usage":
                result={"memory_percent":collect().get("memory_percent")}
            elif action=="ai.get_disk_usage":
                result={"disk_percent":collect().get("disk_percent")}
            elif action=="ai.list_processes":
                result={"processes":await asyncio.to_thread(list_processes, 100)}
            elif action=="ai.get_network_status":
                result={"blocked":network_guard.is_blocked(),"remote_block":network_guard.remote_blocked()}
            elif action=="ai.restart_device":
                if not params.get("_authorized"): raise PermissionError("Device restart requires explicit authorization")
                subprocess.run(["shutdown", "/r", "/t", "5"] if os.name == "nt" else ["shutdown", "-r", "now"], check=False); result={"requested":"restart"}
            elif action=="ai.restart_service":
                if not params.get("_authorized"): raise PermissionError("Service restart requires explicit authorization")
                service=str(params.get("service", "")).strip()
                if not service: raise ValueError("Service name required")
                if os.name == "nt": subprocess.run(["sc.exe", "stop", service], check=False); subprocess.run(["sc.exe", "start", service], check=False)
                else: subprocess.run(["systemctl", "restart", service], check=False)
                result={"service":service,"restarted":True}
            elif action=="ai.install_software":
                if not params.get("_authorized"): raise PermissionError("Software installation requires explicit authorization")
                installer=str(params.get("installer", "")); args=params.get("args") or []
                if not os.path.isfile(installer): raise FileNotFoundError(installer)
                completed=subprocess.run([installer]+[str(x) for x in args],capture_output=True,text=True,timeout=min(int(params.get("timeout",300)),900),check=False)
                result={"return_code":completed.returncode,"stdout":completed.stdout[-10000:],"stderr":completed.stderr[-10000:]}
            elif action=="ai.read_file":
                if not params.get("_authorized"): raise PermissionError("File read requires explicit authorization")
                result={"content":await asyncio.to_thread(read_file, str(params.get("path", "")))}
            elif action=="ai.execute_command":
                if not params.get("_authorized"): raise PermissionError("Command execution requires explicit authorization")
                result=await asyncio.to_thread(execute_terminal, str(params.get("command", "")), int(params.get("timeout",30)))
            elif action in {"device.restart", "device.shutdown", "device.lock"}:
                if not params.get("_authorized"): raise PermissionError("System control requires explicit authorization")
                if action == "device.lock":
                    if os.name == "nt": subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=False)
                    else: subprocess.run(["loginctl", "lock-session"], check=False)
                elif action == "device.restart":
                    subprocess.run(["shutdown", "/r", "/t", "5"] if os.name == "nt" else ["shutdown", "-r", "now"], check=False)
                else:
                    subprocess.run(["shutdown", "/s", "/t", "5"] if os.name == "nt" else ["shutdown", "-h", "now"], check=False)
                result={"requested":action}
            elif action=="process.terminate":
                if not params.get("_authorized"): raise PermissionError("Process termination requires explicit authorization")
                import psutil
                proc=psutil.Process(int(params["pid"])); proc.terminate(); result={"terminated":int(params["pid"])}
            elif action=="service.restart":
                if not params.get("_authorized"): raise PermissionError("Service management requires explicit authorization")
                service=str(params.get("service", "")).strip()
                if not service or any(ch in service for ch in "&|;`\"'"): raise ValueError("Invalid service name")
                if os.name == "nt": subprocess.run(["sc.exe", "stop", service], check=False); subprocess.run(["sc.exe", "start", service], check=False)
                else: subprocess.run(["systemctl", "restart", service], check=False)
                result={"service":service,"restarted":True}
            elif action=="software.install":
                if not params.get("_authorized"): raise PermissionError("Software installation requires explicit authorization")
                installer=str(params.get("installer", "")); args=params.get("args") or []
                if not os.path.isfile(installer): raise FileNotFoundError(installer)
                command=[installer]+[str(x) for x in args]
                completed=subprocess.run(command,capture_output=True,text=True,timeout=min(int(params.get("timeout",300)),900),check=False)
                result={"return_code":completed.returncode,"stdout":completed.stdout[-10000:],"stderr":completed.stderr[-10000:]}
            else:
                raise ValueError(f"Unsupported action: {action}")
        except Exception as exc:
            ok=False; result={"error":str(exc)}
        await ws.send(json.dumps({"type":"action_result","request_id":msg.get("request_id"),"action":action,"success":ok,"result":result,"payload":{"session_id":params.get("session_id")}}))

    async def _stream_remote(self, ws, session_id: str, params: dict):
        quality=60
        interval=0.12
        try:
            await ws.send(json.dumps({"type":"screen_info","payload":{"session_id":session_id,"platform":os.name,"multi_monitor":True}}))
            while not self.stop_event.is_set():
                frame=await asyncio.to_thread(capture_frame, quality, 1600)
                frame["session_id"]=session_id
                await ws.send(json.dumps({"type":"screen_frame","payload":frame}))
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await ws.send(json.dumps({"type":"screen_frame","payload":{"session_id":session_id,"error":str(exc)}}))
