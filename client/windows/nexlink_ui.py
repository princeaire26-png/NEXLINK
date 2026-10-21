"""NEXLINK Command Center UI and remote session viewer."""
from __future__ import annotations
import asyncio, base64, json, threading, time

import httpx
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QTableWidget,
    QTableWidgetItem, QMessageBox, QInputDialog, QTextEdit, QSplitter, QGroupBox, QFileDialog,
    QFormLayout, QDialog, QSpinBox, QComboBox
)
from nexlink_agent.urls import http_base, websocket_base as ws_base


class ApiClient:
    def __init__(self, base: str): self.base=http_base(base); self.token=''
    def headers(self): return {'Authorization': f'Bearer {self.token}'} if self.token else {}
    def request(self, method, path, **kwargs):
        return httpx.request(method, self.base+path, headers={**self.headers(), **kwargs.pop('headers', {})}, timeout=20, **kwargs)
    def login(self, email, password, mfa_code=None):
        payload={'email':email,'password':password}
        if mfa_code: payload['mfa_code']=mfa_code
        r=self.request('POST','/api/v1/auth/login',json=payload); r.raise_for_status(); data=r.json(); self.token=data['access_token']; return data


class RemoteConnection(QObject):
    frame = pyqtSignal(bytes, int, int)
    event = pyqtSignal(dict)
    failed = pyqtSignal(str)
    closed = pyqtSignal()
    def __init__(self, url, token, session_id):
        super().__init__(); self.url=url; self.token=token; self.session_id=session_id; self.loop=None; self.ws=None; self.thread=None
    def start(self):
        self.thread=threading.Thread(target=lambda: asyncio.run(self._run()), daemon=True); self.thread.start()
    async def _run(self):
        import websockets
        self.loop=asyncio.get_running_loop()
        try:
            async with websockets.connect(self.url, max_size=16*1024*1024, ping_interval=20) as ws:
                self.ws=ws
                await ws.send(json.dumps({'type':'authenticate','access_token':self.token}))
                while True:
                    raw=await ws.recv()
                    msg=json.loads(raw)
                    typ=msg.get('type')
                    if typ=='screen_frame':
                        payload=msg.get('payload') or {}
                        if payload.get('jpeg_b64'):
                            data=base64.b64decode(payload['jpeg_b64'])
                            self.frame.emit(data, int(payload.get('width',0)), int(payload.get('height',0)))
                        elif payload.get('error'): self.failed.emit(payload['error'])
                    else: self.event.emit(msg)
        except Exception as exc: self.failed.emit(str(exc))
        finally: self.closed.emit()
    def send(self, message):
        if self.loop and self.ws:
            asyncio.run_coroutine_threadsafe(self.ws.send(json.dumps(message)), self.loop)
    def stop(self):
        self.send({'type':'session_end'})


class RemoteScreenLabel(QLabel):
    input_event = pyqtSignal(dict)
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.input_event.emit({"kind":"click","x":int(event.position().x()),"y":int(event.position().y()),"button":"left"})
        super().mousePressEvent(event)


class RemoteViewer(QDialog):
    def __init__(self, api: ApiClient, session_id: str, device_name: str, parent=None):
        super().__init__(parent); self.setWindowTitle(f'NEXLINK Remote — {device_name}'); self.resize(1200,800); self.api=api; self.session_id=session_id
        self.channel=RemoteConnection(ws_base(api.base).replace('/ws','')+f'/ws/control/{session_id}', api.token, session_id)
        root=QVBoxLayout(self)
        top=QHBoxLayout(); self.state=QLabel('CONNECTING'); self.fps=QLabel('Adaptive stream'); top.addWidget(self.state); top.addStretch(); top.addWidget(self.fps); root.addLayout(top)
        self.screen=RemoteScreenLabel(); self.screen.setText('Waiting for remote screen…'); self.screen.setAlignment(Qt.AlignmentFlag.AlignCenter); self.screen.input_event.connect(lambda payload:self.channel.send({'type':'input_event','payload':payload})); self.screen.setFocusPolicy(Qt.FocusPolicy.StrongFocus); self.screen.setStyleSheet('background:#0b1220;color:#cbd5e1;')
        root.addWidget(self.screen,1)
        controls=QHBoxLayout(); end=QPushButton('End Session'); end.clicked.connect(self.close); controls.addWidget(end); download=QPushButton('Download File'); download.clicked.connect(self.download_file); controls.addWidget(download); controls.addWidget(QLabel('Remote control is authorized for this session.')); root.addLayout(controls); self.pending_download=None
        self.channel.frame.connect(self.on_frame); self.channel.event.connect(self.on_event); self.channel.failed.connect(lambda x:self.state.setText('ERROR: '+x)); self.channel.closed.connect(lambda:self.state.setText('CLOSED'))
        self.channel.start(); self.screen.setFocus()
    def on_frame(self, data, width, height):
        image=QImage.fromData(data, 'JPG');
        if not image.isNull(): self.screen.setPixmap(QPixmap.fromImage(image).scaled(self.screen.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)); self.state.setText(f'LIVE • {width}×{height}')
    def on_event(self, msg):
        if msg.get('type')=='session_state': self.state.setText(msg.get('state','LIVE').upper())
        elif msg.get('type')=='file_transfer_data':
            payload=msg.get('payload') or {}
            if payload.get('direction')=='download' and payload.get('data_b64') and self.pending_download:
                try:
                    with open(self.pending_download,'wb') as handle: handle.write(base64.b64decode(payload['data_b64']))
                    self.state.setText(f"Downloaded {payload.get('size',0)} bytes")
                except Exception as exc: QMessageBox.critical(self,'File Transfer',str(exc))
                finally: self.pending_download=None
    def download_file(self):
        remote,ok=QInputDialog.getText(self,'Download File','Remote path:')
        if not ok or not remote:return
        local,_=QFileDialog.getSaveFileName(self,'Save Remote File')
        if not local:return
        self.pending_download=local
        self.channel.send({'type':'file_transfer_request','payload':{'direction':'download','path':remote}})
    def keyPressEvent(self, event):
        text=event.text()
        if text and text.isprintable(): self.channel.send({'type':'input_event','payload':{'kind':'type','text':text}})
        super().keyPressEvent(event)
    def closeEvent(self,event):
        self.channel.stop(); event.accept()


class DashboardTab(QWidget):
    def __init__(self, api, parent=None):
        super().__init__(parent); self.api=api
        root=QVBoxLayout(self); cards=QHBoxLayout(); self.card_labels={}
        for name in ['DEVICES','ONLINE','ALERTS','AI ACTIONS']:
            box=QGroupBox(name); v=QVBoxLayout(box); label=QLabel('—'); label.setStyleSheet('font-size:26px;font-weight:bold;'); v.addWidget(label); cards.addWidget(box); self.card_labels[name]=label
        root.addLayout(cards); self.summary=QTextEdit(); self.summary.setReadOnly(True); root.addWidget(self.summary)
        refresh=QPushButton('Refresh Command Center'); refresh.clicked.connect(self.refresh); root.addWidget(refresh); self.refresh()
    def refresh(self):
        try:
            d=self.api.request('GET','/api/v1/platform/summary').json(); stats=d['devices']; self.card_labels['DEVICES'].setText(str(stats['total'])); self.card_labels['ONLINE'].setText(str(stats['online'])); self.card_labels['ALERTS'].setText(str(d['open_alerts'])); self.card_labels['AI ACTIONS'].setText(str(d['pending_ai_actions'])); self.summary.setPlainText(json.dumps(d,indent=2))
        except Exception as exc: self.summary.setPlainText(str(exc))


class DevicesTab(QWidget):
    def __init__(self, api, parent=None):
        super().__init__(parent); self.api=api; self.rows=[]
        root=QVBoxLayout(self); bar=QHBoxLayout(); refresh=QPushButton('Refresh'); refresh.clicked.connect(self.refresh); bar.addWidget(refresh); root.addLayout(bar)
        self.table=QTableWidget(0,7); self.table.setHorizontalHeaderLabels(['Name','Status','OS','Agent','Approved','Device ID','Remote']); root.addWidget(self.table); self.refresh()
    def refresh(self):
        try:
            data=self.api.request('GET','/api/v1/devices/').json(); self.rows=data['devices']; self.table.setRowCount(len(self.rows))
            for r,d in enumerate(self.rows):
                vals=[d['name'],d['status'],d['os_type'],d.get('agent_version',''),str(d['approved']),d['device_id'],'']
                for c,v in enumerate(vals[:6]): self.table.setItem(r,c,QTableWidgetItem(str(v)))
                b=QPushButton('Connect' if d['status']=='online' else 'Offline'); b.setEnabled(d['status']=='online'); b.clicked.connect(lambda _,x=d:self.connect(x)); self.table.setCellWidget(r,6,b)
        except Exception as exc: QMessageBox.critical(self,'Devices',str(exc))
    def connect(self,d):
        try:
            r=self.api.request('POST','/api/v1/remote/sessions',json={'device_id':d['id']}); r.raise_for_status(); sid=r.json()['session_id']; viewer=RemoteViewer(self.api,str(sid),d['name'],self); viewer.exec(); self.refresh()
        except Exception as exc: QMessageBox.critical(self,'Remote Access',str(exc))


class AlertsTab(QWidget):
    def __init__(self,api,parent=None):
        super().__init__(parent); self.api=api; root=QVBoxLayout(self); self.table=QTableWidget(0,5); self.table.setHorizontalHeaderLabels(['Device','Severity','Category','Title','State']); root.addWidget(self.table); b=QPushButton('Refresh Alerts'); b.clicked.connect(self.refresh); root.addWidget(b); self.refresh()
    def refresh(self):
        try:
            devices=self.api.request('GET','/api/v1/devices/').json()['devices']; rows=[]
            for d in devices: rows += [(d['name'],a) for a in self.api.request('GET',f"/api/v1/platform/devices/{d['id']}/alerts").json()['alerts']]
            self.table.setRowCount(len(rows))
            for r,(name,a) in enumerate(rows):
                for c,v in enumerate([name,a['severity'],a['category'],a['title'],a['state']]): self.table.setItem(r,c,QTableWidgetItem(str(v)))
        except Exception as exc: QMessageBox.critical(self,'Alerts',str(exc))


class NetworkTab(QWidget):
    def __init__(self,api,parent=None):
        super().__init__(parent); self.api=api; root=QVBoxLayout(self); self.devices=QComboBox(); root.addWidget(self.devices); self.action=QComboBox(); self.action.addItems(['status','block_all','unblock_all','block_domains']); root.addWidget(self.action); self.domains=QLineEdit(); self.domains.setPlaceholderText('example.com, social.example'); root.addWidget(self.domains); b=QPushButton('Apply Network Guard'); b.clicked.connect(self.apply); root.addWidget(b); self.output=QTextEdit(); self.output.setReadOnly(True); root.addWidget(self.output); self.refresh()
    def refresh(self):
        self.devices.clear()
        try:
            for d in self.api.request('GET','/api/v1/devices/').json()['devices']: self.devices.addItem(f"{d['name']} — {d['status']}",d['id'])
        except Exception as exc:self.output.setPlainText(str(exc))
    def apply(self):
        did=self.devices.currentData();
        if not did:return
        payload={'action':self.action.currentText(),'domains':[x.strip() for x in self.domains.text().split(',') if x.strip()]}
        try:
            r=self.api.request('POST',f'/api/v1/devices/{did}/network-guard',json=payload); r.raise_for_status(); self.output.setPlainText(json.dumps(r.json(),indent=2))
        except Exception as exc:self.output.setPlainText(str(exc))


class AITab(QWidget):
    def __init__(self,api,parent=None):
        super().__init__(parent); self.api=api; root=QVBoxLayout(self); self.devices=QComboBox(); root.addWidget(self.devices); self.intent=QLineEdit(); self.intent.setPlaceholderText('Why is this computer slow?'); root.addWidget(self.intent); plan=QPushButton('Analyze / Plan'); plan.clicked.connect(self.plan); root.addWidget(plan); self.output=QTextEdit(); root.addWidget(self.output); self.refresh()
    def refresh(self):
        self.devices.clear()
        try:
            for d in self.api.request('GET','/api/v1/devices/').json()['devices']: self.devices.addItem(d['name'],d['id'])
        except Exception: pass
    def plan(self):
        try:
            r=self.api.request('POST','/api/v1/platform/ai/plan',json={'device_id':self.devices.currentData(),'intent':self.intent.text()}); r.raise_for_status(); self.output.setPlainText(json.dumps(r.json(),indent=2))
        except Exception as exc:self.output.setPlainText(str(exc))


class SecurityTab(QWidget):
    def __init__(self,api,parent=None):
        super().__init__(parent); self.api=api; root=QVBoxLayout(self); self.output=QTextEdit(); self.output.setReadOnly(True); root.addWidget(self.output); b=QPushButton('Load Policies / Relay / Audit'); b.clicked.connect(self.refresh); root.addWidget(b); self.refresh()
    def refresh(self):
        try:
            data={'policies':self.api.request('GET','/api/v1/platform/policies').json(),'relay':self.api.request('GET','/api/v1/platform/relay').json(),'audit':self.api.request('GET','/api/v1/audit/').json()}; self.output.setPlainText(json.dumps(data,indent=2,default=str))
        except Exception as exc:self.output.setPlainText(str(exc))


class AutomationTab(QWidget):
    def __init__(self,api,parent=None):
        super().__init__(parent); self.api=api; root=QVBoxLayout(self); self.name=QLineEdit(); self.name.setPlaceholderText('Disk protection'); root.addWidget(self.name); self.trigger=QLineEdit('{"event":"metrics","condition":{"field":"disk_percent","operator":"gte","value":90}}'); root.addWidget(self.trigger); self.actions=QLineEdit('[{"type":"create_alert"}]'); root.addWidget(self.actions); b=QPushButton('Create Automation'); b.clicked.connect(self.create); root.addWidget(b); self.output=QTextEdit(); root.addWidget(self.output)
    def create(self):
        try:
            payload={'name':self.name.text(),'description':'Created from NEXLINK Command Center','trigger_config':json.loads(self.trigger.text()),'actions':json.loads(self.actions.text()),'enabled':True}; r=self.api.request('POST','/api/v1/platform/automations',json=payload); r.raise_for_status(); self.output.setPlainText(json.dumps(r.json(),indent=2))
        except Exception as exc:self.output.setPlainText(str(exc))


class SupportTab(QWidget):
    def __init__(self, api, parent=None):
        super().__init__(parent); self.api=api; root=QVBoxLayout(self)
        self.devices=QComboBox(); root.addWidget(self.devices)
        self.title=QLineEdit(); self.title.setPlaceholderText('Printer not working')
        self.description=QTextEdit(); self.description.setPlaceholderText('Describe the issue…')
        self.priority=QComboBox(); self.priority.addItems(['low','normal','high','urgent'])
        root.addWidget(self.title); root.addWidget(self.description); root.addWidget(self.priority)
        b=QPushButton('Create Support Request'); b.clicked.connect(self.create); root.addWidget(b)
        self.output=QTextEdit(); self.output.setReadOnly(True); root.addWidget(self.output)
        self.refresh()
    def refresh(self):
        self.devices.clear()
        try:
            for d in self.api.request('GET','/api/v1/devices/').json()['devices']: self.devices.addItem(d['name'],d['id'])
        except Exception: pass
    def create(self):
        try:
            payload={'device_id':self.devices.currentData(),'title':self.title.text(),'description':self.description.toPlainText(),'priority':self.priority.currentText()}
            r=self.api.request('POST','/api/v1/platform/support',json=payload); r.raise_for_status(); self.output.setPlainText(json.dumps(r.json(),indent=2))
        except Exception as exc:self.output.setPlainText(str(exc))
