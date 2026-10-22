"""NEXLINK Windows Server desktop control panel.

The FastAPI/Uvicorn control plane runs in a background thread while this
PyQt6 window provides the operator-facing server UI.
"""
from __future__ import annotations

import os
import sys
import threading
import traceback
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget
)

import server_launcher

APP_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
ICON = APP_ROOT / "assets" / "icons" / "nexlink-server.ico"


class ServerWorker(QObject):
    started = pyqtSignal()
    stopped = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, auto_infra: bool = True):
        super().__init__()
        self.auto_infra = auto_infra
        self.server = None

    def run(self):
        try:
            server_launcher._ensure_server_config()
            if self.auto_infra:
                server_launcher._start_infrastructure()
            elif not (
                server_launcher._port_open("127.0.0.1", 5432)
                and server_launcher._port_open("127.0.0.1", 6379)
            ):
                raise RuntimeError("PostgreSQL/Redis are not running.")

            server_launcher._configure_api_firewall()
            from app.main import app
            import uvicorn

            config = uvicorn.Config(
                app,
                host="0.0.0.0",
                port=int(os.environ.get("PORT", "8000")),
                log_level="info",
            )
            self.server = uvicorn.Server(config)
            self.started.emit()
            self.server.run()
            self.stopped.emit()
        except Exception as exc:
            self.failed.emit(f"{exc}\n\n{traceback.format_exc()}")

    def stop(self):
        if self.server is not None:
            self.server.should_exit = True


class NEXLINKServerWindow(QMainWindow):
    def __init__(self, start_server: bool = True):
        super().__init__()
        self.setWindowTitle("NEXLINK Server")
        self.resize(820, 560)
        if ICON.exists():
            self.setWindowIcon(QIcon(str(ICON)))
        self._thread: QThread | None = None
        self._worker: ServerWorker | None = None

        root = QWidget()
        layout = QVBoxLayout(root)

        title = QLabel("NEXLINK Server")
        title.setStyleSheet("font-size: 28px; font-weight: bold;")
        layout.addWidget(title)
        subtitle = QLabel("NEXLINK Control Plane • FastAPI • PostgreSQL • Redis • LAN-first")
        layout.addWidget(subtitle)

        status_box = QGroupBox("Server Status")
        form = QFormLayout(status_box)
        self.status = QLabel("Starting…")
        self.address = QLabel("http://0.0.0.0:8000")
        self.health = QLabel("http://<SERVER-IP>:8000/health")
        form.addRow("Status:", self.status)
        form.addRow("API:", self.address)
        form.addRow("Health:", self.health)
        layout.addWidget(status_box)

        controls = QHBoxLayout()
        self.start_btn = QPushButton("Start Server")
        self.stop_btn = QPushButton("Stop Server")
        self.restart_btn = QPushButton("Restart")
        self.start_btn.clicked.connect(self.start_server)
        self.stop_btn.clicked.connect(self.stop_server)
        self.restart_btn.clicked.connect(self.restart_server)
        controls.addWidget(self.start_btn)
        controls.addWidget(self.stop_btn)
        controls.addWidget(self.restart_btn)
        layout.addLayout(controls)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("NEXLINK server events appear here…")
        layout.addWidget(self.log)

        info = QLabel(
            "NEXLINK Server is the control plane: identity, device registry, signaling, relay orchestration, audit, policies, AI governance and fleet APIs.\n"
            "The Windows Client remains the operator console and embeds Network Guard; no separate Internet Guard application is used."
        )
        layout.addWidget(info)
        self.setCentralWidget(root)
        if start_server:
            self.start_server()

    def start_server(self):
        if self._thread and self._thread.isRunning():
            return
        self.status.setText("Starting…")
        self.log.append("Starting NEXLINK FastAPI server and infrastructure…")
        self._thread = QThread(self)
        self._worker = ServerWorker(auto_infra=True)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.started.connect(self._on_started)
        self._worker.stopped.connect(self._on_stopped)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()

    def _on_started(self):
        self.status.setText("RUNNING")
        self.log.append("NEXLINK API is listening on TCP 8000.")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def _on_stopped(self):
        self.status.setText("STOPPED")
        self.log.append("NEXLINK API stopped.")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def _on_failed(self, message: str):
        self.status.setText("FAILED")
        self.log.append(message)
        QMessageBox.critical(self, "NEXLINK Server", message)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def stop_server(self):
        if self._worker:
            self._worker.stop()

    def restart_server(self):
        self.stop_server()
        if self._thread:
            self._thread.quit()
            self._thread.wait(5000)
        self._thread = None
        self._worker = None
        self.start_server()

    def closeEvent(self, event):
        self.stop_server()
        if self._thread:
            self._thread.quit()
            self._thread.wait(5000)
        event.accept()


def _self_test() -> int:
    import importlib

    try:
        import server_launcher
        server_launcher._ensure_server_config()
        from app.main import app as fastapi_app
        required = {"/health", "/api/v1/remote/sessions", "/ws/control/{session_id}"}
        paths = {getattr(route, "path", "") for route in fastapi_app.routes}
        missing = sorted(required - paths)
        for module_name in ("nexlink_ai.planner", "nexlink_ai.policy", "nexlink_ai.provider", "nexlink_ai.tools"):
            importlib.import_module(module_name)
        app = QApplication.instance() or QApplication([])
        app.setApplicationName("NEXLINK Server Build Smoke Test")
        window = NEXLINKServerWindow(start_server=False)
        assert window.windowTitle() == "NEXLINK Server"
        assert not window.windowIcon().isNull()
        window.show()
        app.processEvents()
        assert window.isVisible()
        window.close()
        app.processEvents()
    except Exception as exc:
        print(f"NEXLINK Server self-test failed: {type(exc).__name__}: {exc}")
        return 1
    print("NEXLINK Server FastAPI, AI modules and Qt UI smoke test:",
          "OK" if not missing else "MISSING " + ", ".join(missing))
    return 0 if not missing else 1

def main() -> int:
    if "--self-test" in sys.argv:
        return _self_test()
    app = QApplication(sys.argv)
    app.setApplicationName("NEXLINK Server")
    window = NEXLINKServerWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
