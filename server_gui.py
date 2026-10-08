"""NEXLINK Server native desktop console.

The server executable is the primary NEXLINK operator console. It owns the
FastAPI control plane in a background thread and exposes a polished PyQt6
Command Center for fleet management, remote access, Network Guard, AI,
security, automation and support.
"""
from __future__ import annotations

import os
import sys
import threading
import traceback
from pathlib import Path

CLIENT_UI = Path(__file__).resolve().parent / "client" / "windows"
if CLIENT_UI.exists() and str(CLIENT_UI) not in sys.path:
    sys.path.insert(0, str(CLIENT_UI))

from PyQt6.QtCore import QThread, Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPushButton, QStackedWidget,
    QVBoxLayout, QWidget, QProgressBar
)

import server_launcher


class ServerWorker:
    def __init__(self, owner):
        self.owner = owner
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.server = None
        self.discovery = None
        self.error = None

    def start(self):
        self.thread.start()

    def run(self):
        try:
            server_launcher._ensure_server_config()
            server_launcher._start_infrastructure()
            server_launcher._configure_api_firewall()
            from app.main import app
            import uvicorn
            config = uvicorn.Config(
                app,
                host="0.0.0.0",
                port=int(os.environ.get("PORT", "8000")),
                log_level="warning",
            )
            self.server = uvicorn.Server(config)
            from nexlink_discovery import DiscoveryResponder
            self.discovery = DiscoveryResponder(api_port=int(os.environ.get("PORT", "8000"))).start()
            self.owner.server_started.emit()
            self.server.run()
            if self.discovery:
                self.discovery.stop()
            self.owner.server_stopped.emit()
        except Exception as exc:
            self.error = f"{exc}\n\n{traceback.format_exc()}"
            self.owner.server_failed.emit(self.error)

    def stop(self):
        if self.server:
            self.server.should_exit = True
        if self.discovery:
            self.discovery.stop()


class LoginCard(QFrame):
    authenticated = pyqtSignal(object)

    def __init__(self, base_url: str, parent=None):
        super().__init__(parent)
        self.base_url = base_url
        self.setObjectName("Card")
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        title = QLabel("Operator sign in")
        title.setObjectName("CardTitle")
        root.addWidget(title)
        sub = QLabel("Sign in to manage your NEXLINK fleet.")
        sub.setObjectName("Muted")
        root.addWidget(sub)
        form = QFormLayout()
        self.email = QLineEdit()
        self.email.setPlaceholderText("admin@example.com")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Password")
        self.mfa = QLineEdit()
        self.mfa.setPlaceholderText("6-digit MFA code, if enabled")
        form.addRow("Email", self.email)
        form.addRow("Password", self.password)
        form.addRow("MFA", self.mfa)
        root.addLayout(form)
        buttons = QHBoxLayout()
        self.button = QPushButton("Sign in")
        self.button.setObjectName("Primary")
        self.button.clicked.connect(self.login)
        buttons.addWidget(self.button)
        register = QPushButton("Create first account")
        register.clicked.connect(self.register)
        buttons.addWidget(register)
        root.addLayout(buttons)
        self.status = QLabel("Server is ready. On a new installation, create the first owner account here.")
        self.status.setObjectName("Muted")
        root.addWidget(self.status)

    def login(self):
        try:
            from nexlink_ui import ApiClient
            api = ApiClient(self.base_url)
            data = api.login(self.email.text().strip(), self.password.text(), self.mfa.text().strip() or None)
            self.authenticated.emit((api, data))
        except Exception as exc:
            self.status.setText(str(exc))
            QMessageBox.warning(self, "NEXLINK Sign In", str(exc))

    def register(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Create NEXLINK Owner")
        dialog.resize(430, 240)
        form = QFormLayout(dialog)
        name = QLineEdit(); email = QLineEdit(); password = QLineEdit()
        password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Name", name); form.addRow("Email", email); form.addRow("Password", password)
        create = QPushButton("Create Owner Account")
        form.addRow(create)
        def create_account():
            try:
                from nexlink_ui import ApiClient
                api = ApiClient(self.base_url)
                response = api.request("POST", "/api/v1/auth/register", json={
                    "name": name.text().strip(), "email": email.text().strip(), "password": password.text(),
                })
                response.raise_for_status()
                data = response.json()
                self.authenticated.emit((api, data))
                dialog.accept()
            except Exception as exc:
                QMessageBox.warning(dialog, "NEXLINK Registration", str(exc))
        create.clicked.connect(create_account)
        dialog.exec()


class NEXLINKServerWindow(QMainWindow):
    server_started = pyqtSignal()
    server_stopped = pyqtSignal()
    server_failed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.worker = None
        self.api = None
        self.setWindowTitle("NEXLINK — Server Command Center")
        self.resize(1440, 900)
        self.setMinimumSize(1180, 760)
        self._build_shell()
        self._apply_theme()
        self.server_started.connect(self._on_server_started)
        self.server_stopped.connect(self._on_server_stopped)
        self.server_failed.connect(self._on_server_failed)
        self._start_server()

    def _build_shell(self):
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(235)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 22, 18, 18)
        brand = QLabel("NEXLINK")
        brand.setObjectName("Brand")
        side.addWidget(brand)
        sub = QLabel("SERVER COMMAND CENTER")
        sub.setObjectName("BrandSub")
        side.addWidget(sub)
        side.addSpacing(28)
        self.nav = []
        for label, index in [("Overview", 0), ("Fleet & Remote", 1), ("Network Guard", 2), ("NEXLINK AI", 3), ("Security Center", 4), ("Automation", 5), ("Support Center", 6)]:
            b = QPushButton(label)
            b.setCheckable(True)
            b.clicked.connect(lambda checked, i=index: self._select(i))
            side.addWidget(b)
            self.nav.append(b)
        side.addStretch()
        self.server_badge = QLabel("●  STARTING")
        self.server_badge.setObjectName("StatusBadge")
        side.addWidget(self.server_badge)
        self.api_label = QLabel("API  :8000")
        self.discovery_label = QLabel("LAN clients: 0 discovered")
        self.discovery_label.setObjectName("Muted")
        self.api_label.setObjectName("Muted")
        side.addWidget(self.api_label)
        side.addWidget(self.discovery_label)
        root.addWidget(side)

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        header = QFrame()
        header.setObjectName("Header")
        h = QHBoxLayout(header)
        h.setContentsMargins(26, 16, 26, 16)
        self.page_title = QLabel("Overview")
        self.page_title.setObjectName("PageTitle")
        h.addWidget(self.page_title)
        h.addStretch()
        self.health = QLabel("Infrastructure: checking…")
        self.health.setObjectName("Muted")
        h.addWidget(self.health)
        body.addWidget(header)

        self.stack = QStackedWidget()
        body.addWidget(self.stack)
        root.addLayout(body, 1)
        self.setCentralWidget(central)

        self._show_login_or_dashboard()
        self.discovery_timer = QTimer(self)
        self.discovery_timer.timeout.connect(self._refresh_discovery)
        self.discovery_timer.start(2000)


    def _refresh_discovery(self):
        try:
            from nexlink_discovery import get_discovered_clients
            clients = get_discovered_clients()
            self.discovery_label.setText(f"LAN clients: {len(clients)} discovered")
        except Exception:
            pass

    def _show_login_or_dashboard(self):
        self.login_page = QWidget()
        lay = QVBoxLayout(self.login_page)
        lay.setContentsMargins(55, 55, 55, 55)
        hero = QLabel("Your IT operating system.")
        hero.setObjectName("Hero")
        lay.addWidget(hero)
        text = QLabel("Remote access  •  Fleet intelligence  •  Network Guard  •  AI automation  •  Zero-trust security")
        text.setObjectName("Muted")
        lay.addWidget(text)
        lay.addSpacing(25)
        self.login_card = LoginCard("http://127.0.0.1:8000", self)
        self.login_card.authenticated.connect(self._authenticated)
        self.login_card.setMaximumWidth(620)
        lay.addWidget(self.login_card, alignment=Qt.AlignmentFlag.AlignLeft)
        lay.addStretch()
        self.stack.addWidget(self.login_page)
        self._select(0)

    def _authenticated(self, payload):
        self.api, user_data = payload
        self._build_platform_pages()
        self.server_badge.setText("●  ONLINE")
        self.server_badge.setObjectName("StatusBadgeOnline")
        self.page_title.setText("Overview")
        self.nav[0].setChecked(True)
        self.stack.setCurrentIndex(1)
        self.health.setText(f"Operator: {user_data['user']['name']}  •  role={user_data['user']['role']}")

    def _build_platform_pages(self):
        from nexlink_ui import DashboardTab, DevicesTab, AlertsTab, NetworkTab, AITab, SecurityTab, AutomationTab, SupportTab
        pages = [
            DashboardTab(self.api),
            DevicesTab(self.api),
            NetworkTab(self.api),
            AITab(self.api),
            SecurityTab(self.api),
            AutomationTab(self.api),
            SupportTab(self.api),
        ]
        for p in pages:
            self.stack.addWidget(p)

    def _select(self, index):
        if index >= len(self.nav):
            return
        for i, b in enumerate(self.nav):
            b.setChecked(i == index)
        self.page_title.setText(self.nav[index].text())
        if self.api:
            self.stack.setCurrentIndex(index + 1)
        else:
            self.stack.setCurrentIndex(0)

    def _start_server(self):
        self.server_badge.setText("●  STARTING")
        self.health.setText("Starting PostgreSQL/API…")
        self.worker = ServerWorker(self)
        self.worker.start()

    def _on_server_started(self):
        self.server_badge.setText("●  SERVER ONLINE")
        self.health.setText("API listening on 8000  •  LAN control plane ready")

    def _on_server_stopped(self):
        self.server_badge.setText("●  STOPPED")
        self.health.setText("NEXLINK API stopped")

    def _on_server_failed(self, message):
        self.server_badge.setText("●  SETUP REQUIRED")
        self.health.setText("PostgreSQL / infrastructure setup required")
        QMessageBox.critical(self, "NEXLINK Server Setup", message)

    def closeEvent(self, event):
        if self.worker:
            self.worker.stop()
        event.accept()

    def _apply_theme(self):
        self.setStyleSheet("""
        QMainWindow, QWidget { background: #0b1220; color: #e8eef8; font-family: 'Segoe UI'; font-size: 13px; }
        #Sidebar { background: #07101d; border-right: 1px solid #1d2a3d; }
        #Brand { font-size: 28px; font-weight: 800; letter-spacing: 2px; }
        #BrandSub { color: #71809a; font-size: 10px; letter-spacing: 1.5px; }
        QPushButton { background: #111c2d; border: 1px solid #1e2e44; border-radius: 8px; padding: 11px 13px; text-align: left; color: #b9c6d8; }
        QPushButton:hover { background: #17263a; color: #fff; }
        QPushButton:checked { background: #173b66; border-color: #2f79c7; color: #fff; }
        #Header { background: #0d1727; border-bottom: 1px solid #1d2a3d; }
        #PageTitle { font-size: 22px; font-weight: 700; }
        #Hero { font-size: 36px; font-weight: 800; }
        #Muted { color: #8190a7; }
        #StatusBadge, #StatusBadgeOnline { padding: 8px 10px; border-radius: 8px; color: #f4b942; background: #2b2412; }
        #StatusBadgeOnline { color: #58d68d; background: #10291d; }
        #Card { background: #101b2c; border: 1px solid #203149; border-radius: 14px; }
        #CardTitle { font-size: 18px; font-weight: 700; }
        #Primary { background: #246fba; border-color: #2d84d1; text-align: center; color: white; font-weight: 700; }
        QLineEdit, QComboBox, QTextEdit, QTableWidget { background: #0d1727; border: 1px solid #24354d; border-radius: 7px; padding: 7px; color: #e8eef8; }
        QGroupBox { border: 1px solid #203149; border-radius: 10px; margin-top: 12px; padding: 12px; font-weight: 700; }
        QTableWidget { gridline-color: #1c2b40; }
        QHeaderView::section { background: #111e31; color: #aebbd0; padding: 7px; border: 0; }
        """)


def _self_test() -> int:
    from app.main import app
    required = {"/health", "/api/v1/remote/sessions"}
    paths = {getattr(route, "path", "") for route in app.routes}
    missing = sorted(required - paths)
    print("NEXLINK Server GUI self-test:", "OK" if not missing else "MISSING " + ", ".join(missing))
    return 0 if not missing else 1


def main() -> int:
    if "--self-test" in sys.argv:
        return _self_test()
    app = QApplication(sys.argv)
    app.setApplicationName("NEXLINK Server")
    app.setApplicationDisplayName("NEXLINK Server")
    window = NEXLINKServerWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
