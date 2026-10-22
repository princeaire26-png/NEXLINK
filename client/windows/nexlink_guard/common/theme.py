"""Shared dark QSS theme."""
from __future__ import annotations
from PyQt6.QtWidgets import QWidget

DARK_QSS = """
* { background-color: #1e1e2e; color: #cdd6f4; font-family: 'Segoe UI', sans-serif; }
QLabel#title { font-size: 22px; font-weight: bold; color: #89b4fa; }
QLabel#subtitle { font-size: 14px; color: #a6adc8; }
QLabel#error { color: #f38ba8; font-size: 12px; }
QLabel#overlayTitle { font-size: 11px; font-weight: bold; color: #a6e3a1; }
QLabel#overlayTime { font-size: 22px; font-weight: bold; color: #cdd6f4; }
QLabel#result { font-size: 16px; color: #f9e2af; font-family: 'Consolas', monospace; }
QLineEdit { background-color: #313244; border: 1px solid #45475a; border-radius: 6px; padding: 10px; font-size: 18px; letter-spacing: 3px; }
QLineEdit:focus { border: 1px solid #89b4fa; }
QPushButton { background-color: #89b4fa; color: #1e1e2e; border: none; padding: 9px 16px; border-radius: 6px; font-weight: bold; }
QPushButton:hover { background-color: #b4befe; }
QPushButton:pressed { background-color: #74c7ec; }
QPushButton#primary { min-height: 22px; }
QSpinBox { background-color: #313244; border: 1px solid #45475a; border-radius: 4px; padding: 4px 6px; }
QDialog, QInputDialog, QMessageBox { background-color: #1e1e2e; }
QWidget#overlay { background-color: #181825; border: 1px solid #45475a; border-radius: 8px; }
"""


def apply_theme(widget: QWidget) -> None:
    widget.setStyleSheet(DARK_QSS)
