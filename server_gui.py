"""NEXLINK Windows Server desktop control panel.

The FastAPI/Uvicorn control plane runs in a background thread while this
PyQt6 window provides the operator-facing server UI.
"""
from __future__ import annotations

import os
import sys
import threading
import time
import traceback
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget
)

import server_launcher
from nexlink_discovery import DiscoveryResponder, get_discovered_clients

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
        self.discovery: DiscoveryResponder | None = None

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

            api_port = int(os.environ.get("PORT", "8000"))
            self.discovery = DiscoveryResponder(api_port=api_port).start()
            config = uvicorn.Config(
                app,
                host="0.0.0.0",
                port=api_port,
                log_level="info",
            )
            self.server = uvicorn.Server(config)
            self.started.emit()
            try:
                self.server.run()
            finally:
                if self.discovery is not None:
                    self.discovery.stop()
                    self.discovery = None
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
        self.resize(900, 720)
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

        clients_box = QGroupBox("Clients detected on this LAN")
        clients_layout = QVBoxLayout(clients_box)
        self.discovery_status = QLabel(
            "Waiting for client announcements. Detection does not enroll or approve a device."
        )
        clients_layout.addWidget(self.discovery_status)
        self.clients_table = QTableWidget(0, 4)
        self.clients_table.setHorizontalHeaderLabels(["Device", "LAN address", "Operating system", "Last seen"])
        self.clients_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.clients_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.clients_table.horizontalHeader().setStretchLastSection(True)
        clients_layout.addWidget(self.clients_table)
        layout.addWidget(clients_box)

        info = QLabel(
            "NEXLINK Server is the control plane: identity, device registry, signaling, relay orchestration, audit, policies, AI governance and fleet APIs.\n"
            "The Windows Client remains the operator console and embeds Network Guard; no separate Internet Guard application is used."
        )
        layout.addWidget(info)
        self.setCentralWidget(root)
        self.discovery_timer = QTimer(self)
        self.discovery_timer.setInterval(2000)
        self.discovery_timer.timeout.connect(self.refresh_discovered_clients)
        self.discovery_timer.start()
        self.refresh_discovered_clients()
        if start_server:
            self.start_server()

    def refresh_discovered_clients(self):
        clients = get_discovered_clients()
        self.clients_table.setRowCount(len(clients))
        now = int(time.time())
        for row, client in enumerate(clients):
            seen_at = int(client.get("last_seen") or client.get("timestamp") or now)
            age = max(0, now - seen_at)
            values = (
                client.get("device_name") or client.get("hostname") or "Unknown device",
                client.get("ip") or "Unknown",
                client.get("os") or "Unknown",
                "just now" if age < 2 else f"{age}s ago",
            )
            for column, value in enumerate(values):
                self.clients_table.setItem(row, column, QTableWidgetItem(str(value)))
        if clients:
            self.discovery_status.setText(
                f"{len(clients)} client(s) seen in the last 20 seconds. Enrollment and approval are still required."
            )
        else:
            self.discovery_status.setText(
                "No clients seen in the last 20 seconds. Check that both apps are on the same LAN and UDP 39501 is allowed."
            )

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
        self.discovery_timer.stop()
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
        assert window.clients_table.columnCount() == 4
        assert window.discovery_timer.isActive()
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
