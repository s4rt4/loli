import sys
import os
import subprocess
import re
import webbrowser
import psutil 
import glob
import tempfile
import shlex
import logging
from typing import Optional

os.environ["QT_API"] = "pyqt6"

try:
    import qtawesome as qta
    HAS_ICONS = True
except ImportError:
    HAS_ICONS = False

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QFrame, QMessageBox, 
                             QStackedWidget, QTextEdit, QLineEdit, QFileDialog, QComboBox,
                             QProgressBar, QGridLayout, QCheckBox, QSystemTrayIcon, QMenu, 
                             QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import QTimer, Qt, QSize
from PyQt6.QtGui import QFont, QIcon, QAction, QColor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

STYLESHEET = """
QMainWindow { background-color: #f4f6f9; }
QWidget { color: #2c3e50; }
QWidget#Sidebar { background-color: #2c3e50; color: white; }
QWidget#Sidebar QLabel { color: white; }
QPushButton#MenuBtn { text-align: left; padding: 12px 20px; background-color: transparent; border: none; color: #bdc3c7; font-size: 14px; border-radius: 0px; }
QPushButton#MenuBtn:hover { background-color: #34495e; color: white; }
QPushButton#MenuBtn:checked { background-color: #3498db; color: white; font-weight: bold; border-left: 4px solid white; }
QFrame#Card { background-color: white; border-radius: 10px; border: 1px solid #dcdde1; }
QLabel#H1 { font-size: 18px; font-weight: bold; color: #2c3e50; margin-bottom: 15px; }
QLineEdit, QComboBox { background-color: white; color: #2c3e50; border: 1px solid #bdc3c7; padding: 6px; border-radius: 4px; }
QComboBox::drop-down { border: none; }
QCheckBox { color: #2c3e50; }
QTextEdit { background-color: #2c3e50; color: #ecf0f1; border-radius: 5px; padding: 10px; font-family: monospace; }
QPushButton { padding: 8px 15px; border-radius: 5px; font-size: 13px; font-weight: 600; border: 1px solid #bdc3c7; background-color: #ecf0f1; color: #2c3e50; }
QPushButton:hover { background-color: #dfe6e9; }
QPushButton#BtnPrimary { background-color: #3498db; color: white; border: 1px solid #2980b9; }
QPushButton#BtnPrimary:hover { background-color: #2980b9; }
QPushButton#BtnSuccess { background-color: #2ecc71; color: white; border: 1px solid #27ae60; }
QPushButton#BtnSuccess:hover { background-color: #27ae60; }
QPushButton#BtnDanger { background-color: #e74c3c; color: white; border: 1px solid #c0392b; }
QPushButton#BtnDanger:hover { background-color: #c0392b; }
QPushButton#BtnBig { background-color: white; border: 2px solid #3498db; color: #3498db; font-size: 14px; font-weight: bold; padding: 12px; border-radius: 8px; }
QPushButton#BtnBig:hover { background-color: #3498db; color: white; }
QPushButton#BtnQuit { background-color: white; border: 2px solid #e74c3c; color: #e74c3c; font-size: 14px; font-weight: bold; padding: 12px; border-radius: 8px; }
QPushButton#BtnQuit:hover { background-color: #e74c3c; color: white; }
QLabel#StatusRun { color: #27ae60; font-weight: bold; font-size: 13px; background-color: transparent; border: none; }
QLabel#StatusStop { color: #e74c3c; font-weight: bold; font-size: 13px; background-color: transparent; border: none; }
QLabel#StatusNA { color: #95a5a6; font-weight: bold; font-size: 13px; background-color: transparent; border: none; }
QProgressBar#SideBar { background-color: #1a252f; border: none; border-radius: 4px; color: white; text-align: center; font-size: 10px; font-weight: bold; }
QTableWidget { background-color: white; color: #2c3e50; border: 1px solid #bdc3c7; border-radius: 5px; gridline-color: #ecf0f1; }
QHeaderView::section { background-color: #ecf0f1; color: #2c3e50; font-weight: bold; padding: 5px; border: 1px solid #bdc3c7; }
"""

def validate_domain(domain: str) -> bool:
    if not domain or len(domain) > 253:
        return False
    pattern = r'^(?!-)[a-zA-Z0-9-]{1,63}(?<!-)(\.[a-zA-Z0-9-]{1,63})*$'
    return bool(re.match(pattern, domain))

def validate_path(path: str) -> bool:
    if not path:
        return False
    return os.path.isabs(path) and not '..' in path

def validate_port(port: str) -> bool:
    try:
        p = int(port)
        return 1 <= p <= 65535
    except (ValueError, TypeError):
        return False

def validate_username(username: str) -> bool:
    if not username or len(username) > 32:
        return False
    pattern = r'^[a-z_][a-z0-9_-]*\$?$'
    return bool(re.match(pattern, username))

def run_root_script(script_content: str) -> bool:
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write("#!/bin/bash\n" + script_content)
            temp_path = f.name
        
        os.chmod(temp_path, 0o755)
        result = subprocess.run(["pkexec", temp_path], check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Root script failed: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error in run_root_script: {e}")
        return False
    finally:
        try:
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception as e:
            logging.warning(f"Failed to cleanup temp file: {e}")

class Card(QFrame):
    def __init__(self, layout_type="v"):
        super().__init__()
        self.setObjectName("Card")
        self.layout = QVBoxLayout() if layout_type == "v" else QHBoxLayout()
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(10)
        self.setLayout(self.layout)

class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        card_tools = Card()
        grid_tools = QGridLayout()
        grid_tools.setSpacing(10)
        
        btn_local = QPushButton(" Open Localhost")
        btn_local.setObjectName("BtnBig")
        if HAS_ICONS: btn_local.setIcon(qta.icon("fa5s.globe", color="#3498db"))
        btn_local.clicked.connect(lambda: webbrowser.open("http://localhost"))
        
        btn_pma = QPushButton(" Open PHPMyAdmin")
        btn_pma.setObjectName("BtnBig")
        if HAS_ICONS: btn_pma.setIcon(qta.icon("fa5s.database", color="#3498db"))
        btn_pma.clicked.connect(lambda: webbrowser.open("http://localhost/phpmyadmin"))
        
        btn_root = QPushButton(" Open Root Directory")
        btn_root.setObjectName("BtnBig")
        if HAS_ICONS: btn_root.setIcon(qta.icon("fa5s.folder-open", color="#3498db"))
        btn_root.clicked.connect(self.open_root_dir)
        
        btn_quit = QPushButton(" Force Quit App")
        btn_quit.setObjectName("BtnQuit")
        if HAS_ICONS: btn_quit.setIcon(qta.icon("fa5s.power-off", color="#e74c3c"))
        btn_quit.clicked.connect(lambda: self.window().force_quit())

        grid_tools.addWidget(btn_local, 0, 0)
        grid_tools.addWidget(btn_pma, 0, 1)
        grid_tools.addWidget(btn_root, 1, 0)
        grid_tools.addWidget(btn_quit, 1, 1)
        
        card_tools.layout.addLayout(grid_tools)
        layout.addWidget(card_tools)

        card_svc = Card()
        card_svc.layout.addWidget(QLabel("Service Status", objectName="H1"))
        
        self.services = [
            ("apache2", "Apache Web Server", "fa5s.server"), 
            ("nginx", "Nginx Web Server", "fa5s.server"),
            ("mariadb", "MariaDB Database", "fa5s.database"),
            ("postgresql", "PostgreSQL", "fa5s.database"),
            ("mongod", "MongoDB", "fa5s.database")
        ]
        
        self.svc_widgets = {}

        for sys_name, display_name, icon_name in self.services:
            row = QHBoxLayout()
            lbl_icon = QLabel()
            if HAS_ICONS: lbl_icon.setPixmap(qta.icon(icon_name, color="#34495e").pixmap(24, 24))
            row.addWidget(lbl_icon)
            
            lbl_name = QLabel(display_name)
            lbl_name.setStyleSheet("font-weight: bold; font-size: 14px; color: #2c3e50;")
            lbl_name.setFixedWidth(150)
            row.addWidget(lbl_name)

            lbl_status = QLabel("Checking...")
            lbl_status.setFixedWidth(110)
            lbl_status.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(lbl_status)
            row.addStretch()

            action_stack = QStackedWidget()
            action_stack.setFixedWidth(90)
            
            btn_start = QPushButton(" Start")
            btn_start.setObjectName("BtnSuccess")
            if HAS_ICONS: btn_start.setIcon(qta.icon("fa5s.play", color="white"))
            btn_start.clicked.connect(lambda checked, s=sys_name: self.run_cmd(s, "start"))
            
            btn_stop = QPushButton(" Stop")
            btn_stop.setObjectName("BtnDanger")
            if HAS_ICONS: btn_stop.setIcon(qta.icon("fa5s.stop", color="white"))
            btn_stop.clicked.connect(lambda checked, s=sys_name: self.run_cmd(s, "stop"))
            
            action_stack.addWidget(btn_start)
            action_stack.addWidget(btn_stop)

            btn_restart = QPushButton(" Restart")
            btn_restart.setObjectName("BtnPrimary")
            btn_restart.setFixedWidth(90)
            if HAS_ICONS: btn_restart.setIcon(qta.icon("fa5s.sync", color="white"))
            btn_restart.clicked.connect(lambda checked, s=sys_name: self.run_cmd(s, "restart"))

            row.addWidget(action_stack)
            row.addWidget(btn_restart)
            card_svc.layout.addLayout(row)
            
            self.svc_widgets[sys_name] = {
                'status': lbl_status, 'action_stack': action_stack, 'btn_restart': btn_restart
            }
            
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setStyleSheet("color: #ecf0f1;")
            card_svc.layout.addWidget(line)

        layout.addWidget(card_svc)

        card_console = Card()
        card_console.layout.addWidget(QLabel("Terminal Logs (Execution Feedback)", objectName="H1"))
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background-color: #1e1e1e; color: #00ff00; font-family: Consolas, monospace; font-size: 13px; padding: 10px; border-radius: 5px;")
        self.console.setFixedHeight(140) 
        self.console.setPlaceholderText("Ready. Menunggu eksekusi sistem...")
        card_console.layout.addWidget(self.console)
        layout.addWidget(card_console)

        self.setLayout(layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(2000)
        self.update_ui()

    def open_root_dir(self):
        path = "/var/www/html"
        try:
            out = subprocess.getoutput("grep -m 1 'DocumentRoot' /etc/apache2/sites-available/000-default.conf")
            if "DocumentRoot" in out: path = out.split()[-1].strip()
        except Exception as e:
            logging.warning(f"Failed to get document root: {e}")
        subprocess.run(["xdg-open", path])

    def update_ui(self):
        for sys_name, _, _ in self.services:
            widgets = self.svc_widgets[sys_name]
            lbl = widgets['status']
            action_stack = widgets['action_stack']
            btn_restart = widgets['btn_restart']

            is_exist = subprocess.run(["systemctl", "list-unit-files", f"{sys_name}.service"], capture_output=True).returncode == 0
            
            if not is_exist:
                lbl.setText("○ NOT INSTALLED")
                lbl.setObjectName("StatusNA")
                action_stack.hide()
                btn_restart.hide()
            else:
                action_stack.show()
                running = subprocess.run(["systemctl", "is-active", "--quiet", sys_name]).returncode == 0
                if running:
                    lbl.setText("● RUNNING")
                    lbl.setObjectName("StatusRun")
                    action_stack.setCurrentIndex(1)
                    btn_restart.show()
                else:
                    lbl.setText("● STOPPED")
                    lbl.setObjectName("StatusStop")
                    action_stack.setCurrentIndex(0)
                    btn_restart.hide()
            
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)

    def run_cmd(self, svc: str, action: str):
        if action == "start":
            if svc == "apache2" and self.check_svc("nginx"):
                self.console.append("\n[WARNING] Matikan Nginx terlebih dahulu untuk mencegah konflik Port 80!")
                QMessageBox.warning(self, "Conflict", "Nginx sedang berjalan! Harap matikan Nginx sebelum menyalakan Apache.")
                return
            if svc == "nginx" and self.check_svc("apache2"):
                self.console.append("\n[WARNING] Matikan Apache terlebih dahulu untuk mencegah konflik Port 80!")
                QMessageBox.warning(self, "Conflict", "Apache sedang berjalan! Harap matikan Apache sebelum menyalakan Nginx.")
                return

        self.console.append(f"\n> systemctl {action} {svc}...")
        QApplication.processEvents()

        try:
            res = subprocess.run(["pkexec", "systemctl", action, svc], capture_output=True, text=True, timeout=30)
            if res.returncode == 0:
                self.console.append(f"[SUCCESS] {svc} berhasil di-{action}.")
            else:
                self.console.append(f"[ERROR] systemctl gagal (Code {res.returncode})")
                log_res = subprocess.run(["journalctl", "-u", svc, "-n", "15", "--no-pager"], capture_output=True, text=True, timeout=10)
                if log_res.stdout:
                    self.console.append("--- [LOG DETAIL] ---")
                    self.console.append(log_res.stdout.strip())
                    self.console.append("--------------------")
        except subprocess.TimeoutExpired:
            self.console.append(f"[TIMEOUT] Operasi {action} memakan waktu terlalu lama")
        except Exception as e:
            self.console.append(f"[EXCEPTION] {str(e)}")
            logging.error(f"Error in run_cmd: {e}")

        self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())
        QTimer.singleShot(500, self.update_ui)

    def check_svc(self, svc: str) -> bool:
        return subprocess.run(["systemctl", "is-active", "--quiet", svc]).returncode == 0

class SniperPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.setContentsMargins(20,20,20,20)
        card = Card()
        lbl_title = QLabel("Port Sniper (Process Killer)", objectName="H1")
        lbl_desc = QLabel("Cari aplikasi yang membajak port jaringan Anda dan hentikan secara paksa (Kill).")
        lbl_desc.setStyleSheet("color: #7f8c8d; margin-bottom: 10px;")
        card.layout.addWidget(lbl_title)
        card.layout.addWidget(lbl_desc)
        self.btn_scan = QPushButton(" Scan Port Aktif (Membutuhkan akses Root)")
        self.btn_scan.setObjectName("BtnPrimary")
        if HAS_ICONS: self.btn_scan.setIcon(qta.icon("fa5s.search", color="white"))
        self.btn_scan.setFixedHeight(40)
        self.btn_scan.clicked.connect(self.scan_ports)
        card.layout.addWidget(self.btn_scan)
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Protocol", "Port", "Nama Aplikasi", "PID", "Action"])
        self.table.verticalHeader().setDefaultSectionSize(45)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) 
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents) 
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)          
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) 
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents) 
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers) 
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        card.layout.addWidget(self.table)
        layout.addWidget(card)
        self.setLayout(layout)

    def scan_ports(self):
        self.table.setRowCount(0) 
        try:
            out = subprocess.check_output(["pkexec", "ss", "-tulnp"], text=True, timeout=30)
            self.parse_and_populate(out)
        except subprocess.CalledProcessError:
            QMessageBox.critical(self, "Batal", "Gagal memindai port. Autentikasi dibatalkan.")
        except subprocess.TimeoutExpired:
            QMessageBox.critical(self, "Timeout", "Pemindaian port memakan waktu terlalu lama.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Terjadi kesalahan: {str(e)}")
            logging.error(f"Error in scan_ports: {e}")

    def parse_and_populate(self, ss_output: str):
        lines = ss_output.strip().split('\n')
        if len(lines) <= 1: return 
        row_idx = 0
        for line in lines[1:]:
            parts = line.split()
            if len(parts) < 6: continue 
            netid = parts[0] 
            if netid not in ['tcp', 'udp', 'tcp6', 'udp6']: continue
            local_addr = parts[4]
            port = local_addr.split(':')[-1] 
            process_raw = parts[-1] if 'users:' in parts[-1] else ""
            app_name = "System/Unknown"
            pid = "-"
            if process_raw:
                match_name = re.search(r'"([^"]+)"', process_raw)
                match_pid = re.search(r'pid=(\d+)', process_raw)
                if match_name: app_name = match_name.group(1)
                if match_pid: pid = match_pid.group(1)
            if pid == "-": continue
            self.table.insertRow(row_idx)
            item_netid = QTableWidgetItem(netid.upper())
            item_netid.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self.table.setItem(row_idx, 0, item_netid)
            item_port = QTableWidgetItem(port)
            item_port.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold)) 
            item_port.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self.table.setItem(row_idx, 1, item_port)
            item_app = QTableWidgetItem(app_name)
            item_app.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self.table.setItem(row_idx, 2, item_app)
            item_pid = QTableWidgetItem(pid)
            item_pid.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self.table.setItem(row_idx, 3, item_pid)
            btn_kill = QPushButton("KILL")
            btn_kill.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; border-radius: 4px; padding: 6px 12px;")
            btn_kill.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_kill.clicked.connect(lambda checked, p=pid, n=app_name: self.kill_process(p, n))
            cell_widget = QWidget()
            cell_layout = QHBoxLayout(cell_widget)
            cell_layout.setContentsMargins(8, 4, 8, 4)
            cell_layout.addWidget(btn_kill)
            self.table.setCellWidget(row_idx, 4, cell_widget)
            row_idx += 1

    def kill_process(self, pid: str, app_name: str):
        reply = QMessageBox.warning(self, "Tembak Target?", 
                                    f"Yakin ingin menghentikan paksa aplikasi '{app_name}' (PID: {pid})?\n\n"
                                    "Peringatan: OS bisa tidak stabil jika ini adalah proses sistem penting.",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                subprocess.run(["pkexec", "kill", "-9", str(pid)], check=True, timeout=10)
                QMessageBox.information(self, "Target Down", f"Proses {app_name} berhasil dihentikan!")
                self.scan_ports()
            except subprocess.CalledProcessError:
                QMessageBox.critical(self, "Gagal", "Gagal menghentikan proses.")
            except subprocess.TimeoutExpired:
                QMessageBox.critical(self, "Timeout", "Operasi kill memakan waktu terlalu lama.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Terjadi kesalahan: {str(e)}")
                logging.error(f"Error in kill_process: {e}")

class PrefsPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.setContentsMargins(20,20,20,20)
        card_gen = Card()
        card_gen.layout.addWidget(QLabel("General, Ports & Directories", objectName="H1"))
        grid = QGridLayout()
        self.inp_dir = QLineEdit()
        btn_browse = QPushButton("...")
        btn_browse.clicked.connect(self.browse_dir)
        grid.addWidget(QLabel("Document Root:"), 0, 0)
        grid.addWidget(self.inp_dir, 0, 1)
        grid.addWidget(btn_browse, 0, 2)
        self.ports = { "apache2": QLineEdit(), "nginx": QLineEdit(), "mariadb": QLineEdit(), "postgresql": QLineEdit(), "mongod": QLineEdit() }
        grid.addWidget(QLabel("Apache Port:"), 1, 0)
        grid.addWidget(self.ports["apache2"], 1, 1, 1, 2)
        grid.addWidget(QLabel("Nginx Port:"), 2, 0)
        grid.addWidget(self.ports["nginx"], 2, 1, 1, 2)
        grid.addWidget(QLabel("MariaDB Port:"), 3, 0)
        grid.addWidget(self.ports["mariadb"], 3, 1, 1, 2)
        grid.addWidget(QLabel("PostgreSQL Port:"), 4, 0)
        grid.addWidget(self.ports["postgresql"], 4, 1, 1, 2)
        grid.addWidget(QLabel("MongoDB Port:"), 5, 0)
        grid.addWidget(self.ports["mongod"], 5, 1, 1, 2)
        card_gen.layout.addLayout(grid)
        btn_save = QPushButton("Save Configs & Restart Services")
        btn_save.setObjectName("BtnPrimary")
        btn_save.clicked.connect(self.save_prefs)
        card_gen.layout.addWidget(btn_save)
        layout.addWidget(card_gen)

        card_feat = Card()
        card_feat.layout.addWidget(QLabel("Advanced Features (SSL & Mail Catcher)", objectName="H1"))
        h_feat = QHBoxLayout()
        btn_ssl = QPushButton(" Enable Local SSL (HTTPS)")
        btn_ssl.setObjectName("BtnSuccess")
        if HAS_ICONS: btn_ssl.setIcon(qta.icon("fa5s.lock", color="white"))
        btn_ssl.clicked.connect(self.enable_ssl)
        btn_mail = QPushButton(" Setup Mail Catcher")
        btn_mail.setObjectName("BtnPrimary")
        if HAS_ICONS: btn_mail.setIcon(qta.icon("fa5s.envelope", color="white"))
        btn_mail.clicked.connect(self.setup_mailcatcher)
        h_feat.addWidget(btn_ssl)
        h_feat.addWidget(btn_mail)
        card_feat.layout.addLayout(h_feat)
        self.mail_viewer = QTextEdit()
        self.mail_viewer.setReadOnly(True)
        self.mail_viewer.setPlaceholderText("Email lokal yang dikirim via PHP mail() akan muncul di sini...\n(Klik Refresh untuk melihat)")
        card_feat.layout.addWidget(self.mail_viewer)
        btn_refresh_mail = QPushButton(" Refresh Inbox")
        btn_refresh_mail.clicked.connect(self.read_mails)
        card_feat.layout.addWidget(btn_refresh_mail)
        layout.addWidget(card_feat)
        self.setLayout(layout)
        self.load_current_settings()

    def load_current_settings(self):
        try:
            out = subprocess.getoutput("grep -m 1 'DocumentRoot' /etc/apache2/sites-available/000-default.conf")
            if "DocumentRoot" in out: self.inp_dir.setText(out.split()[-1].strip())
        except Exception as e:
            logging.warning(f"Failed to load document root: {e}")

        try:
            if "Listen" in (ap := subprocess.getoutput("grep -m 1 '^Listen' /etc/apache2/ports.conf")): self.ports["apache2"].setText(ap.split()[-1].strip())
            if "listen" in (ng := subprocess.getoutput("grep -m 1 'listen' /etc/nginx/sites-available/default")): self.ports["nginx"].setText(ng.replace('listen','').replace(';','').strip().split()[0])
            if "port" in (ma := subprocess.getoutput("grep -m 1 '^port' /etc/mysql/mariadb.conf.d/50-server.cnf")): self.ports["mariadb"].setText(ma.split('=')[-1].strip())
            if "port" in (pg := subprocess.getoutput("grep -m 1 '^port' /etc/postgresql/*/main/postgresql.conf")): self.ports["postgresql"].setText(pg.split('=')[-1].strip())
            if "port" in (mg := subprocess.getoutput("grep -m 1 '^  port:' /etc/mongod.conf")): self.ports["mongod"].setText(mg.split(':')[-1].strip())
        except Exception as e:
            logging.warning(f"Failed to load port settings: {e}")

    def browse_dir(self):
        if d := QFileDialog.getExistingDirectory(self): self.inp_dir.setText(d)

    def save_prefs(self):
        ndir = self.inp_dir.text()
        
        if ndir and not validate_path(ndir):
            QMessageBox.critical(self, "Error", "Path tidak valid!")
            return
            
        for svc, inp in self.ports.items():
            port = inp.text()
            if port and not validate_port(port):
                QMessageBox.critical(self, "Error", f"Port {svc} tidak valid! Harus 1-65535")
                return
        
        s = ""
        php_ver = subprocess.getoutput("php -r \"echo PHP_MAJOR_VERSION.'.'.PHP_MINOR_VERSION;\" 2>/dev/null")
        if not re.match(r"^\d+\.\d+$", php_ver): php_ver = "8.2"

        if ndir:
            ndir_escaped = shlex.quote(ndir)
            s += f"sed -i 's|DocumentRoot .*|DocumentRoot {ndir_escaped}|g' /etc/apache2/sites-available/000-default.conf\n"
            s += f"cat << 'EOF' > /etc/apache2/conf-available/custom-panel-dir.conf\n<Directory {ndir_escaped}>\n    Options Indexes FollowSymLinks\n    AllowOverride All\n    Require all granted\n</Directory>\nEOF\n"
            s += "a2enconf custom-panel-dir || true\n"
            p_ng = self.ports["nginx"].text()
            if p_ng and validate_port(p_ng):
                s += f"if [ -d /etc/nginx/sites-available ]; then\ncat << 'EOF' > /etc/nginx/sites-available/default\nserver {{\n    listen {p_ng} default_server;\n    root {ndir_escaped};\n    index index.php index.html index.htm;\n    server_name _;\n    location / {{ try_files $uri $uri/ =404; }}\n    location ~ \\.php$ {{\n        include snippets/fastcgi-php.conf;\n        fastcgi_pass unix:/run/php/php{php_ver}-fpm.sock;\n    }}\n}}\nEOF\nfi\n"
            if ndir.startswith("/home/"):
                user_home = "/".join(ndir.split("/")[:3])
                user_home_escaped = shlex.quote(user_home)
                s += f"chmod +x {user_home_escaped}\nchown -R $USER:$USER {ndir_escaped} || true\nchmod -R 755 {ndir_escaped} || true\n"

        if p_ap := self.ports["apache2"].text():
            if validate_port(p_ap):
                s += f"sed -i 's/^Listen .*/Listen {p_ap}/g' /etc/apache2/ports.conf\nsed -i -E 's/<VirtualHost \\*:.*>/<VirtualHost \\*:{p_ap}>/g' /etc/apache2/sites-available/000-default.conf\nsystemctl restart apache2 || true\n"
        if p_ma := self.ports["mariadb"].text():
            if validate_port(p_ma):
                s += f"sed -i -E 's/^port\s*=.*/port = {p_ma}/g' /etc/mysql/mariadb.conf.d/50-server.cnf\nsystemctl restart mariadb || true\n"
        if p_pg := self.ports["postgresql"].text():
            if validate_port(p_pg):
                s += f"sed -i -E 's/^#?port = [0-9]+/port = {p_pg}/g' /etc/postgresql/*/main/postgresql.conf\nsystemctl restart postgresql || true\n"
        if p_mg := self.ports["mongod"].text():
            if validate_port(p_mg):
                s += f"sed -i -E 's/^  port: [0-9]+/  port: {p_mg}/g' /etc/mongod.conf\nsystemctl restart mongod || true\n"
            
        if ndir or p_ng: s += "systemctl restart nginx || true\n"

        if run_root_script(s): 
            QMessageBox.information(self, "Success", "Konfigurasi disimpan! File conf telah diperbaiki.")
        else: 
            QMessageBox.critical(self, "Error", "Gagal menerapkan konfigurasi.")

    def enable_ssl(self):
        if run_root_script("a2enmod ssl && a2ensite default-ssl && systemctl restart apache2"): 
            QMessageBox.information(self, "SSL Enabled", "SSL Berhasil diaktifkan!")
        else: 
            QMessageBox.critical(self, "Error", "Gagal mengaktifkan SSL.")

    def setup_mailcatcher(self):
        script = "echo '#!/bin/bash\ncat >> /tmp/php-mail.log\necho -e \"\\n---END OF MAIL---\\n\" >> /tmp/php-mail.log' > /usr/local/bin/local-mailcatcher\nchmod +x /usr/local/bin/local-mailcatcher\ntouch /tmp/php-mail.log && chmod 777 /tmp/php-mail.log\nfor ini in /etc/php/*/apache2/php.ini /etc/php/*/fpm/php.ini; do\nif [ -f \"$ini\" ]; then\nif grep -q \"sendmail_path\" \"$ini\"; then\nsed -i 's|^;*sendmail_path .*|sendmail_path = /usr/local/bin/local-mailcatcher|g' \"$ini\"\nelse\necho 'sendmail_path = /usr/local/bin/local-mailcatcher' >> \"$ini\"\nfi\nfi\ndone\nsystemctl restart apache2 || true\nsystemctl restart php*-fpm || true"
        if run_root_script(script): 
            QMessageBox.information(self, "Mail Catcher", "Mail Catcher berhasil di-setup!")
            self.read_mails()
        else: 
            QMessageBox.critical(self, "Error", "Gagal setup Mail Catcher.")

    def read_mails(self):
        try:
            with open("/tmp/php-mail.log", "r") as f: 
                self.mail_viewer.setText(f.read().strip() or "Belum ada email yang ditangkap.")
        except FileNotFoundError: 
            self.mail_viewer.setText("Mail catcher log belum terbentuk. Silakan setup terlebih dahulu.")
        except Exception as e:
            self.mail_viewer.setText(f"Error membaca log: {str(e)}")
            logging.error(f"Error reading mail log: {e}")

class PhpPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.setContentsMargins(20,20,20,20)
        card_ver = Card()
        card_ver.layout.addWidget(QLabel("Universal PHP Switcher (Apache & Nginx FPM)", objectName="H1"))
        h_ver = QHBoxLayout()
        self.combo_php = QComboBox()
        self.combo_php.setMinimumHeight(40)
        self.populate_php()
        btn_switch = QPushButton("Apply PHP Version")
        btn_switch.setObjectName("BtnPrimary")
        btn_switch.setMinimumHeight(40)
        if HAS_ICONS: btn_switch.setIcon(qta.icon("fa5s.exchange-alt", color="white"))
        btn_switch.clicked.connect(self.switch_php)
        h_ver.addWidget(QLabel("Pilih Versi:"))
        h_ver.addWidget(self.combo_php)
        h_ver.addWidget(btn_switch)
        card_ver.layout.addLayout(h_ver)
        layout.addWidget(card_ver)

        card_ext = Card()
        card_ext.layout.addWidget(QLabel("PHP Extensions (Toggle)", objectName="H1"))
        self.ext_list = ["curl", "gd", "mbstring", "mysql", "xml", "zip", "intl", "sqlite3", "bcmath", "imagick"]
        self.checks = {}
        grid = QGridLayout()
        r, c = 0, 0
        for ext in self.ext_list:
            chk = QCheckBox(ext)
            chk.setStyleSheet("font-size: 14px; padding: 5px;")
            chk.clicked.connect(self.toggle_ext)
            self.checks[ext] = chk
            grid.addWidget(chk, r, c)
            c += 1
            if c > 3: c=0; r+=1
        card_ext.layout.addLayout(grid)
        btn_refresh = QPushButton(" Refresh Extension Status")
        btn_refresh.setObjectName("BtnSuccess") 
        if HAS_ICONS: btn_refresh.setIcon(qta.icon("fa5s.sync", color="white"))
        btn_refresh.clicked.connect(self.check_status)
        card_ext.layout.addWidget(btn_refresh)
        layout.addWidget(card_ext)
        layout.addStretch()
        self.setLayout(layout)
        QTimer.singleShot(500, self.check_status)

    def populate_php(self):
        try: 
            self.combo_php.addItems(sorted([d for d in os.listdir('/etc/php/') if d[0].isdigit()]))
        except Exception as e:
            self.combo_php.addItem("N/A")
            logging.warning(f"Failed to populate PHP versions: {e}")

    def switch_php(self):
        target = self.combo_php.currentText()
        if target == "N/A": return
        
        if not re.match(r'^\d+\.\d+$', target):
            QMessageBox.critical(self, "Error", "Versi PHP tidak valid!")
            return
            
        script = f"update-alternatives --set php /usr/bin/php{target} || true\nif command -v a2dismod &> /dev/null; then\na2dismod php* || true\na2enmod php{target} || true\nsystemctl restart apache2 || true\nfi\nsystemctl stop php*-fpm || true\nsystemctl start php{target}-fpm || true\nsystemctl enable php{target}-fpm || true\nif [ -f /etc/nginx/sites-available/default ]; then\nsed -i -E 's/fastcgi_pass unix:\/run\/php\/php[0-9.]+-fpm\\.sock;/fastcgi_pass unix:\/run\/php\/php{target}-fpm.sock;/g' /etc/nginx/sites-available/default\nsystemctl restart nginx || true\nfi\n"
        if run_root_script(script):
            QMessageBox.information(self, "Berhasil", f"PHP {target} sekarang aktif untuk Apache & Nginx!")
            self.check_status()
        else: 
            QMessageBox.critical(self, "Error", "Gagal berpindah versi PHP.")

    def check_status(self):
        try:
            ver = subprocess.check_output(["php", "-r", "echo PHP_MAJOR_VERSION.'.'.PHP_MINOR_VERSION;"], text=True, timeout=5)
            self.curr_ver = ver
            active = os.listdir(f"/etc/php/{ver}/cli/conf.d/")
            for ext, chk in self.checks.items(): 
                chk.setChecked(any(ext in f for f in active))
        except Exception as e:
            logging.warning(f"Failed to check PHP status: {e}")

    def toggle_ext(self):
        chk = self.sender()
        ext = chk.text()
        ver = getattr(self, 'curr_ver', '8.2')
        act = "phpenmod" if chk.isChecked() else "phpdismod"
        try:
            subprocess.run(["pkexec", "sh", "-c", f"{act} -v {ver} {ext} && systemctl restart apache2 || true && systemctl restart php{ver}-fpm || true"], timeout=30)
        except Exception as e:
            logging.error(f"Failed to toggle extension: {e}")
            QMessageBox.critical(self, "Error", f"Gagal toggle extension: {str(e)}")

class EditorPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.setContentsMargins(20,20,20,20)
        card = Card()
        card.layout.addWidget(QLabel("Config Editor", objectName="H1"))
        h = QHBoxLayout()
        self.combo = QComboBox()
        self.combo.setMinimumHeight(35)
        
        self.files = {
            "Apache: Main Config": "/etc/apache2/apache2.conf",
            "Apache: Ports Config": "/etc/apache2/ports.conf",
            "Apache: Default VHost": "/etc/apache2/sites-available/000-default.conf",
            "Nginx: Main Config": "/etc/nginx/nginx.conf",
            "Nginx: Default VHost": "/etc/nginx/sites-available/default",
            "MariaDB: Main Config": "/etc/mysql/mariadb.conf.d/50-server.cnf",
            "MongoDB: Main Config": "/etc/mongod.conf",
            "OS: Hosts File": "/etc/hosts"
        }
        
        php_cli = glob.glob("/etc/php/*/cli/php.ini")
        if php_cli: self.files[f"PHP: CLI ini ({php_cli[0].split('/')[3]})"] = php_cli[0]
        
        php_apa = glob.glob("/etc/php/*/apache2/php.ini")
        if php_apa: self.files[f"PHP: Apache ini ({php_apa[0].split('/')[3]})"] = php_apa[0]
        
        php_fpm = glob.glob("/etc/php/*/fpm/php.ini")
        if php_fpm: self.files[f"PHP: FPM ini ({php_fpm[0].split('/')[3]})"] = php_fpm[0]
        
        pg = glob.glob("/etc/postgresql/*/main/postgresql.conf")
        if pg: self.files[f"PostgreSQL: Config ({pg[0].split('/')[3]})"] = pg[0]

        self.combo.addItems(self.files.keys())
        
        btn_load = QPushButton("Load File")
        btn_load.setObjectName("BtnPrimary") 
        if HAS_ICONS: btn_load.setIcon(qta.icon("fa5s.folder-open", color="white"))
        btn_load.clicked.connect(self.load_file)
        h.addWidget(self.combo)
        h.addWidget(btn_load)
        card.layout.addLayout(h)
        self.editor = QTextEdit()
        card.layout.addWidget(self.editor)
        btn_save = QPushButton("Save Changes (Root)")
        btn_save.setObjectName("BtnDanger")
        if HAS_ICONS: btn_save.setIcon(qta.icon("fa5s.save", color="white"))
        btn_save.clicked.connect(self.save_file)
        card.layout.addWidget(btn_save)
        layout.addWidget(card)
        self.setLayout(layout)

    def load_file(self):
        path = self.files[self.combo.currentText()]
        if os.path.exists(path):
            try:
                with open(path,'r') as f: 
                    self.editor.setText(f.read())
                self.curr_path = path
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Gagal membaca file: {str(e)}")
                logging.error(f"Failed to load file: {e}")
        else: 
            QMessageBox.warning(self, "Not Found", "File tidak ditemukan di sistem Anda.")

    def save_file(self):
        if hasattr(self, 'curr_path'):
            content = self.editor.toPlainText()
            try:
                with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
                    temp_file.write(content)
                    temp_path = temp_file.name
                
                subprocess.run(["pkexec", "cp", temp_path, self.curr_path], check=True, timeout=10)
                os.remove(temp_path)
                QMessageBox.information(self, "Saved", "File berhasil disimpan!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Gagal menyimpan: {str(e)}")
                logging.error(f"Failed to save file: {e}")
                if 'temp_path' in locals() and os.path.exists(temp_path):
                    os.remove(temp_path)

class UtilsPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.setContentsMargins(20,20,20,20)
        card_perm = Card()
        card_perm.layout.addWidget(QLabel("Permission Fixer", objectName="H1"))
        h_perm = QHBoxLayout()
        self.inp_user = QLineEdit(os.environ.get('USER', 'live'))
        self.inp_user.setPlaceholderText("Username target...")
        self.inp_user.setMinimumHeight(35)
        btn_fix = QPushButton(" Fix Permissions")
        btn_fix.setObjectName("BtnSuccess")
        if HAS_ICONS: btn_fix.setIcon(qta.icon("fa5s.check-circle", color="white"))
        btn_fix.clicked.connect(self.fix_perms)
        h_perm.addWidget(QLabel("User:"))
        h_perm.addWidget(self.inp_user)
        h_perm.addWidget(btn_fix)
        card_perm.layout.addLayout(h_perm)
        layout.addWidget(card_perm)
        card_vhost = Card()
        card_vhost.layout.addWidget(QLabel("Create Virtual Host (Apache)", objectName="H1"))
        grid = QGridLayout()
        self.inp_dom = QLineEdit()
        self.inp_path = QLineEdit("/var/www/html")
        self.inp_path.setMinimumHeight(35)
        btn_browse = QPushButton("Browse...")
        btn_browse.setObjectName("BtnPrimary")
        btn_browse.setFixedWidth(100)
        btn_browse.clicked.connect(self.browse)
        grid.addWidget(QLabel("Domain:"), 0, 0)
        grid.addWidget(self.inp_dom, 0, 1, 1, 2)
        grid.addWidget(QLabel("Path:"), 1, 0)
        grid.addWidget(self.inp_path, 1, 1)
        grid.addWidget(btn_browse, 1, 2)
        card_vhost.layout.addLayout(grid)
        btn_create = QPushButton("Create Host")
        btn_create.setObjectName("BtnPrimary")
        if HAS_ICONS: btn_create.setIcon(qta.icon("fa5s.globe", color="white"))
        btn_create.clicked.connect(self.create_vhost)
        card_vhost.layout.addWidget(btn_create)
        layout.addWidget(card_vhost)
        layout.addStretch()
        self.setLayout(layout)

    def fix_perms(self):
        username = self.inp_user.text()
        if not validate_username(username):
            QMessageBox.critical(self, "Error", "Username tidak valid!")
            return
            
        try:
            username_escaped = shlex.quote(username)
            subprocess.run(["pkexec", "sh", "-c", f"chown -R {username_escaped}:{username_escaped} /var/www/html && chmod -R 755 /var/www/html"], check=True, timeout=30)
            QMessageBox.information(self, "Success", "Permission Fixed!")
        except subprocess.TimeoutExpired:
            QMessageBox.critical(self, "Timeout", "Operasi memakan waktu terlalu lama.")
        except Exception as e:
            QMessageBox.critical(self, "Fail", f"Gagal: {str(e)}")
            logging.error(f"Failed to fix permissions: {e}")

    def browse(self):
        if d := QFileDialog.getExistingDirectory(self): self.inp_path.setText(d)

    def create_vhost(self):
        dom = self.inp_dom.text()
        path = self.inp_path.text()
        
        if not validate_domain(dom):
            QMessageBox.critical(self, "Error", "Domain tidak valid!")
            return
            
        if not validate_path(path):
            QMessageBox.critical(self, "Error", "Path tidak valid!")
            return
            
        if not os.path.exists(path):
            QMessageBox.critical(self, "Error", "Path tidak ditemukan di sistem!")
            return
            
        try:
            dom_escaped = shlex.quote(dom)
            path_escaped = shlex.quote(path)
            
            vhost_content = f"""<VirtualHost *:80>
    ServerName {dom}
    DocumentRoot {path}
    <Directory {path}>
        Options Indexes FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>
</VirtualHost>"""
            
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
                temp_file.write(vhost_content)
                temp_path = temp_file.name
            
            subprocess.run(["pkexec", "cp", temp_path, f"/etc/apache2/sites-available/{dom}.conf"], check=True, timeout=10)
            os.remove(temp_path)
            subprocess.run(["pkexec", "sh", "-c", f"a2ensite {dom_escaped}.conf && systemctl reload apache2"], check=True, timeout=20)
            QMessageBox.information(self, "Success", "Domain created!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Gagal membuat domain: {str(e)}")
            logging.error(f"Failed to create vhost: {e}")
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Debian Ultimate Server Panel")
        self.resize(1050, 780)
        self.setStyleSheet(STYLESHEET)
        self.is_quitting = False
        
        main_wid = QWidget()
        self.setCentralWidget(main_wid)
        main_lay = QHBoxLayout()
        main_lay.setContentsMargins(0,0,0,0)
        main_lay.setSpacing(0)
        main_wid.setLayout(main_lay)
        
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(230)
        side_lay = QVBoxLayout()
        side_lay.setContentsMargins(0,20,0,20)
        
        title = QLabel("SERVER\nMANAGER")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 16px; margin-bottom: 30px;")
        side_lay.addWidget(title)
        
        self.btn_dash = self.mk_btn("Dashboard", "fa5s.tachometer-alt")
        self.btn_prefs = self.mk_btn("Preferences", "fa5s.cogs")
        self.btn_php = self.mk_btn("PHP Manager", "fa5b.php")
        self.btn_sniper = self.mk_btn("Port Sniper", "fa5s.crosshairs") 
        self.btn_edit = self.mk_btn("Config Editor", "fa5s.edit")
        self.btn_util = self.mk_btn("Utilities", "fa5s.tools")
        
        side_lay.addWidget(self.btn_dash)
        side_lay.addWidget(self.btn_prefs)
        side_lay.addWidget(self.btn_php)
        side_lay.addWidget(self.btn_sniper)
        side_lay.addWidget(self.btn_edit)
        side_lay.addWidget(self.btn_util)
        
        side_lay.addStretch()

        sys_frame = QFrame()
        sys_lay = QVBoxLayout(sys_frame)
        sys_lay.setContentsMargins(15, 10, 15, 10)
        sys_lay.setSpacing(8)
        
        lbl_sys = QLabel("SYSTEM RESOURCES")
        lbl_sys.setStyleSheet("color: #7f8c8d; font-size: 11px; font-weight: bold; margin-bottom: 5px;")
        sys_lay.addWidget(lbl_sys)

        self.side_bars = {}
        for label, color in [("CPU", "#3498db"), ("RAM", "#2ecc71"), ("DISK", "#f1c40f")]:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #bdc3c7; font-size: 10px; font-weight: bold;")
            lbl.setFixedWidth(35)
            
            bar = QProgressBar()
            bar.setObjectName("SideBar")
            bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {color}; border-radius: 4px; }}")
            bar.setFormat("%p%")
            
            row.addWidget(lbl)
            row.addWidget(bar)
            sys_lay.addLayout(row)
            self.side_bars[label] = bar
            
        side_lay.addWidget(sys_frame)
        sidebar.setLayout(side_lay)
        main_lay.addWidget(sidebar)
        
        self.stack = QStackedWidget()
        self.stack.addWidget(DashboardPage())
        self.stack.addWidget(PrefsPage())
        self.stack.addWidget(PhpPage())
        self.stack.addWidget(SniperPage())
        self.stack.addWidget(EditorPage())
        self.stack.addWidget(UtilsPage())
        main_lay.addWidget(self.stack)
        
        self.btn_dash.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.btn_prefs.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        self.btn_php.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        self.btn_sniper.clicked.connect(lambda: self.stack.setCurrentIndex(3))
        self.btn_edit.clicked.connect(lambda: self.stack.setCurrentIndex(4))
        self.btn_util.clicked.connect(lambda: self.stack.setCurrentIndex(5))
        self.btn_dash.setChecked(True)
        
        self.setup_tray_icon()
        
        self.global_timer = QTimer()
        self.global_timer.timeout.connect(self.update_sidebar_resources)
        self.global_timer.start(2000)
        self.update_sidebar_resources()

    def update_sidebar_resources(self):
        try:
            self.side_bars["CPU"].setValue(int(psutil.cpu_percent()))
            self.side_bars["RAM"].setValue(int(psutil.virtual_memory().percent))
            self.side_bars["DISK"].setValue(int(psutil.disk_usage('/').percent))
        except Exception as e:
            logging.warning(f"Failed to update system resources: {e}")

    def mk_btn(self, text: str, icon: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("MenuBtn")
        btn.setCheckable(True)
        btn.setAutoExclusive(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if HAS_ICONS: btn.setIcon(qta.icon(icon, color="white" if "php" in icon else "#bdc3c7"))
        return btn

    def setup_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon.fromTheme("utilities-system-monitor", QIcon("")))
        tray_menu = QMenu()
        show_action = QAction("Open Panel", self)
        show_action.triggered.connect(self.showNormal)
        quit_action = QAction("Quit Panel", self)
        quit_action.triggered.connect(self.force_quit)
        tray_menu.addAction(show_action)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def closeEvent(self, event):
        if not self.is_quitting:
            event.ignore()
            self.hide()
            self.tray_icon.showMessage("Running in Background", "Panel disembunyikan ke taskbar.", QSystemTrayIcon.MessageIcon.Information, 2500)
        else:
            if hasattr(self, 'global_timer'):
                self.global_timer.stop()
            event.accept()

    def force_quit(self):
        self.is_quitting = True
        if hasattr(self, 'global_timer'):
            self.global_timer.stop()
        QApplication.instance().quit()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())