"""Small frameless bottom-right countdown overlay, shown while internet
access is unlocked so the child can see how much time is left.
Disappears on hover to allow clicking system tray icons underneath."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from nexlink_guard.common.theme import apply_theme


class OverlayWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setFixedSize(190, 70)
        apply_theme(self)
        self.setObjectName("overlay")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        title = QLabel("NEXLINK Internet Active")
        title.setObjectName("overlayTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.time_label = QLabel("00:00")
        self.time_label.setObjectName("overlayTime")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.time_label)

        # Hover-to-disappear logic initialization
        self._hover_timer = QTimer()
        self._hover_timer.timeout.connect(self._check_mouse_position)
        self._is_hidden_for_hover = False

    def show(self) -> None:
        self._move_to_corner()
        super().show()

    def update_time(self, seconds_remaining: int) -> None:
        h = seconds_remaining // 3600
        m = (seconds_remaining % 3600) // 60
        s = seconds_remaining % 60
        self.time_label.setText(f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}")

    def _move_to_corner(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - self.width() - 10, screen.bottom() - self.height() - 10)

    def enterEvent(self, event) -> None:
        """Triggered when the mouse cursor enters the widget area."""
        super().enterEvent(event)
        self._hide_for_hover()

    def _hide_for_hover(self) -> None:
        """Makes the widget visually invisible and click-through."""
        if not self._is_hidden_for_hover:
            self._is_hidden_for_hover = True
            
            # 1. Make visually invisible
            self.setWindowOpacity(0.0)
            
            # 2. Make click-through so the user can click taskbar icons underneath
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            
            # 3. Start timer to check when the mouse leaves.
            # (We must use a timer because WA_TransparentForMouseEvents prevents leaveEvent from firing)
            self._hover_timer.start(100)

    def _check_mouse_position(self) -> None:
        """Checks if the global cursor has moved outside the widget's boundaries."""
        cursor_pos = self.mapFromGlobal(QCursor.pos())
        if not self.rect().contains(cursor_pos):
            # Mouse has left the widget area
            self._restore_from_hover()

    def _restore_from_hover(self) -> None:
        """Restores the widget's visibility and click-blocking behavior."""
        if self._is_hidden_for_hover:
            self._is_hidden_for_hover = False
            
            # Restore visibility and mouse interaction
            self.setWindowOpacity(1.0)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            
            # Stop polling to save CPU cycles
            self._hover_timer.stop()