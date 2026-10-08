"""Login + admin panels.
Login now asks for username AND password (multiple admin accounts exist).
Which panel opens depends on the authenticated user's role:
admin:       generate vouchers (sees only their own), change own password
superadmin:  everything an admin can do, plus create/delete admin
             accounts, reset any account's password, revoke active sessions,
             and manage blocked websites.
"""
from __future__ import annotations
import os
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDialog, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)
from nexlink_guard.common import db, network_controller
from nexlink_guard.common.theme import apply_theme

_ICON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icon.ico")


def open_admin_panel() -> None:
    parent = QApplication.activeWindow()
    dialog = LoginDialog(parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return
    AdminPanel(dialog.user, parent).exec()


class LoginDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Admin Login")
        if os.path.isfile(_ICON_PATH):
            self.setWindowIcon(QIcon(_ICON_PATH))
        self.setModal(True)
        self.resize(320, 180)
        self.user: dict | None = None
        apply_theme(self)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Username:"))
        self.username_input = QLineEdit()
        layout.addWidget(self.username_input)
        layout.addWidget(QLabel("Password:"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self._try_login)
        layout.addWidget(self.password_input)
        self.error_label = QLabel("")
        self.error_label.setObjectName("error")
        layout.addWidget(self.error_label)
        login_btn = QPushButton("Login")
        login_btn.clicked.connect(self._try_login)
        layout.addWidget(login_btn)
        self.username_input.setFocus()

    def _try_login(self) -> None:
        user = db.verify_user(self.username_input.text(), self.password_input.text())
        if user is None:
            self.error_label.setText("Incorrect username or password.")
            self.password_input.clear()
            return
        self.user = user
        self.accept()


class AdminPanel(QDialog):
    def __init__(self, user: dict, parent=None) -> None:
        super().__init__(parent)
        self.user = user
        self.setWindowTitle(f"NEXLINK Admin -- {user['username']} ({user['role']})")
        if os.path.isfile(_ICON_PATH):
            self.setWindowIcon(QIcon(_ICON_PATH))
        self.setModal(True)
        self.resize(600, 500)
        apply_theme(self)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        
        # Available to ALL admins
        tabs.addTab(self._build_voucher_tab(), "Vouchers")
        tabs.addTab(self._build_account_tab(), "My Account")
        
        # SUPERADMIN-ONLY tabs
        if user["role"] == db.ROLE_SUPERADMIN:
            tabs.addTab(self._build_manage_admins_tab(), "Manage Admins")
            tabs.addTab(self._build_active_sessions_tab(), "Active Sessions")
            tabs.addTab(self._build_blocked_sites_tab(), "Blocked Sites")
            
        layout.addWidget(tabs)
        
        if user["role"] == db.ROLE_SUPERADMIN:
            quit_btn = QPushButton("Quit NEXLINK")
            quit_btn.clicked.connect(self._quit_app)
            layout.addWidget(quit_btn)

    def _quit_app(self) -> None:
        confirm = QMessageBox.question(
            self, "Confirm", "Quit NEXLINK? This stops all enforcement until it's launched again."
        )
        if confirm == QMessageBox.StandardButton.Yes:
            QApplication.instance().quit()

    # ---------------------------------------------------------- vouchers --
    def _build_voucher_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        title = QLabel("Generate Voucher")
        title.setObjectName("title")
        layout.addWidget(title)
        
        row = QHBoxLayout()
        row.addWidget(QLabel("Duration:"))
        self.duration = QSpinBox()
        self.duration.setRange(1, 24 * 60)
        self.duration.setValue(60)
        self.duration.setSuffix(" min")
        row.addWidget(self.duration)
        
        hours_btn = QPushButton("Set in hours...")
        hours_btn.clicked.connect(self._set_hours)
        row.addWidget(hours_btn)
        layout.addLayout(row)
        
        generate_btn = QPushButton("Generate Voucher")
        generate_btn.setObjectName("primary")
        generate_btn.clicked.connect(self._generate)
        layout.addWidget(generate_btn)
        
        self.result_label = QLabel("")
        self.result_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.result_label)
        
        history_label = QLabel(
            "All vouchers" if self.user["role"] == db.ROLE_SUPERADMIN else "Your vouchers"
        )
        layout.addWidget(history_label)
        
        self.history_list = QListWidget()
        layout.addWidget(self.history_list)
        self._refresh_history()
        return tab

    def _set_hours(self) -> None:
        h, ok = QInputDialog.getInt(self, "Hours", "Duration in hours:", 1, 1, 24)
        if ok:
            self.duration.setValue(h * 60)

    def _generate(self) -> None:
        code = db.generate_voucher(self.duration.value(), self.user["username"])
        self.result_label.setText(f"Voucher code:\n{code}")
        self._refresh_history()

    def _refresh_history(self) -> None:
        self.history_list.clear()
        created_by = None if self.user["role"] == db.ROLE_SUPERADMIN else self.user["username"]
        for v in db.list_vouchers(created_by=created_by, limit=15):
            status = "used" if v["used"] else "unused"
            hours = v["duration_minutes"] / 60
            who = f"  ·  by {v['created_by']}" if created_by is None else ""
            self.history_list.addItem(
                QListWidgetItem(f"{v['code']}  ·  {hours:g}h  ·  {status}{who}")
            )

    # --------------------------------------------------------- my account --
    def _build_account_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel(f"Logged in as: {self.user['username']} ({self.user['role']})"))
        layout.addStretch()
        change_pw_btn = QPushButton("Change my password")
        change_pw_btn.clicked.connect(self._change_own_password)
        layout.addWidget(change_pw_btn)
        return tab

    def _change_own_password(self) -> None:
        new, ok = QInputDialog.getText(
            self, "Change Password", "New password:", QLineEdit.EchoMode.Password
        )
        if ok and new:
            db.set_password(self.user["username"], new)
            QMessageBox.information(self, "Account", "Password changed.")

    # --------------------------------------------------- manage admins --
    def _build_manage_admins_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        title = QLabel("Admin Accounts")
        title.setObjectName("title")
        layout.addWidget(title)
        
        self.users_list = QListWidget()
        layout.addWidget(self.users_list)
        self._refresh_users()
        
        create_row = QHBoxLayout()
        self.new_username = QLineEdit()
        self.new_username.setPlaceholderText("Username")
        create_row.addWidget(self.new_username)
        
        self.new_password = QLineEdit()
        self.new_password.setPlaceholderText("Password")
        self.new_password.setEchoMode(QLineEdit.EchoMode.Password)
        create_row.addWidget(self.new_password)
        
        self.new_role = QComboBox()
        self.new_role.addItems([db.ROLE_ADMIN, db.ROLE_SUPERADMIN])
        create_row.addWidget(self.new_role)
        layout.addLayout(create_row)
        
        create_btn = QPushButton("Create Account")
        create_btn.clicked.connect(self._create_account)
        layout.addWidget(create_btn)
        
        button_row = QHBoxLayout()
        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self._delete_selected)
        button_row.addWidget(delete_btn)
        
        reset_pw_btn = QPushButton("Reset Password for Selected")
        reset_pw_btn.clicked.connect(self._reset_selected_password)
        button_row.addWidget(reset_pw_btn)
        layout.addLayout(button_row)
        return tab

    def _refresh_users(self) -> None:
        self.users_list.clear()
        for u in db.list_users():
            self.users_list.addItem(f"{u['username']}  ·  {u['role']}")

    def _selected_username(self) -> str | None:
        item = self.users_list.currentItem()
        if item is None:
            return None
        return item.text().split("  ·  ")[0]

    def _create_account(self) -> None:
        ok, message = db.create_user(
            self.new_username.text(), self.new_password.text(), self.new_role.currentText()
        )
        QMessageBox.information(self, "Manage Admins", message)
        if ok:
            self.new_username.clear()
            self.new_password.clear()
            self._refresh_users()

    def _delete_selected(self) -> None:
        username = self._selected_username()
        if username is None:
            return
        if username == self.user["username"]:
            QMessageBox.warning(self, "Manage Admins", "You cannot delete your own account while logged in.")
            return
        confirm = QMessageBox.question(
            self, "Confirm", f"Delete account '{username}'? This cannot be undone."
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        ok, message = db.delete_user(username)
        QMessageBox.information(self, "Manage Admins", message)
        if ok:
            self._refresh_users()

    def _reset_selected_password(self) -> None:
        username = self._selected_username()
        if username is None:
            return
        new, ok = QInputDialog.getText(
            self, "Reset Password", f"New password for '{username}':", QLineEdit.EchoMode.Password
        )
        if ok and new:
            db.set_password(username, new)
            QMessageBox.information(self, "Manage Admins", "Password reset.")

    # ------------------------------------------------ active sessions --
    def _build_active_sessions_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        title = QLabel("Active Sessions")
        title.setObjectName("title")
        layout.addWidget(title)
        
        self.sessions_table = QTableWidget()
        self.sessions_table.setColumnCount(4)
        self.sessions_table.setHorizontalHeaderLabels(["Session ID", "Voucher Code", "Started At", "Action"])
        self.sessions_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.sessions_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.sessions_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.sessions_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.sessions_table)
        
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_active_sessions)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self._refresh_active_sessions()
        return tab

    def _refresh_active_sessions(self) -> None:
        sessions = db.get_active_sessions()
        self.sessions_table.setRowCount(len(sessions))
        
        for row, session in enumerate(sessions):
            session_id = session["id"]
            code = session["voucher_code"]
            started_at = session["started_at"]
            
            self.sessions_table.setItem(row, 0, QTableWidgetItem(str(session_id)))
            self.sessions_table.setItem(row, 1, QTableWidgetItem(code))
            self.sessions_table.setItem(row, 2, QTableWidgetItem(started_at))
            
            revoke_btn = QPushButton("Revoke")
            revoke_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            revoke_btn.setStyleSheet("""
                QPushButton {
                    background-color: #dc3545; 
                    color: white; 
                    font-weight: bold; 
                    border-radius: 4px; 
                    padding: 4px 8px;
                }
                QPushButton:hover { background-color: #c82333; }
                QPushButton:pressed { background-color: #bd2130; }
            """)
            revoke_btn.clicked.connect(lambda checked, sid=session_id: self._revoke_session(sid))
            self.sessions_table.setCellWidget(row, 3, revoke_btn)

    def _revoke_session(self, session_id: int) -> None:
        reply = QMessageBox.question(
            self, "Confirm Revoke", 
            f"Are you sure you want to revoke session #{session_id}?\n\n"
            "This will immediately terminate internet access for this device.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            success = db.revoke_active_session(session_id)
            if success:
                QMessageBox.information(
                    self, "Success", 
                    "Session revoked successfully. Internet access will be blocked momentarily."
                )
                self._refresh_active_sessions()
            else:
                QMessageBox.warning(
                    self, "Error", 
                    "Failed to revoke session. It may have already ended or been revoked."
                )

    # -------------------------------------------------- blocked sites --
    def _build_blocked_sites_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        title = QLabel("Blocked Websites")
        title.setObjectName("title")
        layout.addWidget(title)
        
        info_label = QLabel("Add domains to block (e.g., facebook.com, youtube.com)")
        info_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(info_label)
        
        # Add URL input
        add_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter domain (e.g., facebook.com)")
        self.url_input.returnPressed.connect(self._add_blocked_url)
        add_row.addWidget(self.url_input)
        
        add_btn = QPushButton("Block")
        add_btn.setObjectName("primary")
        add_btn.clicked.connect(self._add_blocked_url)
        add_row.addWidget(add_btn)
        layout.addLayout(add_row)
        
        # Blocked URLs table
        self.blocked_table = QTableWidget()
        self.blocked_table.setColumnCount(3)
        self.blocked_table.setHorizontalHeaderLabels(["Domain", "Added By", "Action"])
        self.blocked_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.blocked_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.blocked_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.blocked_table)
        
        self._refresh_blocked_urls()
        return tab

    def _add_blocked_url(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            return
        
        success, message = db.add_blocked_url(url, self.user["username"])
        QMessageBox.information(self, "Blocked Sites", message)
        
        if success:
            self.url_input.clear()
            self._refresh_blocked_urls()
            # Apply changes to hosts file
            network_controller.update_blocked_urls(db.get_blocked_domains())

    def _refresh_blocked_urls(self) -> None:
        blocked = db.list_blocked_urls()
        self.blocked_table.setRowCount(len(blocked))
        
        for row, item in enumerate(blocked):
            self.blocked_table.setItem(row, 0, QTableWidgetItem(item["domain"]))
            self.blocked_table.setItem(row, 1, QTableWidgetItem(item["added_by"]))
            
            remove_btn = QPushButton("Remove")
            remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            remove_btn.setStyleSheet("""
                QPushButton {
                    background-color: #6c757d; 
                    color: white; 
                    border-radius: 4px; 
                    padding: 4px 8px;
                }
                QPushButton:hover { background-color: #5a6268; }
            """)
            remove_btn.clicked.connect(lambda checked, uid=item["id"]: self._remove_blocked_url(uid))
            self.blocked_table.setCellWidget(row, 2, remove_btn)

    def _remove_blocked_url(self, url_id: int) -> None:
        reply = QMessageBox.question(
            self, "Confirm", 
            "Remove this site from the block list?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if db.remove_blocked_url(url_id):
                self._refresh_blocked_urls()
                # Apply changes to hosts file
                network_controller.update_blocked_urls(db.get_blocked_domains())