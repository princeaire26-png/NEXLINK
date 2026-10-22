"""Countdown timer + signals. Persists the active session so the app
survives restarts (e.g. if the PC reboots mid-session)."""
from __future__ import annotations
from datetime import datetime, timedelta
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from nexlink_guard.common import db

WARNING_THRESHOLD_SECONDS = 120


class SessionManager(QObject):
    tick = pyqtSignal(int)
    warning_triggered = pyqtSignal(int)
    session_expired = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)
        self._session_id: int | None = None
        self._expires_at: datetime | None = None
        self._warning_fired = False

    def start_session(self, session_id: int, duration_minutes: int) -> None:
        self._session_id = session_id
        self._expires_at = datetime.now() + timedelta(minutes=duration_minutes)
        self._warning_fired = False
        self._timer.start()
        self.tick.emit(self.seconds_remaining())

    def load_active_session(self) -> bool:
        db.end_expired_sessions()
        session = db.get_active_session()
        if session is None:
            return False
        self._session_id = session["id"]
        self._expires_at = datetime.fromisoformat(session["expires_at"])
        self._warning_fired = self.seconds_remaining() <= WARNING_THRESHOLD_SECONDS
        self._timer.start()
        self.tick.emit(self.seconds_remaining())
        return True

    def seconds_remaining(self) -> int:
        if self._expires_at is None:
            return 0
        return max(0, int((self._expires_at - datetime.now()).total_seconds()))

    def _on_tick(self) -> None:
        # 1. Check if session was revoked externally by the admin panel
        if self._session_id is not None and not db.is_session_active(self._session_id):
            self._timer.stop()
            self._session_id = None
            self._expires_at = None
            self.session_expired.emit()
            return

        # 2. Normal countdown logic
        remaining = self.seconds_remaining()
        self.tick.emit(remaining)
        
        if 0 < remaining <= WARNING_THRESHOLD_SECONDS and not self._warning_fired:
            self._warning_fired = True
            self.warning_triggered.emit(remaining)
            
        if remaining <= 0:
            self._timer.stop()
            if self._session_id is not None:
                db.end_session(self._session_id)
                self._session_id = None
            self._expires_at = None
            self.session_expired.emit()