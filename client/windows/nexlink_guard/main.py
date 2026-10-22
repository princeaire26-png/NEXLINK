"""
NEXLINK - Internet Access Gate
Blocks outbound internet access on this PC until a voucher code is entered.
Must be run as Administrator.
"""
import os
import sys
from PyQt6.QtGui import QIcon, QPixmap, QColor
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon, QMenu

from nexlink_guard.common import db, network_controller
from nexlink_guard.common.gate_window import GateWindow
from nexlink_guard.common.overlay_widget import OverlayWidget
from nexlink_guard.common.session_manager import SessionManager
from nexlink_guard.common.admin_panel import open_admin_panel

# --- Constants ---
SINGLE_INSTANCE_KEY = "NEXLINK-SingleInstance"
_BASE_DIR = os.path.dirname(os.path.abspath(getattr(sys, "frozen", False) and sys.executable or __file__))
ICON_ICO_PATH = os.path.join(_BASE_DIR, "icon.ico")
ICON_PNG_PATH = os.path.join(_BASE_DIR, "icon.png")


# --- Helper Functions ---
def _make_icon() -> QIcon:
    """Loads the app icon, falling back to a generated colored square if assets are missing."""
    for path in (ICON_ICO_PATH, ICON_PNG_PATH):
        if os.path.isfile(path):
            icon = QIcon(path)
            if not icon.isNull():
                return icon
    
    # Fallback: 32x32 blue square
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor("#4f8cff"))
    return QIcon(pixmap)


# --- Main Application Class ---
class NEXLINKApp:
    def __init__(self, agent_process=None):
        self.agent_process = agent_process
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.app.setWindowIcon(_make_icon())
        self.app.aboutToQuit.connect(self._shutdown_agent)
        
        # 1. Initialize Database
        db.init_db()
        
        # 2. Initialize Core Components
        self.gate = GateWindow()
        self.overlay = OverlayWidget()
        self.session = SessionManager()
        self._local_server: QLocalServer | None = None
        
        # 3. Wire up Signals
        self.gate.unlocked.connect(self._on_unlocked)
        self.gate.admin_requested.connect(self._on_admin_requested)
        
        self.session.tick.connect(self.overlay.update_time)
        self.session.warning_triggered.connect(self._on_warning)
        self.session.session_expired.connect(self._on_expired)
        
        # 4. Initialize UI Elements
        self._build_tray_icon()

    def _shutdown_agent(self):
        if self.agent_process is not None and self.agent_process.poll() is None:
            try:
                self.agent_process.terminate()
            except OSError:
                pass

    def _build_tray_icon(self):
        """Creates the system tray icon and its context menu."""
        self.tray = QSystemTrayIcon(_make_icon(), self.app)
        self.tray.setToolTip("NEXLINK")

        menu = QMenu()
        
        show_action = menu.addAction("Enter voucher code")
        show_action.triggered.connect(self._show_gate_or_overlay)
        
        admin_action = menu.addAction("Admin Dashboard")
        admin_action.triggered.connect(self._on_admin_requested)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _show_gate_or_overlay(self):
        """Displays the correct UI based on current network state."""
        if network_controller.is_blocked():
            self.gate.show()
        else:
            self.overlay.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_gate_or_overlay()

    def _on_admin_requested(self):
        """Opens the superadmin dashboard."""
        open_admin_panel()

    def _on_unlocked(self, session_id: int, duration_minutes: int):
        """Handles successful voucher redemption."""
        self.gate.hide()
        try:
            network_controller.unblock_internet()
        except RuntimeError as exc:
            QMessageBox.critical(None, "NEXLINK", str(exc))
            return
        self.session.start_session(session_id, duration_minutes)
        self.overlay.show()

    def _on_warning(self, seconds_remaining: int):
        """Shows a warning dialog when time is running low (e.g., < 5 mins)."""
        minutes = seconds_remaining // 60
        QMessageBox.warning(
            None, "NEXLINK",
            f"NEXLINK internet access will end in about {minutes} minute(s)."
        )

    def _on_expired(self):
        """Handles session expiration or external revocation."""
        self.overlay.hide()
        try:
            network_controller.block_internet()
        except RuntimeError as exc:
            QMessageBox.critical(None, "NEXLINK", str(exc))
            return
        self.gate.show()

    def _start_single_instance_listener(self):
        """Starts a local server to detect and handle duplicate app launches."""
        self._local_server = QLocalServer()
        self._local_server.newConnection.connect(self._show_gate_or_overlay)
        QLocalServer.removeServer(SINGLE_INSTANCE_KEY)
        self._local_server.listen(SINGLE_INSTANCE_KEY)

    def run(self):
        """Main execution flow."""
        # 1. Check for existing instance
        probe = QLocalSocket()
        probe.connectToServer(SINGLE_INSTANCE_KEY)
        if probe.waitForConnected(200):
            probe.disconnectFromServer()
            sys.exit(0)  # Signal existing instance to show UI, then exit this one

        # 2. Verify Administrator privileges
        if not network_controller.is_admin():
            QMessageBox.critical(
                None, "NEXLINK",
                "NEXLINK must be run as Administrator to control the firewall."
            )
            sys.exit(1)

        # 3. Start single-instance listener
        self._start_single_instance_listener()

        # 4. Restore previous session or start blocked
        resumed = self.session.load_active_session()
        if resumed:
            try:
                network_controller.unblock_internet()
            except RuntimeError as exc:
                QMessageBox.critical(None, "NEXLINK", str(exc))
                network_controller.block_internet()
                self.gate.show()
                return
            self.overlay.show()
        else:
            try:
                network_controller.block_internet()
            except RuntimeError as exc:
                QMessageBox.critical(None, "NEXLINK", str(exc))
                return
            self.gate.show()
            
        # 5. Start Event Loop
        return self.app.exec()


if __name__ == "__main__":
    NEXLINKApp().run()