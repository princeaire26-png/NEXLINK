"""NEXLINK unified Windows command center: remote access + RMM + Network Guard + AI + security."""
from __future__ import annotations
import os, platform, sys, time
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, QLineEdit, QPushButton, QDialog, QFormLayout, QMessageBox, QTextEdit, QComboBox
from PyQt6.QtGui import QIcon
from nexlink_agent.config import AgentConfig, identity_path
from nexlink_agent.identity import DeviceIdentity
from nexlink_agent.service import AgentService
from nexlink_agent.main import enroll
from nexlink_agent.urls import http_base, websocket_base
from nexlink_agent import network_guard
from nexlink_guard.common import db
from nexlink_guard.common.gate_window import GateWindow
from nexlink_guard.common.overlay_widget import OverlayWidget
from nexlink_guard.common.session_manager import SessionManager
from nexlink_guard.common.admin_panel import open_admin_panel
from nexlink_ui import ApiClient, DashboardTab, DevicesTab, AlertsTab, NetworkTab, AITab, SecurityTab, AutomationTab, SupportTab
from nexlink_discovery import discover_servers

APP_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
ICON = APP_ROOT / "assets" / "icons" / "nexlink-client.ico"

class ServerDiscoveryWorker(QThread):
    servers_found = pyqtSignal(list)

    def run(self):
        try:
            servers = discover_servers(timeout=2.5)
        except Exception:
            servers = []
        self.servers_found.emit(servers)


class SetupDialog(QDialog):
    def __init__(self,parent=None,auto_discover=True):
        super().__init__(parent); self.setWindowTitle('NEXLINK Setup'); self.resize(560,340); form=QFormLayout(self)
        self._discovery_thread = None
        self.server=QLineEdit(); self.server.setPlaceholderText('192.168.1.20:8000 or https://server.example.com'); self.token=QLineEdit(); self.token.setPlaceholderText('Enrollment token'); self.name=QLineEdit(platform.node()); self.passphrase=QLineEdit('nexlink-local'); self.passphrase.setEchoMode(QLineEdit.EchoMode.Password)
        self.discovered_servers=QComboBox()
        self.discovered_servers.addItem('Choose a NEXLINK server found on this LAN…','')
        self.discovered_servers.currentIndexChanged.connect(self._select_discovered_server)
        self.discovery_status=QLabel('Searching for NEXLINK servers on this LAN…')
        self.find_servers_button=QPushButton('Scan LAN for servers')
        self.find_servers_button.clicked.connect(self.find_servers)
        form.addRow('Server:',self.server)
        form.addRow('Discovered servers:',self.discovered_servers)
        form.addRow('Discovery:',self.discovery_status)
        form.addRow(self.find_servers_button)
        for label,widget in [('Enrollment token:',self.token),('Device name:',self.name),('Identity passphrase:',self.passphrase)]: form.addRow(label,widget)
        b=QPushButton('Save / Enroll'); b.clicked.connect(self.accept_setup); form.addRow(b)
        if auto_discover:
            self.find_servers()

    def find_servers(self):
        if self._discovery_thread is not None and self._discovery_thread.isRunning():
            return
        self.find_servers_button.setEnabled(False)
        self.discovery_status.setText('Scanning the local network for NEXLINK servers…')
        worker=ServerDiscoveryWorker(self)
        worker.servers_found.connect(self._on_servers_found)
        worker.finished.connect(self._on_discovery_finished)
        self._discovery_thread=worker
        worker.start()

    def _on_discovery_finished(self):
        self.find_servers_button.setEnabled(True)
        worker=self._discovery_thread
        self._discovery_thread=None
        if worker is not None:
            worker.deleteLater()

    def _on_servers_found(self,servers):
        self.discovered_servers.clear()
        self.discovered_servers.addItem('Choose a NEXLINK server found on this LAN…','')
        for server in servers:
            url=server.get('url')
            if not url:
                continue
            host=server.get('hostname') or 'NEXLINK Server'
            self.discovered_servers.addItem(f"{host} — {server.get('ip')}:{server.get('port',8000)}",url)
        count=self.discovered_servers.count()-1
        if count == 1:
            self.discovery_status.setText('One server found. Its address has been filled in; confirm it before saving.')
            self.discovered_servers.setCurrentIndex(1)
        elif count > 1:
            self.discovery_status.setText(f'{count} servers found. Choose the server you want to use.')
        else:
            self.discovery_status.setText('No server found. Enter its address manually or scan again.')

    def _select_discovered_server(self,index):
        url=self.discovered_servers.itemData(index)
        if url:
            self.server.setText(url)

    def closeEvent(self,event):
        if self._discovery_thread is not None and self._discovery_thread.isRunning():
            self._discovery_thread.wait(3000)
        event.accept()

    def accept_setup(self):
        if not self.server.text().strip(): QMessageBox.warning(self,'NEXLINK','Enter the server address.'); return
        try:
            server_url = http_base(self.server.text())
        except ValueError as exc:
            QMessageBox.warning(self, 'NEXLINK', str(exc))
            return
        cfg=AgentConfig(server_url=server_url,device_name=self.name.text().strip() or platform.node(),identity_passphrase=self.passphrase.text(),agent_version='2.0.0'); cfg.save(); ident=DeviceIdentity.load_or_create(identity_path(),cfg.identity_passphrase)
        if self.token.text().strip():
            try: QMessageBox.information(self,'Enrollment',enroll(cfg,ident,self.token.text().strip()).get('message','Enrollment submitted.'))
            except Exception as exc: QMessageBox.critical(self,'Enrollment failed',str(exc)); return
        self.accept()

class LocalGuardTab(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent); db.init_db(); root=QVBoxLayout(self); self.state=QLabel(); root.addWidget(self.state); row=QHBoxLayout()
        for text,fn in [('Enter voucher',self.redeem),('Local admin',open_admin_panel),('Block Internet',self.block)]: b=QPushButton(text); b.clicked.connect(fn); row.addWidget(b)
        root.addLayout(row); domain=QPushButton('Block domains'); domain.clicked.connect(self.domains); root.addWidget(domain); self.timer=SessionManager(); self.timer.tick.connect(lambda s:self.update_state()); self.timer.session_expired.connect(self.expire); self.update_state()
    def update_state(self): self.state.setText(f"NETWORK GUARD • INTERNET {'BLOCKED' if network_guard.is_blocked() else 'AVAILABLE'}")
    def redeem(self):
        from PyQt6.QtWidgets import QInputDialog
        code,ok=QInputDialog.getText(self,'Voucher','Voucher code:');
        if not ok:return
        good,duration=db.redeem_voucher(code)
        if not good: QMessageBox.warning(self,'Voucher','Invalid, used or revoked voucher.'); return
        try: network_guard.unblock_internet(); sid=db.create_session(code,duration); self.timer.start_session(sid,duration); self.update_state()
        except Exception as exc: QMessageBox.critical(self,'Network Guard',str(exc))
    def expire(self):
        try: network_guard.block_internet()
        except Exception: pass
        self.update_state()
    def block(self):
        try: network_guard.block_internet(); self.update_state()
        except Exception as exc: QMessageBox.critical(self,'Network Guard',str(exc))
    def domains(self):
        from PyQt6.QtWidgets import QInputDialog
        d,ok=QInputDialog.getText(self,'Blocked domains','Comma-separated domains:');
        if ok:
            try: network_guard.update_blocked_domains([x.strip() for x in d.split(',') if x.strip()])
            except Exception as exc: QMessageBox.critical(self,'Network Guard',str(exc))

class NEXLINKWindow(QMainWindow):
    def __init__(self, smoke_test: bool = False):
        super().__init__(); self.setWindowTitle('NEXLINK Command Center'); self.resize(1320,820)
        if ICON.exists(): self.setWindowIcon(QIcon(str(ICON)))
        cfg=AgentConfig.load()
        if not cfg.server_url:
            if smoke_test:
                cfg=AgentConfig(server_url='http://127.0.0.1:8000',device_name='NEXLINK Build Smoke Test',identity_passphrase='nexlink-package-self-test')
            else:
                dlg=SetupDialog(self)
                if dlg.exec()!=QDialog.DialogCode.Accepted: raise RuntimeError('NEXLINK setup cancelled')
                cfg=AgentConfig.load()
        self.agent=None
        if not smoke_test:
            try: self.agent=AgentService(cfg,DeviceIdentity.load_or_create(identity_path(),cfg.identity_passphrase or 'nexlink-local')); self.agent.start()
            except Exception as exc: QMessageBox.warning(self,'NEXLINK Agent',f'Agent could not start:\n{exc}')
        self.api=ApiClient(cfg.server_url); self.tabs=QTabWidget(); self.login_tab=self._login_tab(); self.tabs.addTab(self.login_tab,'Sign In'); self.setCentralWidget(self.tabs)
        self.apply_style()
    def apply_style(self): self.setStyleSheet('QMainWindow{background:#0b1220;} QGroupBox{font-weight:bold;} QPushButton{padding:7px 12px;} QTabWidget::pane{border:1px solid #243247;}')
    def _login_tab(self):
        w=QWidget(); form=QFormLayout(w); self.email=QLineEdit(); self.password=QLineEdit(); self.password.setEchoMode(QLineEdit.EchoMode.Password); self.mfa=QLineEdit(); self.mfa.setPlaceholderText('Optional 6-digit MFA'); b=QPushButton('Sign in to NEXLINK'); b.clicked.connect(self.login); form.addRow('Email:',self.email); form.addRow('Password:',self.password); form.addRow('MFA:',self.mfa); form.addRow(b); self.login_status=QLabel('Connect to the NEXLINK server.'); form.addRow(self.login_status); return w
    def login(self):
        try:
            data=self.api.login(self.email.text(),self.password.text(),self.mfa.text().strip() or None); self.login_status.setText(f"Signed in as {data['user']['name']} • role={data['user']['role']}"); self.build_tabs()
        except Exception as exc: QMessageBox.critical(self,'Sign in failed',str(exc))
    def build_tabs(self):
        while self.tabs.count()>1: self.tabs.removeTab(1)
        self.tabs.addTab(DashboardTab(self.api),'Command Center'); self.tabs.addTab(DevicesTab(self.api),'Devices / Remote'); self.tabs.addTab(AlertsTab(self.api),'Alerts'); self.tabs.addTab(NetworkTab(self.api),'Network Guard'); self.tabs.addTab(AITab(self.api),'NEXLINK AI'); self.tabs.addTab(AutomationTab(self.api),'Automation'); self.tabs.addTab(SecurityTab(self.api),'Security Center'); self.tabs.addTab(SupportTab(self.api),'Support Center'); self.tabs.addTab(LocalGuardTab(self),'Local Guard'); about=QTextEdit(); about.setReadOnly(True); about.setPlainText('NEXLINK\n\nConnect • Control • Understand • Automate\n\nRemote Access + RMM + Network Guard + AI + Security Center + Automation + LAN-first operation.\n\nThis build keeps the former Internet Guard capability inside NEXLINK; it is not a separate product.') ; self.tabs.addTab(about,'About')
    def closeEvent(self,event):
        if self.agent:self.agent.stop()
        event.accept()

def _self_test():
    from nexlink_agent.protocol import Envelope
    import nexlink_agent.remote as remote
    import tempfile
    env=Envelope(type='ping',payload={'timestamp':int(time.time())}); env.validate(); assert Envelope.from_json(env.to_json()).type=='ping'
    assert http_base('192.168.1.20:8000') == 'http://192.168.1.20:8000'
    assert websocket_base('192.168.1.20:8000') == 'ws://192.168.1.20:8000/ws'
    assert http_base('wss://nexlink.example.com/ws') == 'https://nexlink.example.com'
    assert AgentConfig(server_url='192.168.1.20:8000').server_url == '192.168.1.20:8000'
    assert callable(network_guard.block_internet)
    assert all(callable(getattr(remote, name, None)) for name in ('capture_frame', 'apply_input', 'read_file'))
    assert callable(AgentService) and callable(AITab)
    with tempfile.TemporaryDirectory() as folder:
        identity_file = Path(folder) / 'identity.json'
        identity = DeviceIdentity.load_or_create(identity_file, 'nexlink-package-self-test')
        restored = DeviceIdentity.load(identity_file, 'nexlink-package-self-test')
        assert restored.device_id == identity.device_id
        old_local_app_data = os.environ.get('LOCALAPPDATA')
        try:
            os.environ['LOCALAPPDATA'] = folder
            AgentConfig(server_url='http://127.0.0.1:8000', device_name='NEXLINK Build Smoke Test',
                        identity_passphrase='nexlink-package-self-test').save()
            assert AgentConfig.load().server_url == 'http://127.0.0.1:8000'
            app = QApplication.instance() or QApplication([])
            app.setApplicationName('NEXLINK Build Smoke Test')
            setup=SetupDialog(auto_discover=False)
            setup._on_servers_found([{
                'hostname':'NEXLINK-SERVER',
                'ip':'192.168.1.20',
                'port':8000,
                'url':'http://192.168.1.20:8000',
            }])
            assert setup.discovered_servers.count() == 2
            assert setup.server.text() == 'http://192.168.1.20:8000'
            setup.close()
            window = NEXLINKWindow(smoke_test=True)
            assert window.windowTitle() == 'NEXLINK Command Center'
            assert window.tabs.count() == 1
            assert not window.windowIcon().isNull()
            window.show()
            app.processEvents()
            assert window.isVisible()
            window.close()
            app.processEvents()
        finally:
            if old_local_app_data is None:
                os.environ.pop('LOCALAPPDATA', None)
            else:
                os.environ['LOCALAPPDATA'] = old_local_app_data
    print('NEXLINK Client self-test and Qt UI smoke test OK'); return 0

def main():
    if '--self-test' in sys.argv:return _self_test()
    app=QApplication(sys.argv); app.setApplicationName('NEXLINK')
    if os.name=='nt' and not network_guard.is_admin(): QMessageBox.critical(None,'NEXLINK','Run NEXLINK-Client.exe as Administrator so Network Guard can enforce Windows Firewall policy.'); return 1
    w=NEXLINKWindow(); w.show(); return app.exec()

if __name__=='__main__': raise SystemExit(main())
