"""Small centered always-on-top popup with voucher entry and a visible
admin button. Unlike a fullscreen lock screen, this can be closed without
entering a code -- closing it does NOT unblock the network; the firewall
rule is controlled independently by network_controller, so dismissing
this window just hides the prompt, it doesn't grant access. See
main.py / tray icon for how the user reopens it."""
from __future__ import annotations
import os
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QIcon
from PyQt6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget
from nexlink_guard.common import db, network_controller
from nexlink_guard.common.theme import apply_theme

_ICON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icon.ico")


class GateWindow(QWidget):
    unlocked = pyqtSignal(int, int)
    admin_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Dialog
        )
        self.setWindowTitle("NEXLINK")
        if os.path.isfile(_ICON_PATH):
            self.setWindowIcon(QIcon(_ICON_PATH))
        self.setFixedSize(360, 300)
        apply_theme(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)

        title = QLabel("🔒  NEXLINK Internet Access Locked")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Enter your voucher code to continue.")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("XXXX-XXXX-XXXX")
        self.code_input.setMaxLength(14)
        self.code_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.code_input.returnPressed.connect(self._try_redeem)
        layout.addWidget(self.code_input)

        self.error_label = QLabel("")
        self.error_label.setObjectName("error")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.error_label)

        layout.addSpacing(6)

        submit = QPushButton("Unlock")
        submit.setObjectName("primary")
        submit.setMinimumHeight(36)
        submit.clicked.connect(self._try_redeem)
        layout.addWidget(submit)

        admin_btn = QPushButton("Admin")
        admin_btn.setMinimumHeight(30)
        admin_btn.clicked.connect(self.admin_requested.emit)
        layout.addWidget(admin_btn)

    def show(self) -> None:
        self._center_on_screen()
        super().show()
        self.raise_()
        self.activateWindow()
        self.code_input.setFocus()

    def _center_on_screen(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2,
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        # Closing the popup only hides it -- it does NOT unblock the
        # network. The firewall rule stays active until a valid voucher
        # is redeemed. The user can reopen this via the tray icon.
        event.ignore()
        self.hide()

    def _try_redeem(self) -> None:
        code = self.code_input.text().strip().upper()
        if not code:
            return
        if network_controller.is_remote_blocked():
            self.error_label.setText("Internet access is locked by the NEXLINK server.")
            return
        ok, duration = db.redeem_voucher(code)
        if not ok:
            self.error_label.setText("Invalid or already-used code.")
            self.code_input.selectAll()
            return
        session_id = db.create_session(code, duration)
        self.code_input.clear()
        self.error_label.clear()
        self.unlocked.emit(session_id, duration)
