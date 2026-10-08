"""Windows-first remote desktop primitives with safe optional dependencies."""
from __future__ import annotations
import base64
import io
import os
import platform
import subprocess
import threading
import time
from typing import Any


def capture_frame(quality: int = 60, max_width: int = 1600) -> dict[str, Any]:
    from PIL import ImageGrab
    image = ImageGrab.grab(all_screens=True)
    if image.width > max_width:
        ratio = max_width / image.width
        image = image.resize((max_width, int(image.height * ratio)))
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=max(25, min(90, int(quality))), optimize=True)
    return {"jpeg_b64": base64.b64encode(buf.getvalue()).decode("ascii"), "width": image.width, "height": image.height, "captured_at": time.time()}


def apply_input(event: dict[str, Any]) -> dict[str, Any]:
    try:
        import pyautogui
    except ImportError as exc:
        raise RuntimeError("PyAutoGUI is not installed in this agent build") from exc
    kind = event.get("kind")
    if kind == "move":
        pyautogui.moveTo(int(event["x"]), int(event["y"]), duration=0)
    elif kind == "click":
        pyautogui.click(int(event["x"]), int(event["y"]), button=event.get("button", "left"))
    elif kind == "double_click":
        pyautogui.doubleClick(int(event["x"]), int(event["y"]))
    elif kind == "key_down":
        pyautogui.keyDown(str(event["key"]))
    elif kind == "key_up":
        pyautogui.keyUp(str(event["key"]))
    elif kind == "type":
        pyautogui.write(str(event.get("text", "")), interval=0.01)
    elif kind == "scroll":
        pyautogui.scroll(int(event.get("amount", 0)))
    else:
        raise ValueError(f"Unsupported input event: {kind}")
    return {"accepted": True, "kind": kind}


def sync_clipboard(text: str) -> dict[str, Any]:
    try:
        import pyperclip
        pyperclip.copy(text)
        return {"accepted": True}
    except ImportError:
        return {"accepted": False, "error": "Clipboard dependency unavailable"}


def execute_terminal(command: str, timeout: int = 30) -> dict[str, Any]:
    if not command.strip():
        raise ValueError("Empty command")
    timeout = max(1, min(int(timeout), 120))
    if os.name == "nt":
        args = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command]
    else:
        args = ["/bin/sh", "-lc", command]
    completed = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    return {"return_code": completed.returncode, "stdout": completed.stdout[-20000:], "stderr": completed.stderr[-20000:]}


def list_processes(limit: int = 100) -> list[dict[str, Any]]:
    import psutil
    rows = []
    for proc in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent"]):
        try:
            rows.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    rows.sort(key=lambda x: float(x.get("cpu_percent") or 0), reverse=True)
    return rows[:max(1, min(limit, 500))]


def read_file(path: str, max_bytes: int = 2_000_000) -> str:
    p = os.path.abspath(path)
    if os.path.isdir(p):
        raise ValueError("Path is a directory")
    with open(p, "rb") as handle:
        data = handle.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("File exceeds the maximum readable size")
    return data.decode("utf-8", errors="replace")
