"""NEXLINK Windows endpoint application: remote access, RMM, Network Guard and AI."""
from __future__ import annotations

import os
import platform
import sys
import time
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QTabWidget, QTextEdit, QVBoxLayout, QWidget, QComboBox,
)

from nexlink_agent.config import AgentConfig, identity_path
from nexlink_discovery import discover_servers, ClientAnnouncer
from nexlink_agent.identity import DeviceIdentity
from nexlink_agent import network_guard
from nexlink_guard.common import db
from nexlink_guard.common.admin_panel import open_admin_panel
from nexlink_guard.common.session_manager import SessionManager
from nexlink_ui import (
    AITab, AlertsTab, ApiClient, AutomationTab, DashboardTab, DevicesTab,
    NetworkTab, SecurityTab, SupportTab,
)

ICON = Path(__file__).parent / "nexlink_guard" / "icon.ico"


class DiscoveryWorker(QThread):
    found = pyqtSignal(object)
    failed = pyqtSignal(str)

    def run(self):
        try:
            self.found.emit(discover_servers(timeout=2.5))
        except Exception as exc:
            self.failed.emit(str(exc))


class SetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connect NEXLINK to your LAN")
        self.resize(650, 390)
        self.worker = None
        form = QFormLayout(self)
        self.server = QLineEdit()
        self.server.setPlaceholderText("Automatically discovered, or 192.168.1.20:8000")
        self.servers = QComboBox()
        self.servers.setPlaceholderText("Searching for NEXLINK servers…")
        self.servers.currentIndexChanged.connect(self._select_server)
        self.discover = QPushButton("Discover on LAN")
        self.discover.clicked.connect(self.start_discovery)
        self.token = QLineEdit()
        self.token.setPlaceholderText("Enrollment token (optional)")
        self.name = QLineEdit(platform.node())
        self.passphrase = QLineEdit("nexlink-local")
        self.passphrase.setEchoMode(QLineEdit.EchoMode.Password)
        self.status = QLabel("Looking for NEXLINK Server on this LAN…")
        self.status.setWordWrap(True)
        form.addRow("NEXLINK Server:", self.server)
        row = QHBoxLayout(); row.addWidget(self.servers, 1); row.addWidget(self.discover); form.addRow("LAN Servers:", row)
        form.addRow("Enrollment token:", self.token)
        form.addRow("Device name:", self.name)
        form.addRow("Identity passphrase:", self.passphrase)
        form.addRow(self.status)
        button = QPushButton("Save / Enroll")
        button.clicked.connect(self.accept_setup)
        form.addRow(button)
        self.start_discovery()

    def start_discovery(self):
        if self.worker and self.worker.isRunning():
            return
        self.servers.clear()
        self.servers.setPlaceholderText("Searching…")
        self.status.setText("Broadcasting a LAN discovery request. NEXLINK never scans the Internet for servers.")
        self.worker = DiscoveryWorker()
        self.worker.found.connect(self.discovery_finished)
        self.worker.failed.connect(lambda error: self.status.setText(f"LAN discovery failed: {error}"))
        self.worker.start()

    def discovery_finished(self, servers):
        self.servers.clear()
        for item in servers:
            label = f"{item.get('hostname', 'NEXLINK Server')} — {item.get('ip')}:{item.get('port', 8000)}"
            self.servers.addItem(label, item.get('url'))
        if servers:
            self.servers.setCurrentIndex(0)
            self.status.setText(f"Found {len(servers)} NEXLINK Server(s) on the LAN. The first one is selected.")
        else:
            self.status.setText("No NEXLINK Server was found. Make sure the Server is running and Windows Firewall allows NEXLINK LAN Discovery (UDP 39501). You can also enter its address manually.")

    def _select_server(self, index):
        if index >= 0:
            value = self.servers.itemData(index)
            if value:
                self.server.setText(value)

    def accept_setup(self):
        if not self.server.text().strip():
            QMessageBox.warning(self, "NEXLINK", "No NEXLINK Server was found. Start NEXLINK Server on the LAN, click Discover on LAN, or enter its address manually.")
            return
        cfg = AgentConfig(
            server_url=self.server.text().strip(),
            device_name=self.name.text().strip() or platform.node(),
            identity_passphrase=self.passphrase.text() or "nexlink-local",
            agent_version="2.1.0",
        )
        cfg.save()
        ident = DeviceIdentity.load_or_create(identity_path(), cfg.identity_passphrase)
        if self.token.text().strip():
            try:
                from nexlink_agent.main import enroll
                result = enroll(cfg, ident, self.token.text().strip())
                QMessageBox.information(self, "Enrollment", result.get("message", "Enrollment submitted."))
            except Exception as exc:
                QMessageBox.critical(self, "Enrollment failed", str(exc))
                return
        self.accept()


class LocalGuardTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        db.init_db()
        root = QVBoxLayout(self)
        self.state = QLabel()
        root.addWidget(self.state)
        row = QHBoxLayout()
        for text, fn in [
            ("Enter voucher", self.redeem),
            ("Local admin", open_admin_panel),
            ("Block Internet", self.block),
        ]:
            button = QPushButton(text)
            button.clicked.connect(fn)
            row.addWidget(button)
        root.addLayout(row)
        domains = QPushButton("Block domains")
        domains.clicked.connect(self.domains)
        root.addWidget(domains)
        self.timer = SessionManager()
        self.timer.tick.connect(lambda _seconds: self.update_state())
        self.timer.session_expired.connect(self.expire)
        self.update_state()

    def update_state(self):
        self.state.setText(
            f"NETWORK GUARD  •  INTERNET {'BLOCKED' if network_guard.is_blocked() else 'AVAILABLE'}"
        )

    def redeem(self):
        from PyQt6.QtWidgets import QInputDialog
        code, ok = QInputDialog.getText(self, "Voucher", "Voucher code:")
        if not ok or not code:
            return
        good, duration = db.redeem_voucher(code)
        if not good:
            QMessageBox.warning(self, "Voucher", "Invalid, used or revoked voucher.")
            return
        try:
            network_guard.unblock_internet()
            sid = db.create_session(code, duration)
            self.timer.start_session(sid, duration)
            self.update_state()
        except Exception as exc:
            QMessageBox.critical(self, "Network Guard", str(exc))

    def expire(self):
        try:
            network_guard.block_internet()
        finally:
            self.update_state()

    def block(self):
        try:
            network_guard.block_internet()
            self.update_state()
        except Exception as exc:
            QMessageBox.critical(self, "Network Guard", str(exc))

    def domains(self):
        from PyQt6.QtWidgets import QInputDialog
        value, ok = QInputDialog.getText(self, "Blocked domains", "Comma-separated domains:")
        if ok:
            try:
                network_guard.update_blocked_domains([x.strip() for x in value.split(",") if x.strip()])
            except Exception as exc:
                QMessageBox.critical(self, "Network Guard", str(exc))


class NEXLINKWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NEXLINK Command Center")
        self.resize(1320, 820)
        if ICON.exists():
            self.setWindowIcon(QIcon(str(ICON)))

        cfg = AgentConfig.load()
        if not cfg.server_url:
            dialog = SetupDialog(self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                raise RuntimeError("NEXLINK setup cancelled")
            cfg = AgentConfig.load()

        self.agent = None
        self.discovery_announcer = None
        try:
            from nexlink_agent.service import AgentService
            identity = DeviceIdentity.load_or_create(
                identity_path(), cfg.identity_passphrase or "nexlink-local"
            )
            self.agent = AgentService(cfg, identity)
            self.agent.start()
            self.discovery_announcer = ClientAnnouncer(identity.device_id, cfg.device_name, cfg.agent_version).start()
        except Exception as exc:
            QMessageBox.warning(self, "NEXLINK Agent", f"The endpoint agent could not start:\n{exc}")

        self.api = ApiClient(cfg.http_url)
        self.tabs = QTabWidget()
        self.login_tab = self._login_tab()
        self.tabs.addTab(self.login_tab, "Sign In")
        self.setCentralWidget(self.tabs)
        self.apply_style()

    def apply_style(self):
        self.setStyleSheet(
            "QMainWindow{background:#0b1220;} QLabel{color:#e8eef8;} "
            "QGroupBox{font-weight:bold;} QPushButton{padding:8px 12px;} "
            "QTabWidget::pane{border:1px solid #243247;}"
        )

    def _login_tab(self):
        widget = QWidget()
        form = QFormLayout(widget)
        self.email = QLineEdit()
        self.email.setPlaceholderText("admin@example.com")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.mfa = QLineEdit()
        self.mfa.setPlaceholderText("Optional 6-digit MFA")
        sign_in = QPushButton("Sign in to NEXLINK")
        sign_in.clicked.connect(self.login)
        form.addRow("Email:", self.email)
        form.addRow("Password:", self.password)
        form.addRow("MFA:", self.mfa)
        form.addRow(sign_in)
        self.login_status = QLabel("Connect to the NEXLINK Server.")
        form.addRow(self.login_status)
        return widget

    def login(self):
        try:
            data = self.api.login(
                self.email.text().strip(), self.password.text(), self.mfa.text().strip() or None
            )
            self.login_status.setText(
                f"Signed in as {data['user']['name']} • role={data['user']['role']}"
            )
            self.build_tabs()
        except Exception as exc:
            QMessageBox.critical(self, "Sign in failed", str(exc))

    def build_tabs(self):
        while self.tabs.count() > 1:
            self.tabs.removeTab(1)
        pages = [
            (DashboardTab(self.api), "Command Center"),
            (DevicesTab(self.api), "Devices / Remote"),
            (AlertsTab(self.api), "Alerts"),
            (NetworkTab(self.api), "Network Guard"),
            (AITab(self.api), "NEXLINK AI"),
            (AutomationTab(self.api), "Automation"),
            (SecurityTab(self.api), "Security Center"),
            (SupportTab(self.api), "Support Center"),
            (LocalGuardTab(self), "Local Guard"),
        ]
        for page, title in pages:
            self.tabs.addTab(page, title)
        about = QTextEdit()
        about.setReadOnly(True)
        about.setPlainText(
            "NEXLINK\n\nConnect • Control • Understand • Automate\n\n"
            "Remote Access + RMM + Network Guard + AI + Security Center + Automation + LAN-first operation.\n\n"
            "The former Internet Guard capability is integrated into NEXLINK; there is no separate product."
        )
        self.tabs.addTab(about, "About")

    def closeEvent(self, event):
        if self.discovery_announcer:
            self.discovery_announcer.stop()
        if self.agent:
            self.agent.stop()
        event.accept()


def _self_test():
    from nexlink_agent.protocol import Envelope
    env = Envelope(type="ping", payload={"timestamp": int(time.time())})
    env.validate()
    assert Envelope.from_json(env.to_json()).type == "ping"
    assert callable(network_guard.block_internet)
    print("NEXLINK Client self-test OK")
    return 0


def main():
    if "--self-test" in sys.argv:
        return _self_test()
    app = QApplication(sys.argv)
    app.setApplicationName("NEXLINK")
    if os.name == "nt" and not network_guard.is_admin():
        QMessageBox.critical(
            None,
            "NEXLINK",
            "NEXLINK Client must run elevated so Network Guard can enforce Windows firewall policy.",
        )
        return 1
    window = NEXLINKWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
