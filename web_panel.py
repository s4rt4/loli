import sys
import os
import subprocess
import re
import webbrowser
import psutil 
import glob
import tempfile
import shlex
import socket
import shutil
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
                             QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget,
                             QSizePolicy, QGraphicsDropShadowEffect)
from PyQt6.QtCore import QTimer, Qt, QSize, QThread, pyqtSignal, QByteArray
from PyQt6.QtGui import QFont, QIcon, QAction, QColor, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "logo.svg")
TRAY_ICON_PATH = os.path.join(BASE_DIR, "logo-tray.svg")
# Tool yang diunduh saat runtime (pgweb/mailpit/phpMyAdmin) butuh lokasi yang bisa ditulis.
# Dari source, BASE_DIR bisa ditulis; saat terinstal sistem (mis. /usr/share/loli) pakai data dir per-user.
DATA_DIR = BASE_DIR if os.access(BASE_DIR, os.W_OK) else os.path.join(os.path.expanduser("~"), ".local", "share", "loli")
try:
    os.makedirs(DATA_DIR, exist_ok=True)
except Exception:
    DATA_DIR = BASE_DIR
APP_NAME = "Loli — Localhost Linux"
APP_VERSION = "1.0.1"
PGWEB_PORT = 8081
MAILPIT_UI_PORT = 8025
MAILPIT_SMTP_PORT = 1025

STYLESHEET = """
QMainWindow { background-color: #f8fafc; }
QWidget { color: #1e293b; }
QWidget#Sidebar { background-color: #1e293b; color: white; }
QWidget#Sidebar QLabel { color: white; }
QPushButton#MenuBtn { text-align: left; padding: 12px 20px; background-color: transparent; border: none; color: #94a3b8; font-size: 14px; border-radius: 0px; }
QPushButton#MenuBtn:hover { background-color: #334155; color: white; }
QPushButton#MenuBtn:checked { background-color: #3b82f6; color: white; font-weight: bold; border-left: 4px solid white; }
QFrame#Card { background-color: white; border-radius: 12px; border: 1px solid #e2e8f0; }
QLabel#H1 { font-size: 18px; font-weight: bold; color: #1e293b; margin-bottom: 15px; }
QLineEdit, QComboBox { background-color: white; color: #1e293b; border: 1px solid #cbd5e1; padding: 7px; border-radius: 6px; }
QLineEdit:focus, QComboBox:focus { border: 1px solid #3b82f6; }
QComboBox::drop-down { border: none; }
QCheckBox { color: #1e293b; }
QTextEdit { background-color: #1e293b; color: #e2e8f0; border-radius: 8px; padding: 10px; font-family: monospace; }
QPushButton { padding: 8px 16px; border-radius: 8px; font-size: 13px; font-weight: 600; border: 1px solid #cbd5e1; background-color: #f1f5f9; color: #334155; }
QPushButton:hover { background-color: #e2e8f0; }
QPushButton#BtnPrimary { background-color: #3b82f6; color: white; border: none; }
QPushButton#BtnPrimary:hover { background-color: #2563eb; }
QPushButton#BtnSuccess { background-color: #22c55e; color: white; border: none; }
QPushButton#BtnSuccess:hover { background-color: #16a34a; }
QPushButton#BtnDanger { background-color: #ef4444; color: white; border: none; }
QPushButton#BtnDanger:hover { background-color: #dc2626; }
QPushButton#BtnGhost { background-color: white; border: 1px solid #cbd5e1; color: #334155; font-weight: 600; }
QPushButton#BtnGhost:hover { background-color: #eff6ff; border: 1px solid #3b82f6; color: #2563eb; }
QLabel#PageTitle { font-size: 22px; font-weight: bold; color: #1e293b; }
QLabel#PageSub { color: #94a3b8; font-size: 12px; }
QLabel#Hint { color: #94a3b8; font-size: 12px; }
QLabel#Brand { color: white; font-size: 20px; font-weight: bold; }
QLabel#BrandSub { color: #94a3b8; font-size: 9px; font-weight: bold; letter-spacing: 2px; }
QPushButton#SideQuit { text-align: left; padding: 10px 20px; background-color: transparent; border: none; color: #94a3b8; font-size: 13px; }
QPushButton#SideQuit:hover { background-color: #334155; color: #ef4444; }
QLabel#StatusRun { color: #15803d; font-weight: bold; font-size: 11px; background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 12px; padding: 3px 13px; }
QLabel#StatusStop { color: #b91c1c; font-weight: bold; font-size: 11px; background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 12px; padding: 3px 13px; }
QLabel#StatusNA { color: #64748b; font-weight: bold; font-size: 11px; background-color: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 12px; padding: 3px 13px; }
QFrame#Row { background-color: transparent; border-radius: 8px; }
QFrame#Row:hover { background-color: #f1f5f9; }
QPushButton#BtnQuitGhost { background-color: white; border: 1px solid #fecaca; color: #ef4444; }
QPushButton#BtnQuitGhost:hover { background-color: #fef2f2; border: 1px solid #ef4444; color: #dc2626; }
QProgressBar#SideBar { background-color: #0f172a; border: none; border-radius: 4px; color: white; text-align: center; font-size: 10px; font-weight: bold; }
QTableWidget { background-color: white; color: #1e293b; border: 1px solid #e2e8f0; border-radius: 8px; gridline-color: #f1f5f9; }
QHeaderView::section { background-color: #f1f5f9; color: #334155; font-weight: bold; padding: 6px; border: none; border-bottom: 1px solid #e2e8f0; }
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

class _Worker(QThread):
    """Menjalankan fungsi blocking (subprocess/pkexec) di luar thread GUI agar UI tidak freeze."""
    finished_result = pyqtSignal(object)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            res = self._fn()
        except Exception as e:
            res = e
        self.finished_result.emit(res)

def run_async(parent, fn, on_done=None):
    """Jalankan fn() di thread terpisah; panggil on_done(hasil) di thread GUI saat selesai."""
    if not hasattr(parent, "_workers"):
        parent._workers = []
    w = _Worker(fn)

    def _cb(res):
        try:
            if on_done:
                on_done(res)
        finally:
            if w in parent._workers:
                parent._workers.remove(w)

    w.finished_result.connect(_cb)
    parent._workers.append(w)
    w.start()
    return w

def load_logo_pixmap(size: int, path: str = LOGO_PATH):
    """Render SVG logo ke pixmap persegi penuh (tanpa terpotong seperti QIcon.pixmap)."""
    if not os.path.exists(path):
        return None
    try:
        renderer = QSvgRenderer(path)
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        renderer.render(painter)
        painter.end()
        return pm
    except Exception as e:
        logging.warning(f"Failed to render logo: {e}")
        pm = QIcon(path).pixmap(QSize(size, size))
        return pm if not pm.isNull() else None

ICON_DIR = os.path.join(BASE_DIR, "icons")

# Peta nama ikon Font Awesome -> file SVG lokal (icons/<name>.svg).
# Tombol yang pakai nama ini otomatis memakai SVG bila tersedia.
_SVG_FOR_QTA = {
    "fa5s.play": "start",
    "fa5s.stop": "stop",
    "fa5s.sync": "restart",
    "fa5s.external-link-alt": "open",
}

def svg_icon(name, color="#cbd5e1", size=24):
    """Render Lucide SVG (icons/<name>.svg) ke QIcon dengan warna `color`.
    'currentColor' di-replace agar bisa di-tint. Return None bila file tak ada."""
    if not name:
        return None
    path = os.path.join(ICON_DIR, name + ".svg")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = f.read().replace("currentColor", color)
        renderer = QSvgRenderer(QByteArray(data.encode("utf-8")))
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        renderer.render(painter)
        painter.end()
        return QIcon(pm)
    except Exception as e:
        logging.warning(f"svg_icon failed for {name}: {e}")
        return None

def app_icon(qta_name, color="#334155", size=24):
    """Ikon SVG lokal bila ada mapping & file-nya tersedia, jika tidak fallback ke qtawesome."""
    svg = _SVG_FOR_QTA.get(qta_name)
    if svg:
        ic = svg_icon(svg, color, size)
        if ic is not None:
            return ic
    if HAS_ICONS:
        return qta.icon(qta_name, color=color)
    return QIcon()


def get_web_root() -> str:
    try:
        out = subprocess.run(["grep", "-m1", "^DocumentRoot", "/etc/httpd/conf/httpd.conf"],
                             capture_output=True, text=True, timeout=5).stdout
        if "DocumentRoot" in out:
            return out.split()[-1].strip().strip('"')
    except Exception as e:
        logging.warning(f"Failed to read DocumentRoot: {e}")
    return "/var/www/html"

def port_in_use(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False

def open_path(path: str):
    try:
        subprocess.Popen(["xdg-open", path])
    except Exception as e:
        logging.error(f"xdg-open failed: {e}")

def open_terminal(path: str) -> bool:
    candidates = [
        ("ptyxis", ["-d", path]),
        ("gnome-terminal", [f"--working-directory={path}"]),
        ("konsole", ["--workdir", path]),
        ("xfce4-terminal", [f"--working-directory={path}"]),
        ("xterm", ["-e", f"cd {shlex.quote(path)} && bash"]),
    ]
    for term, args in candidates:
        if shutil.which(term):
            try:
                subprocess.Popen([term] + args)
                return True
            except Exception as e:
                logging.warning(f"Failed to open terminal {term}: {e}")
    return False

def open_editor(path: str) -> bool:
    for ed in ("code", "codium"):
        if shutil.which(ed):
            try:
                subprocess.Popen([ed, path])
                return True
            except Exception as e:
                logging.warning(f"Failed to open editor {ed}: {e}")
    open_path(path)
    return False

def polkit_agent_running() -> bool:
    """True bila kemungkinan besar ada authentication agent polkit (untuk dialog password pkexec).
    Catatan: GNOME/KDE menyatukan agen ke dalam shell-nya (tak ada proses terpisah); XFCE/LXQt/WM
    minimalis butuh agen standalone (lxpolkit, polkit-gnome, dsb)."""
    try:
        for p in psutil.process_iter(['name', 'cmdline']):
            name = (p.info.get('name') or '').lower()
            if name == 'gnome-shell':  # GNOME: agen polkit menyatu di shell
                return True
            if ('polkit' in name and name != 'polkitd') or 'policykit' in name:
                return True
            cmd = ' '.join(p.info.get('cmdline') or []).lower()
            if any(k in cmd for k in ('authentication-agent', 'lxpolkit', 'xfce-polkit', 'policykit-agent')):
                return True
    except Exception as e:
        logging.warning(f"polkit agent check failed: {e}")
    # Desktop yang dikenal membundel agen polkit ke sesi/shell-nya
    de = (os.environ.get('XDG_CURRENT_DESKTOP', '') + ':' + os.environ.get('XDG_SESSION_DESKTOP', '')).lower()
    return any(k in de for k in ('gnome', 'kde', 'plasma', 'cinnamon', 'unity', 'pantheon', 'deepin', 'mate', 'ukui'))

class Card(QFrame):
    def __init__(self, layout_type="v"):
        super().__init__()
        self.setObjectName("Card")
        self.layout = QVBoxLayout() if layout_type == "v" else QHBoxLayout()
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(10)
        self.setLayout(self.layout)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(15, 23, 42, 28))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

def title_block(title, subtitle):
    """Judul halaman + subtitle abu di bawahnya, sebagai satu widget."""
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(2)
    v.addWidget(QLabel(title, objectName="PageTitle"))
    v.addWidget(QLabel(subtitle, objectName="PageSub"))
    return w

class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()
        self.pgweb_proc = None
        self.mailpit_proc = None
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        header = QHBoxLayout()
        header.addWidget(title_block("Dashboard", "Service status & quick controls"))
        header.addStretch()
        btn_local = QPushButton(" Open Localhost")
        btn_local.setObjectName("BtnGhost")
        btn_local.setCursor(Qt.CursorShape.PointingHandCursor)
        if HAS_ICONS: btn_local.setIcon(app_icon("fa5s.globe", color="#3b82f6"))
        btn_local.clicked.connect(lambda: webbrowser.open("http://localhost"))
        btn_root = QPushButton(" Open Root Dir")
        btn_root.setObjectName("BtnGhost")
        btn_root.setCursor(Qt.CursorShape.PointingHandCursor)
        if HAS_ICONS: btn_root.setIcon(app_icon("fa5s.folder-open", color="#3b82f6"))
        btn_root.clicked.connect(self.open_root_dir)
        btn_quit = QPushButton(" Quit")
        btn_quit.setObjectName("BtnQuitGhost")
        btn_quit.setCursor(Qt.CursorShape.PointingHandCursor)
        if HAS_ICONS: btn_quit.setIcon(app_icon("fa5s.power-off", color="#ef4444"))
        btn_quit.clicked.connect(lambda: self.window().force_quit())
        header.addWidget(btn_local)
        header.addWidget(btn_root)
        header.addWidget(btn_quit)
        layout.addLayout(header)

        card_db = Card()
        card_db.layout.addWidget(QLabel("Database Tools", objectName="H1"))

        row_pma = QHBoxLayout()
        lbl_pma = QLabel("phpMyAdmin (MySQL/MariaDB)")
        lbl_pma.setStyleSheet("font-weight: 600; font-size: 14px; color: #1e293b;")
        lbl_pma.setFixedWidth(224)
        row_pma.addWidget(lbl_pma)
        self.lbl_pma_status = QLabel("...")
        self.lbl_pma_status.setObjectName("StatusNA")
        self.lbl_pma_status.setFixedHeight(24)
        row_pma.addWidget(self.lbl_pma_status, 0, Qt.AlignmentFlag.AlignVCenter)
        row_pma.addStretch()
        btn_pma_open = QPushButton(" Open")
        btn_pma_open.setObjectName("BtnPrimary")
        btn_pma_open.setFixedWidth(92)
        if HAS_ICONS: btn_pma_open.setIcon(app_icon("fa5s.external-link-alt", color="white"))
        btn_pma_open.clicked.connect(lambda: webbrowser.open("http://localhost/phpmyadmin"))
        self.btn_pma_setup = QPushButton(" Setup / Repair")
        self.btn_pma_setup.setObjectName("BtnGhost")
        self.btn_pma_setup.setFixedWidth(148)
        if HAS_ICONS: self.btn_pma_setup.setIcon(app_icon("fa5s.wrench", color="#334155"))
        self.btn_pma_setup.clicked.connect(self.on_pma_action)
        btn_pma_setup = self.btn_pma_setup
        row_pma.addWidget(btn_pma_open)
        row_pma.addWidget(btn_pma_setup)
        row_pma.setContentsMargins(8, 5, 8, 5)
        row_pma_w = QFrame(); row_pma_w.setObjectName("Row"); row_pma_w.setLayout(row_pma)
        card_db.layout.addWidget(row_pma_w)

        line_db = QFrame()
        line_db.setFrameShape(QFrame.Shape.HLine)
        line_db.setStyleSheet("color: #e2e8f0;")
        card_db.layout.addWidget(line_db)

        row_pg = QHBoxLayout()
        lbl_pg = QLabel("pgweb (PostgreSQL)")
        lbl_pg.setStyleSheet("font-weight: 600; font-size: 14px; color: #1e293b;")
        lbl_pg.setFixedWidth(224)
        row_pg.addWidget(lbl_pg)
        self.lbl_pg_status = QLabel("● STOPPED")
        self.lbl_pg_status.setObjectName("StatusStop")
        self.lbl_pg_status.setFixedHeight(24)
        row_pg.addWidget(self.lbl_pg_status, 0, Qt.AlignmentFlag.AlignVCenter)
        row_pg.addStretch()
        self.btn_pg_toggle = QPushButton(" Start")
        self.btn_pg_toggle.setObjectName("BtnSuccess")
        self.btn_pg_toggle.setFixedWidth(92)
        if HAS_ICONS: self.btn_pg_toggle.setIcon(app_icon("fa5s.play", color="white"))
        self.btn_pg_toggle.clicked.connect(self.toggle_pgweb)
        btn_pg_open = QPushButton(" Open")
        btn_pg_open.setObjectName("BtnGhost")
        btn_pg_open.setFixedWidth(92)
        if HAS_ICONS: btn_pg_open.setIcon(app_icon("fa5s.external-link-alt", color="#334155"))
        btn_pg_open.clicked.connect(lambda: webbrowser.open("http://localhost:8081"))
        row_pg.addWidget(self.btn_pg_toggle)
        row_pg.addWidget(btn_pg_open)
        row_pg.setContentsMargins(8, 5, 8, 5)
        row_pg_w = QFrame(); row_pg_w.setObjectName("Row"); row_pg_w.setLayout(row_pg)
        card_db.layout.addWidget(row_pg_w)

        line_db3 = QFrame()
        line_db3.setFrameShape(QFrame.Shape.HLine)
        line_db3.setStyleSheet("color: #e2e8f0;")
        card_db.layout.addWidget(line_db3)

        row_mp = QHBoxLayout()
        lbl_mp = QLabel("Mailpit (SMTP Inbox)")
        lbl_mp.setStyleSheet("font-weight: 600; font-size: 14px; color: #1e293b;")
        lbl_mp.setFixedWidth(224)
        row_mp.addWidget(lbl_mp)
        self.lbl_mp_status = QLabel("● STOPPED")
        self.lbl_mp_status.setObjectName("StatusStop")
        self.lbl_mp_status.setFixedHeight(24)
        row_mp.addWidget(self.lbl_mp_status, 0, Qt.AlignmentFlag.AlignVCenter)
        row_mp.addStretch()
        self.btn_mp_toggle = QPushButton(" Start")
        self.btn_mp_toggle.setObjectName("BtnSuccess")
        self.btn_mp_toggle.setFixedWidth(92)
        if HAS_ICONS: self.btn_mp_toggle.setIcon(app_icon("fa5s.play", color="white"))
        self.btn_mp_toggle.clicked.connect(self.toggle_mailpit)
        btn_mp_open = QPushButton(" Open")
        btn_mp_open.setObjectName("BtnGhost")
        btn_mp_open.setFixedWidth(92)
        if HAS_ICONS: btn_mp_open.setIcon(app_icon("fa5s.external-link-alt", color="#334155"))
        btn_mp_open.clicked.connect(lambda: webbrowser.open(f"http://localhost:{MAILPIT_UI_PORT}"))
        row_mp.addWidget(self.btn_mp_toggle)
        row_mp.addWidget(btn_mp_open)
        row_mp.setContentsMargins(8, 5, 8, 5)
        row_mp_w = QFrame(); row_mp_w.setObjectName("Row"); row_mp_w.setLayout(row_mp)
        card_db.layout.addWidget(row_mp_w)

        layout.addWidget(card_db)

        card_svc = Card()
        card_svc.layout.addWidget(QLabel("Service Status", objectName="H1"))
        
        self.services = [
            ("httpd", "Apache Web Server", "fa5s.server"),
            ("nginx", "Nginx Web Server", "fa5s.server"),
            ("mariadb", "MariaDB Database", "fa5s.database"),
            ("postgresql", "PostgreSQL", "fa5s.database"),
            ("valkey", "Valkey (Redis)", "fa5s.bolt"),
            ("memcached", "Memcached", "fa5s.memory"),
            ("mongod", "MongoDB", "fa5s.database")
        ]
        # service -> nama paket dnf (utk tombol Install bila belum terpasang)
        self.svc_packages = {
            "httpd": "httpd", "nginx": "nginx", "mariadb": "mariadb-server",
            "postgresql": "postgresql-server", "valkey": "valkey", "memcached": "memcached",
            "mongod": "mongodb-org",
        }

        self.svc_widgets = {}

        for sys_name, display_name, icon_name in self.services:
            row = QHBoxLayout()
            lbl_icon = QLabel()
            if HAS_ICONS: lbl_icon.setPixmap(app_icon(icon_name, color="#334155").pixmap(24, 24))
            row.addWidget(lbl_icon)
            
            lbl_name = QLabel(display_name)
            lbl_name.setStyleSheet("font-weight: bold; font-size: 14px; color: #1e293b;")
            lbl_name.setFixedWidth(142)
            row.addWidget(lbl_name)
            row.addSpacing(16)

            lbl_status = QLabel("Checking...")
            lbl_status.setObjectName("StatusNA")
            lbl_status.setFixedHeight(24)
            row.addWidget(lbl_status, 0, Qt.AlignmentFlag.AlignVCenter)
            row.addStretch()

            action_stack = QStackedWidget()
            action_stack.setFixedWidth(95)
            
            btn_start = QPushButton(" Start")
            btn_start.setObjectName("BtnSuccess")
            if HAS_ICONS: btn_start.setIcon(app_icon("fa5s.play", color="white"))
            btn_start.clicked.connect(lambda checked, s=sys_name: self.run_cmd(s, "start"))
            
            btn_stop = QPushButton(" Stop")
            btn_stop.setObjectName("BtnDanger")
            if HAS_ICONS: btn_stop.setIcon(app_icon("fa5s.stop", color="white"))
            btn_stop.clicked.connect(lambda checked, s=sys_name: self.run_cmd(s, "stop"))
            
            action_stack.addWidget(btn_start)
            action_stack.addWidget(btn_stop)

            btn_restart = QPushButton(" Restart")
            btn_restart.setObjectName("BtnPrimary")
            btn_restart.setFixedWidth(105)
            if HAS_ICONS: btn_restart.setIcon(app_icon("fa5s.sync", color="white"))
            btn_restart.clicked.connect(lambda checked, s=sys_name: self.run_cmd(s, "restart"))

            btn_install = QPushButton(" Install")
            btn_install.setObjectName("BtnGhost")
            btn_install.setFixedWidth(150)
            if HAS_ICONS: btn_install.setIcon(app_icon("fa5s.download", color="#334155"))
            btn_install.clicked.connect(lambda checked, s=sys_name: self.install_svc(s))
            btn_install.hide()

            row.addWidget(action_stack)
            row.addWidget(btn_restart)
            row.addWidget(btn_install)
            row.setContentsMargins(8, 5, 8, 5)
            row_w = QFrame(); row_w.setObjectName("Row"); row_w.setLayout(row)
            card_svc.layout.addWidget(row_w)

            self.svc_widgets[sys_name] = {
                'status': lbl_status, 'action_stack': action_stack,
                'btn_restart': btn_restart, 'btn_install': btn_install,
                'icon': lbl_icon, 'icon_name': icon_name,
            }
            
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setStyleSheet("color: #e2e8f0;")
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
            out = subprocess.getoutput("grep -m 1 'DocumentRoot' /etc/httpd/conf/httpd.conf")
            if "DocumentRoot" in out: path = out.split()[-1].strip().strip('"')
        except Exception as e:
            logging.warning(f"Failed to get document root: {e}")
        subprocess.run(["xdg-open", path])

    def update_ui(self):
        # Status DB murah (cek file + proses) -> aman di thread GUI
        self.update_db_status()
        # Polling systemctl berat -> jalankan di thread agar UI tidak freeze
        if getattr(self, "_poll_running", False):
            return
        self._poll_running = True
        services = list(self.services)

        def work():
            result = {}
            for sys_name, _, _ in services:
                exist = subprocess.run(["systemctl", "list-unit-files", f"{sys_name}.service"],
                                       capture_output=True, timeout=10).returncode == 0
                if not exist:
                    result[sys_name] = "missing"
                else:
                    running = subprocess.run(["systemctl", "is-active", "--quiet", sys_name],
                                             timeout=10).returncode == 0
                    result[sys_name] = "running" if running else "stopped"
            return result

        def done(res):
            self._poll_running = False
            if isinstance(res, Exception):
                logging.warning(f"Status poll failed: {res}")
                return
            self._apply_status(res)

        run_async(self, work, done)

    def _apply_status(self, status: dict):
        for sys_name, _, _ in self.services:
            widgets = self.svc_widgets[sys_name]
            lbl = widgets['status']
            action_stack = widgets['action_stack']
            btn_restart = widgets['btn_restart']
            btn_install = widgets['btn_install']
            state = status.get(sys_name, "missing")

            if state == "missing":
                lbl.setText("○ NOT INSTALLED")
                lbl.setObjectName("StatusNA")
                action_stack.hide()
                btn_restart.hide()
                # tampilkan tombol Install bila paketnya kita kenal
                btn_install.setVisible(sys_name in self.svc_packages)
            else:
                btn_install.hide()
                action_stack.show()
                if state == "running":
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

            if HAS_ICONS:
                tint = "#27ae60" if state == "running" else ("#cbd5e1" if state == "missing" else "#94a3b8")
                widgets['icon'].setPixmap(app_icon(widgets['icon_name'], color=tint).pixmap(24, 24))

    def install_svc(self, svc: str):
        pkg = self.svc_packages.get(svc)
        if not pkg:
            return
        # MongoDB tidak ada di repo Fedora -> daftarkan repo resmi MongoDB dulu
        if svc == "mongod":
            self.console.append("\n> setup repo MongoDB + dnf install mongodb-org...")
            script = (
                "cat << 'EOF' > /etc/yum.repos.d/mongodb-org-8.0.repo\n"
                "[mongodb-org-8.0]\n"
                "name=MongoDB Repository\n"
                "baseurl=https://repo.mongodb.org/yum/redhat/9/mongodb-org/8.0/x86_64/\n"
                "gpgcheck=1\n"
                "enabled=1\n"
                "gpgkey=https://pgp.mongodb.com/server-8.0.asc\n"
                "EOF\n"
                "dnf install -y mongodb-org\n"
            )

            def done_mongo(ok):
                self.console.append("[SUCCESS] mongodb-org terpasang." if ok is True
                                    else "[ERROR] gagal install MongoDB (lihat dialog/izin).")
                self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())
                QTimer.singleShot(500, self.update_ui)

            run_async(self, lambda: run_root_script(script), done_mongo)
            return

        self.console.append(f"\n> dnf install {pkg}...")

        def work():
            return subprocess.run(["pkexec", "dnf", "install", "-y", pkg],
                                  capture_output=True, text=True, timeout=600).returncode

        def done(rc):
            if rc == 0:
                self.console.append(f"[SUCCESS] {pkg} terpasang.")
            elif isinstance(rc, Exception):
                self.console.append(f"[EXCEPTION] {rc}")
            else:
                self.console.append(f"[ERROR] gagal install {pkg} (code {rc})")
            self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())
            QTimer.singleShot(500, self.update_ui)

        run_async(self, work, done)

    def run_cmd(self, svc: str, action: str):
        if action == "start":
            if svc == "httpd" and self.check_svc("nginx"):
                self.console.append("\n[WARNING] Matikan Nginx terlebih dahulu untuk mencegah konflik Port 80!")
                QMessageBox.warning(self, "Conflict", "Nginx sedang berjalan! Harap matikan Nginx sebelum menyalakan Apache.")
                return
            if svc == "nginx" and self.check_svc("httpd"):
                self.console.append("\n[WARNING] Matikan Apache terlebih dahulu untuk mencegah konflik Port 80!")
                QMessageBox.warning(self, "Conflict", "Apache sedang berjalan! Harap matikan Apache sebelum menyalakan Nginx.")
                return

        self.console.append(f"\n> systemctl {action} {svc}...")

        def work():
            res = subprocess.run(["pkexec", "systemctl", action, svc], capture_output=True, text=True, timeout=120)
            detail = ""
            if res.returncode != 0:
                try:
                    log_res = subprocess.run(["journalctl", "-u", svc, "-n", "15", "--no-pager"], capture_output=True, text=True, timeout=10)
                    detail = log_res.stdout or ""
                except Exception:
                    pass
            return (res.returncode, detail)

        def done(r):
            if isinstance(r, subprocess.TimeoutExpired):
                self.console.append(f"[TIMEOUT] Operasi {action} memakan waktu terlalu lama")
            elif isinstance(r, Exception):
                self.console.append(f"[EXCEPTION] {str(r)}")
                logging.error(f"Error in run_cmd: {r}")
            else:
                rc, detail = r
                if rc == 0:
                    self.console.append(f"[SUCCESS] {svc} berhasil di-{action}.")
                else:
                    self.console.append(f"[ERROR] systemctl gagal (Code {rc})")
                    if detail:
                        self.console.append("--- [LOG DETAIL] ---")
                        self.console.append(detail.strip())
                        self.console.append("--------------------")
            self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())
            QTimer.singleShot(500, self.update_ui)

        run_async(self, work, done)

    def check_svc(self, svc: str) -> bool:
        try:
            return subprocess.run(["systemctl", "is-active", "--quiet", svc], timeout=5).returncode == 0
        except Exception:
            return False

    def update_db_status(self):
        # phpMyAdmin: 3 state -> belum diunduh / belum setup / configured
        pma_present = os.path.exists(os.path.join(DATA_DIR, "phpmyadmin", "index.php"))
        if not pma_present:
            self.lbl_pma_status.setText("○ NOT INSTALLED")
            self.lbl_pma_status.setObjectName("StatusNA")
            self.btn_pma_setup.setText(" Download")
            if HAS_ICONS: self.btn_pma_setup.setIcon(app_icon("fa5s.download", color="#334155"))
        elif os.path.exists("/etc/httpd/conf.d/phpMyAdmin.conf"):
            self.lbl_pma_status.setText("● CONFIGURED")
            self.lbl_pma_status.setObjectName("StatusRun")
            self.btn_pma_setup.setText(" Setup / Repair")
            if HAS_ICONS: self.btn_pma_setup.setIcon(app_icon("fa5s.wrench", color="#334155"))
        else:
            self.lbl_pma_status.setText("○ NOT SET UP")
            self.lbl_pma_status.setObjectName("StatusNA")
            self.btn_pma_setup.setText(" Setup / Repair")
            if HAS_ICONS: self.btn_pma_setup.setIcon(app_icon("fa5s.wrench", color="#334155"))
        self.lbl_pma_status.style().unpolish(self.lbl_pma_status)
        self.lbl_pma_status.style().polish(self.lbl_pma_status)

        # pgweb: running (port) / belum diunduh / stopped
        pg_bin = os.path.join(DATA_DIR, "pgweb_linux_amd64")
        if self._pgweb_running():
            self.lbl_pg_status.setText("● RUNNING")
            self.lbl_pg_status.setObjectName("StatusRun")
            self.btn_pg_toggle.setText(" Stop")
            self.btn_pg_toggle.setObjectName("BtnDanger")
            if HAS_ICONS: self.btn_pg_toggle.setIcon(app_icon("fa5s.stop", color="white"))
        elif not os.path.exists(pg_bin):
            self.lbl_pg_status.setText("○ NOT INSTALLED")
            self.lbl_pg_status.setObjectName("StatusNA")
            self.btn_pg_toggle.setText(" Download")
            self.btn_pg_toggle.setObjectName("BtnPrimary")
            if HAS_ICONS: self.btn_pg_toggle.setIcon(app_icon("fa5s.download", color="white"))
        else:
            self.lbl_pg_status.setText("● STOPPED")
            self.lbl_pg_status.setObjectName("StatusStop")
            self.btn_pg_toggle.setText(" Start")
            self.btn_pg_toggle.setObjectName("BtnSuccess")
            if HAS_ICONS: self.btn_pg_toggle.setIcon(app_icon("fa5s.play", color="white"))
        for w in (self.lbl_pg_status, self.btn_pg_toggle):
            w.style().unpolish(w)
            w.style().polish(w)

        # mailpit: running (port) / belum diunduh / stopped
        mp_bin = os.path.join(DATA_DIR, "mailpit")
        if port_in_use(MAILPIT_UI_PORT):
            self.lbl_mp_status.setText("● RUNNING")
            self.lbl_mp_status.setObjectName("StatusRun")
            self.btn_mp_toggle.setText(" Stop")
            self.btn_mp_toggle.setObjectName("BtnDanger")
            if HAS_ICONS: self.btn_mp_toggle.setIcon(app_icon("fa5s.stop", color="white"))
        elif not os.path.exists(mp_bin):
            self.lbl_mp_status.setText("○ NOT INSTALLED")
            self.lbl_mp_status.setObjectName("StatusNA")
            self.btn_mp_toggle.setText(" Download")
            self.btn_mp_toggle.setObjectName("BtnPrimary")
            if HAS_ICONS: self.btn_mp_toggle.setIcon(app_icon("fa5s.download", color="white"))
        else:
            self.lbl_mp_status.setText("● STOPPED")
            self.lbl_mp_status.setObjectName("StatusStop")
            self.btn_mp_toggle.setText(" Start")
            self.btn_mp_toggle.setObjectName("BtnSuccess")
            if HAS_ICONS: self.btn_mp_toggle.setIcon(app_icon("fa5s.play", color="white"))
        for w in (self.lbl_mp_status, self.btn_mp_toggle):
            w.style().unpolish(w)
            w.style().polish(w)

    def toggle_mailpit(self):
        mp_bin = os.path.join(DATA_DIR, "mailpit")
        if port_in_use(MAILPIT_UI_PORT):
            self.stop_mailpit()
        elif not os.path.exists(mp_bin):
            self.download_mailpit()
        else:
            self.start_mailpit()

    def download_mailpit(self):
        self.btn_mp_toggle.setEnabled(False)
        self.btn_mp_toggle.setText(" Downloading...")
        url = "https://github.com/axllent/mailpit/releases/latest/download/mailpit-linux-amd64.tar.gz"
        dest = DATA_DIR

        def work():
            tar = os.path.join(dest, "_mailpit.tar.gz")
            subprocess.run(["curl", "-fL", "-o", tar, url], check=True, timeout=180)
            subprocess.run(["tar", "-xzf", tar, "-C", dest, "mailpit"], check=True, timeout=60)
            os.chmod(os.path.join(dest, "mailpit"), 0o755)
            try: os.remove(tar)
            except Exception: pass
            return True

        def done(res):
            self.btn_mp_toggle.setEnabled(True)
            if res is True:
                QMessageBox.information(self, "Mailpit", "Mailpit berhasil diunduh. Klik Start untuk menjalankan.")
            else:
                QMessageBox.critical(self, "Error", f"Gagal mengunduh Mailpit:\n{res}")
            self.update_db_status()

        run_async(self, work, done)

    def start_mailpit(self):
        if port_in_use(MAILPIT_UI_PORT):
            webbrowser.open(f"http://localhost:{MAILPIT_UI_PORT}")
            self.update_db_status()
            return
        binary = os.path.join(DATA_DIR, "mailpit")
        if not os.path.exists(binary):
            self.download_mailpit()
            return
        try:
            os.chmod(binary, 0o755)
            self._mailpit_log = tempfile.NamedTemporaryFile(mode='w+', suffix='.log', prefix='mailpit-', delete=False)
            self.mailpit_proc = subprocess.Popen(
                [binary, "--listen", f"127.0.0.1:{MAILPIT_UI_PORT}", "--smtp", f"127.0.0.1:{MAILPIT_SMTP_PORT}"],
                stdout=subprocess.DEVNULL, stderr=self._mailpit_log)
        except Exception as e:
            logging.error(f"Failed to start mailpit: {e}")
            QMessageBox.critical(self, "Error", f"Gagal menjalankan Mailpit: {str(e)}")
            return
        QTimer.singleShot(1000, self._check_mailpit_started)
        self.update_db_status()

    def _check_mailpit_started(self):
        proc = self.mailpit_proc
        if proc is not None and proc.poll() is not None:
            err = ""
            try:
                lg = getattr(self, "_mailpit_log", None)
                if lg is not None:
                    lg.flush()
                    with open(lg.name) as f:
                        err = f.read()
            except Exception:
                pass
            self.mailpit_proc = None
            msg = (err.strip().splitlines() or ["proses berhenti tanpa pesan"])[-1]
            QMessageBox.critical(self, "Mailpit gagal start", f"Mailpit berhenti:\n\n{msg}")
        elif port_in_use(MAILPIT_UI_PORT):
            webbrowser.open(f"http://localhost:{MAILPIT_UI_PORT}")
        self.update_db_status()

    def stop_mailpit(self):
        if self.mailpit_proc is not None and self.mailpit_proc.poll() is None:
            try:
                self.mailpit_proc.terminate()
                self.mailpit_proc.wait(timeout=5)
            except Exception:
                try: self.mailpit_proc.kill()
                except Exception: pass
        self.mailpit_proc = None
        if port_in_use(MAILPIT_UI_PORT):
            try:
                subprocess.run(["pkill", "-f", f"{DATA_DIR}/mailpit"], timeout=5)
            except Exception as e:
                logging.warning(f"Failed to pkill mailpit: {e}")
        self.update_db_status()

    def on_pma_action(self):
        # Tombol dinamis: Download bila belum ada, selain itu Setup/Repair
        if not os.path.exists(os.path.join(DATA_DIR, "phpmyadmin", "index.php")):
            self.download_phpmyadmin()
        else:
            self.setup_phpmyadmin()

    def download_phpmyadmin(self):
        self.btn_pma_setup.setEnabled(False)
        self.btn_pma_setup.setText(" Downloading...")

        def work():
            import json, urllib.request, zipfile
            meta = json.loads(urllib.request.urlopen(
                "https://www.phpmyadmin.net/home_page/version.json", timeout=30).read().decode())
            ver = meta.get("version")
            if not ver:
                raise RuntimeError("tidak bisa mendeteksi versi phpMyAdmin")
            url = f"https://files.phpmyadmin.net/phpMyAdmin/{ver}/phpMyAdmin-{ver}-all-languages.zip"
            zpath = os.path.join(DATA_DIR, "_pma.zip")
            subprocess.run(["curl", "-fL", "-o", zpath, url], check=True, timeout=360)
            with zipfile.ZipFile(zpath) as z:
                z.extractall(DATA_DIR)
            extracted = os.path.join(DATA_DIR, f"phpMyAdmin-{ver}-all-languages")
            target = os.path.join(DATA_DIR, "phpmyadmin")
            if os.path.isdir(extracted) and not os.path.exists(target):
                shutil.move(extracted, target)
            try: os.remove(zpath)
            except Exception: pass
            return ver

        def done(res):
            self.btn_pma_setup.setEnabled(True)
            if isinstance(res, str):
                QMessageBox.information(self, "phpMyAdmin",
                    f"phpMyAdmin {res} berhasil diunduh.\nKlik 'Setup / Repair' untuk konfigurasi.")
            else:
                QMessageBox.critical(self, "Error", f"Gagal mengunduh phpMyAdmin:\n{res}")
            self.update_db_status()

        run_async(self, work, done)

    def setup_phpmyadmin(self):
        import secrets
        pma = os.path.join(DATA_DIR, "phpmyadmin")
        if not os.path.exists(os.path.join(pma, "index.php")):
            QMessageBox.critical(self, "Error", f"phpMyAdmin tidak ditemukan di:\n{pma}")
            return

        secret = secrets.token_hex(16)
        config = (
            "<?php\n"
            "declare(strict_types=1);\n"
            f"$cfg['blowfish_secret'] = '{secret}';\n"
            "$i = 0;\n"
            "$i++;\n"
            "$cfg['Servers'][$i]['auth_type'] = 'cookie';\n"
            "$cfg['Servers'][$i]['host'] = '127.0.0.1';\n"
            "$cfg['Servers'][$i]['compress'] = false;\n"
            "$cfg['Servers'][$i]['AllowNoPassword'] = true;\n"
            f"$cfg['TempDir'] = '{pma}/tmp';\n"
        )

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.php', delete=False) as tf:
                tf.write(config)
                tmp_path = tf.name
        except Exception as e:
            logging.error(f"Failed to write phpMyAdmin config: {e}")
            QMessageBox.critical(self, "Error", "Gagal menyiapkan config phpMyAdmin.")
            return

        pma_q = shlex.quote(pma)
        tmp_q = shlex.quote(tmp_path)
        script = (
            f"PMA={pma_q}\n"
            f"cp {tmp_q} \"$PMA/config.inc.php\"\n"
            "mkdir -p \"$PMA/tmp\"\n"
            "cat << 'EOF' > /etc/httpd/conf.d/phpMyAdmin.conf\n"
            f"Alias /phpmyadmin {pma}\n"
            f"<Directory {pma}>\n"
            "    Options FollowSymLinks\n"
            "    DirectoryIndex index.php\n"
            "    AllowOverride All\n"
            "    Require all granted\n"
            "</Directory>\n"
            "EOF\n"
            "chown -R apache:apache \"$PMA\"\n"
            "chmod 1777 \"$PMA/tmp\"\n"
            f"command -v semanage >/dev/null 2>&1 && semanage fcontext -a -t httpd_sys_content_t '{pma}(/.*)?' 2>/dev/null\n"
            f"command -v semanage >/dev/null 2>&1 && semanage fcontext -a -t httpd_sys_rw_content_t '{pma}/tmp(/.*)?' 2>/dev/null\n"
            "command -v restorecon >/dev/null 2>&1 && restorecon -R \"$PMA\"\n"
            # SELinux: izinkan httpd/php membuka koneksi jaringan ke database (perbaiki error 2002 Permission denied)
            "command -v setsebool >/dev/null 2>&1 && setsebool -P httpd_can_network_connect_db on 2>/dev/null || true\n"
            "systemctl restart httpd\n"
        )

        def work():
            return run_root_script(script)

        def done(ok):
            if tmp_path and os.path.exists(tmp_path):
                try: os.remove(tmp_path)
                except Exception: pass
            if ok is True:
                QMessageBox.information(self, "phpMyAdmin", "phpMyAdmin siap diakses di:\nhttp://localhost/phpmyadmin")
                webbrowser.open("http://localhost/phpmyadmin")
            else:
                QMessageBox.critical(self, "Error", "Gagal melakukan setup phpMyAdmin.")
            self.update_db_status()

        run_async(self, work, done)

    def _pgweb_running(self):
        # Berbasis port: terdeteksi walau prosesnya orphan dari sesi sebelumnya
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.3)
                return s.connect_ex(("127.0.0.1", PGWEB_PORT)) == 0
        except Exception:
            return False

    def toggle_pgweb(self):
        if self._pgweb_running():
            self.stop_pgweb()
        elif not os.path.exists(os.path.join(DATA_DIR, "pgweb_linux_amd64")):
            self.download_pgweb()
        else:
            self.start_pgweb()

    def download_pgweb(self):
        self.btn_pg_toggle.setEnabled(False)
        self.btn_pg_toggle.setText(" Downloading...")
        url = "https://github.com/sosedoff/pgweb/releases/latest/download/pgweb_linux_amd64.zip"

        def work():
            import zipfile
            zpath = os.path.join(DATA_DIR, "_pgweb.zip")
            subprocess.run(["curl", "-fL", "-o", zpath, url], check=True, timeout=240)
            with zipfile.ZipFile(zpath) as z:
                member = next((n for n in z.namelist() if "pgweb" in n.lower() and not n.endswith("/")), None)
                if not member:
                    raise RuntimeError("binary pgweb tidak ditemukan di arsip")
                with z.open(member) as src, open(os.path.join(DATA_DIR, "pgweb_linux_amd64"), "wb") as dst:
                    shutil.copyfileobj(src, dst)
            os.chmod(os.path.join(DATA_DIR, "pgweb_linux_amd64"), 0o755)
            try: os.remove(zpath)
            except Exception: pass
            return True

        def done(res):
            self.btn_pg_toggle.setEnabled(True)
            if res is True:
                QMessageBox.information(self, "pgweb", "pgweb berhasil diunduh. Klik Start untuk menjalankan.")
            else:
                QMessageBox.critical(self, "Error", f"Gagal mengunduh pgweb:\n{res}")
            self.update_db_status()

        run_async(self, work, done)

    def start_pgweb(self):
        if self._pgweb_running():
            # Sudah berjalan (mis. instance lama) -> jangan spawn lagi, cukup buka
            webbrowser.open(f"http://localhost:{PGWEB_PORT}")
            self.update_db_status()
            return

        binary = os.path.join(DATA_DIR, "pgweb_linux_amd64")
        if not os.path.exists(binary):
            QMessageBox.critical(self, "Error", f"Binary pgweb tidak ditemukan di:\n{binary}")
            return
        try:
            os.chmod(binary, 0o755)
            # stderr ke file (bukan PIPE) supaya buffer tidak penuh & error bisa dibaca jika gagal
            self._pgweb_log = tempfile.NamedTemporaryFile(mode='w+', suffix='.log', prefix='pgweb-', delete=False)
            self.pgweb_proc = subprocess.Popen(
                [binary, "--bind", "127.0.0.1", "--listen", str(PGWEB_PORT), "--sessions"],
                stdout=subprocess.DEVNULL, stderr=self._pgweb_log)
        except Exception as e:
            logging.error(f"Failed to start pgweb: {e}")
            QMessageBox.critical(self, "Error", f"Gagal menjalankan pgweb: {str(e)}")
            return
        # Cek setelah jeda: kalau proses sudah mati, tampilkan errornya
        QTimer.singleShot(1000, self._check_pgweb_started)
        self.update_db_status()

    def _check_pgweb_started(self):
        proc = self.pgweb_proc
        if proc is not None and proc.poll() is not None:
            err = ""
            try:
                log_path = getattr(self, "_pgweb_log", None)
                if log_path is not None:
                    log_path.flush()
                    with open(log_path.name) as f:
                        err = f.read()
            except Exception:
                pass
            self.pgweb_proc = None
            msg = (err.strip().splitlines() or ["proses berhenti tanpa pesan"])[-1]
            QMessageBox.critical(self, "pgweb gagal start", f"pgweb berhenti:\n\n{msg}")
        elif self._pgweb_running():
            webbrowser.open(f"http://localhost:{PGWEB_PORT}")
        self.update_db_status()

    def stop_pgweb(self):
        if self.pgweb_proc is not None and self.pgweb_proc.poll() is None:
            try:
                self.pgweb_proc.terminate()
                self.pgweb_proc.wait(timeout=5)
            except Exception:
                try: self.pgweb_proc.kill()
                except Exception: pass
        self.pgweb_proc = None
        # Bersihkan juga instance orphan yang masih memegang port
        if self._pgweb_running():
            try:
                subprocess.run(["pkill", "-f", "pgweb_linux_amd64"], timeout=5)
            except Exception as e:
                logging.warning(f"Failed to pkill pgweb: {e}")
        self.update_db_status()

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
        if HAS_ICONS: self.btn_scan.setIcon(app_icon("fa5s.search", color="white"))
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
            btn_kill.setStyleSheet("background-color: #ef4444; color: white; font-weight: bold; border-radius: 4px; padding: 6px 12px;")
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
        if HAS_ICONS: btn_ssl.setIcon(app_icon("fa5s.lock", color="white"))
        btn_ssl.clicked.connect(self.enable_ssl)
        btn_mail = QPushButton(" Setup Mail Catcher")
        btn_mail.setObjectName("BtnPrimary")
        if HAS_ICONS: btn_mail.setIcon(app_icon("fa5s.envelope", color="white"))
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
            out = subprocess.getoutput("grep -m 1 'DocumentRoot' /etc/httpd/conf/httpd.conf")
            if "DocumentRoot" in out: self.inp_dir.setText(out.split()[-1].strip().strip('"'))
        except Exception as e:
            logging.warning(f"Failed to load document root: {e}")

        try:
            if "Listen" in (ap := subprocess.getoutput("grep -m 1 '^Listen' /etc/httpd/conf/httpd.conf")): self.ports["apache2"].setText(ap.split()[-1].strip())
            if "listen" in (ng := subprocess.getoutput("grep -m 1 'listen' /etc/nginx/nginx.conf")): self.ports["nginx"].setText(ng.replace('listen','').replace(';','').strip().split()[0])
            if "port" in (ma := subprocess.getoutput("grep -m 1 '^port' /etc/my.cnf.d/mariadb-server.cnf")): self.ports["mariadb"].setText(ma.split('=')[-1].strip())
            if "port" in (pg := subprocess.getoutput("grep -m 1 '^port' /var/lib/pgsql/data/postgresql.conf")): self.ports["postgresql"].setText(pg.split('=')[-1].strip())
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
        if not re.match(r"^\d+\.\d+$", php_ver): php_ver = "8.4"

        p_ng = self.ports["nginx"].text()

        if ndir:
            ndir_escaped = shlex.quote(ndir)
            s += f"sed -i 's|^DocumentRoot .*|DocumentRoot {ndir_escaped}|g' /etc/httpd/conf/httpd.conf\n"
            s += f"cat << 'EOF' > /etc/httpd/conf.d/custom-panel-dir.conf\n<Directory {ndir_escaped}>\n    Options Indexes FollowSymLinks\n    AllowOverride All\n    Require all granted\n</Directory>\nEOF\n"
            if p_ng and validate_port(p_ng):
                s += f"if [ -d /etc/nginx/conf.d ]; then\ncat << 'EOF' > /etc/nginx/conf.d/custom-panel.conf\nserver {{\n    listen {p_ng};\n    root {ndir_escaped};\n    index index.php index.html index.htm;\n    server_name _;\n    location / {{ try_files $uri $uri/ =404; }}\n    location ~ \\.php$ {{\n        fastcgi_split_path_info ^(.+\\.php)(/.+)$;\n        fastcgi_pass unix:/run/php-fpm/www.sock;\n        fastcgi_index index.php;\n        include fastcgi_params;\n        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;\n    }}\n}}\nEOF\nfi\n"
            if ndir.startswith("/home/"):
                user_home = "/".join(ndir.split("/")[:3])
                user_home_escaped = shlex.quote(user_home)
                s += f"chmod +x {user_home_escaped}\nchown -R apache:apache {ndir_escaped} || true\nchmod -R 755 {ndir_escaped} || true\n"
                # SELinux (Fedora): izinkan httpd melayani docroot custom
                s += f"command -v semanage >/dev/null 2>&1 && semanage fcontext -a -t httpd_sys_content_t {ndir_escaped}'(/.*)?' 2>/dev/null; command -v restorecon >/dev/null 2>&1 && restorecon -R {ndir_escaped} || true\n"

        if p_ap := self.ports["apache2"].text():
            if validate_port(p_ap):
                s += f"sed -i 's/^Listen .*/Listen {p_ap}/g' /etc/httpd/conf/httpd.conf\n"
                # SELinux (Fedora): daftarkan port http non-standar sebelum restart
                s += f"command -v semanage >/dev/null 2>&1 && semanage port -a -t http_port_t -p tcp {p_ap} 2>/dev/null || true\n"
                s += "systemctl restart httpd || true\n"
        if p_ma := self.ports["mariadb"].text():
            if validate_port(p_ma):
                s += f"printf '[mysqld]\\nport = {p_ma}\\n' > /etc/my.cnf.d/custom-panel.cnf\nsystemctl restart mariadb || true\n"
        if p_pg := self.ports["postgresql"].text():
            if validate_port(p_pg):
                s += f"sed -i -E 's/^#?port = [0-9]+/port = {p_pg}/g' /var/lib/pgsql/data/postgresql.conf\nsystemctl restart postgresql || true\n"
        if p_mg := self.ports["mongod"].text():
            if validate_port(p_mg):
                s += f"sed -i -E 's/^  port: [0-9]+/  port: {p_mg}/g' /etc/mongod.conf\nsystemctl restart mongod || true\n"

        if ndir or p_ng: s += "systemctl restart nginx || true\n"

        if run_root_script(s): 
            QMessageBox.information(self, "Success", "Konfigurasi disimpan! File conf telah diperbaiki.")
        else: 
            QMessageBox.critical(self, "Error", "Gagal menerapkan konfigurasi.")

    def enable_ssl(self):
        # Fedora: paket mod_ssl menaruh /etc/httpd/conf.d/ssl.conf yang otomatis dimuat
        if run_root_script("dnf install -y mod_ssl && systemctl restart httpd"):
            QMessageBox.information(self, "SSL Enabled", "SSL Berhasil diaktifkan (mod_ssl terpasang)!")
        else:
            QMessageBox.critical(self, "Error", "Gagal mengaktifkan SSL.")

    def setup_mailcatcher(self):
        script = "echo '#!/bin/bash\ncat >> /tmp/php-mail.log\necho -e \"\\n---END OF MAIL---\\n\" >> /tmp/php-mail.log' > /usr/local/bin/local-mailcatcher\nchmod +x /usr/local/bin/local-mailcatcher\ntouch /tmp/php-mail.log && chmod 777 /tmp/php-mail.log\nfor ini in /etc/php.ini; do\nif [ -f \"$ini\" ]; then\nif grep -q \"sendmail_path\" \"$ini\"; then\nsed -i 's|^;*sendmail_path .*|sendmail_path = /usr/local/bin/local-mailcatcher|g' \"$ini\"\nelse\necho 'sendmail_path = /usr/local/bin/local-mailcatcher' >> \"$ini\"\nfi\nfi\ndone\nsystemctl restart httpd || true\nsystemctl restart php-fpm || true"
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
        if HAS_ICONS: btn_switch.setIcon(app_icon("fa5s.exchange-alt", color="white"))
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
        if HAS_ICONS: btn_refresh.setIcon(app_icon("fa5s.sync", color="white"))
        btn_refresh.clicked.connect(self.check_status)
        card_ext.layout.addWidget(btn_refresh)
        layout.addWidget(card_ext)
        layout.addStretch()
        self.setLayout(layout)
        QTimer.singleShot(500, self.check_status)

    def populate_php(self):
        try:
            ver = subprocess.check_output(["php", "-r", "echo PHP_MAJOR_VERSION.'.'.PHP_MINOR_VERSION;"], text=True, timeout=5).strip()
            self.combo_php.addItem(ver)
        except Exception as e:
            self.combo_php.addItem("N/A")
            logging.warning(f"Failed to populate PHP versions: {e}")

    def switch_php(self):
        target = self.combo_php.currentText()
        if target == "N/A": return
        
        if not re.match(r'^\d+\.\d+$', target):
            QMessageBox.critical(self, "Error", "Versi PHP tidak valid!")
            return

        # Fedora memakai satu PHP sistem yang dikelola dnf (atau dnf module / Remi untuk versi lain).
        QMessageBox.information(self, "Info",
            f"Fedora menggunakan satu PHP sistem (saat ini {target}) yang dikelola oleh dnf.\n\n"
            "Untuk berpindah versi, jalankan di terminal (mis. via repo Remi):\n"
            "  sudo dnf module reset php\n"
            "  sudo dnf module enable php:remi-8.3\n"
            "  sudo dnf install php\n\n"
            "Panel tidak mengubah versi otomatis untuk mencegah kerusakan sistem.")

    def check_status(self):
        try:
            ver = subprocess.check_output(["php", "-r", "echo PHP_MAJOR_VERSION.'.'.PHP_MINOR_VERSION;"], text=True, timeout=5)
            self.curr_ver = ver
            active = os.listdir("/etc/php.d/")
            for ext, chk in self.checks.items():
                chk.setChecked(any(ext in f for f in active))
        except Exception as e:
            logging.warning(f"Failed to check PHP status: {e}")

    def toggle_ext(self):
        chk = self.sender()
        ext = chk.text()
        # Pemetaan ekstensi -> paket Fedora. None = bawaan (php-common/php-pdo), tak bisa di-toggle terpisah.
        pkg_map = {
            "curl": None, "sqlite3": None,
            "gd": "php-gd", "mbstring": "php-mbstring", "mysql": "php-mysqlnd",
            "xml": "php-xml", "zip": "php-pecl-zip", "intl": "php-intl",
            "bcmath": "php-bcmath", "imagick": "php-pecl-imagick",
        }
        pkg = pkg_map.get(ext)
        if pkg is None:
            QMessageBox.information(self, "Info", f"Ekstensi '{ext}' adalah bawaan PHP Fedora dan tidak dapat di-toggle terpisah.")
            chk.setChecked(True)
            return
        action = "install" if chk.isChecked() else "remove"
        try:
            res = subprocess.run(["pkexec", "sh", "-c", f"dnf {action} -y {shlex.quote(pkg)} && (systemctl restart php-fpm || true) && (systemctl restart httpd || true)"], timeout=300)
            if res.returncode != 0:
                QMessageBox.warning(self, "Gagal", f"Operasi 'dnf {action} {pkg}' gagal (paket tidak tersedia atau dibatalkan).")
        except Exception as e:
            logging.error(f"Failed to toggle extension: {e}")
            QMessageBox.critical(self, "Error", f"Gagal toggle extension: {str(e)}")
        self.check_status()

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
            "Apache: Main Config": "/etc/httpd/conf/httpd.conf",
            "Apache: PHP Module": "/etc/httpd/conf.d/php.conf",
            "Apache: SSL Config": "/etc/httpd/conf.d/ssl.conf",
            "Apache: Panel VHost": "/etc/httpd/conf.d/custom-panel-dir.conf",
            "Nginx: Main Config": "/etc/nginx/nginx.conf",
            "Nginx: Panel VHost": "/etc/nginx/conf.d/custom-panel.conf",
            "MariaDB: Server Config": "/etc/my.cnf.d/mariadb-server.cnf",
            "PHP: php.ini": "/etc/php.ini",
            "PHP: FPM Pool (www)": "/etc/php-fpm.d/www.conf",
            "MongoDB: Main Config": "/etc/mongod.conf",
            "OS: Hosts File": "/etc/hosts"
        }

        pg = glob.glob("/var/lib/pgsql/data/postgresql.conf") + glob.glob("/var/lib/pgsql/*/data/postgresql.conf")
        if pg: self.files["PostgreSQL: Config"] = pg[0]

        self.combo.addItems(self.files.keys())
        
        btn_load = QPushButton("Load File")
        btn_load.setObjectName("BtnPrimary") 
        if HAS_ICONS: btn_load.setIcon(app_icon("fa5s.folder-open", color="white"))
        btn_load.clicked.connect(self.load_file)
        h.addWidget(self.combo)
        h.addWidget(btn_load)
        card.layout.addLayout(h)
        self.editor = QTextEdit()
        card.layout.addWidget(self.editor)
        btn_save = QPushButton("Save Changes (Root)")
        btn_save.setObjectName("BtnDanger")
        if HAS_ICONS: btn_save.setIcon(app_icon("fa5s.save", color="white"))
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
        if HAS_ICONS: btn_fix.setIcon(app_icon("fa5s.check-circle", color="white"))
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
        if HAS_ICONS: btn_create.setIcon(app_icon("fa5s.globe", color="white"))
        btn_create.clicked.connect(self.create_vhost)
        card_vhost.layout.addWidget(btn_create)

        self.dom_table = QTableWidget()
        self.dom_table.setColumnCount(3)
        self.dom_table.setHorizontalHeaderLabels(["Domain", "Document Root", ""])
        self.dom_table.verticalHeader().setVisible(False)
        self.dom_table.verticalHeader().setDefaultSectionSize(40)
        dh = self.dom_table.horizontalHeader()
        dh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        dh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        dh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.dom_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.dom_table.setMaximumHeight(180)
        card_vhost.layout.addWidget(self.dom_table)
        layout.addWidget(card_vhost)

        card_dbsetup = Card()
        card_dbsetup.layout.addWidget(QLabel("Database Setup", objectName="H1"))
        hint = QLabel("Aksi sekali-pakai untuk menyiapkan database server lokal.")
        hint.setObjectName("Hint")
        card_dbsetup.layout.addWidget(hint)
        h_dbs = QHBoxLayout()
        btn_pg_init = QPushButton(" Init PostgreSQL")
        btn_pg_init.setObjectName("BtnPrimary")
        if HAS_ICONS: btn_pg_init.setIcon(app_icon("fa5s.database", color="white"))
        btn_pg_init.clicked.connect(self.init_postgres)
        btn_pg_login = QPushButton(" PostgreSQL Login Setup")
        btn_pg_login.setObjectName("BtnPrimary")
        if HAS_ICONS: btn_pg_login.setIcon(app_icon("fa5s.key", color="white"))
        btn_pg_login.clicked.connect(self.setup_postgres_login)
        btn_my_pwless = QPushButton(" MariaDB Passwordless")
        btn_my_pwless.setObjectName("BtnPrimary")
        if HAS_ICONS: btn_my_pwless.setIcon(app_icon("fa5s.key", color="white"))
        btn_my_pwless.clicked.connect(self.setup_mariadb_passwordless)
        h_dbs.addWidget(btn_pg_init)
        h_dbs.addWidget(btn_pg_login)
        h_dbs.addWidget(btn_my_pwless)
        h_dbs.addStretch()
        card_dbsetup.layout.addLayout(h_dbs)
        layout.addWidget(card_dbsetup)

        layout.addStretch()
        self.setLayout(layout)
        self.refresh_domains()

    def init_postgres(self):
        # Fedora: data dir harus di-initdb sekali sebelum service bisa start
        script = (
            "if [ ! -f /var/lib/pgsql/data/PG_VERSION ]; then\n"
            "  postgresql-setup --initdb\n"
            "fi\n"
            "systemctl enable --now postgresql\n"
        )

        def done(ok):
            if ok is True:
                QMessageBox.information(self, "PostgreSQL", "PostgreSQL berhasil di-inisialisasi & dijalankan.")
            else:
                QMessageBox.critical(self, "Error", "Gagal inisialisasi PostgreSQL.")

        run_async(self, lambda: run_root_script(script), done)

    def setup_postgres_login(self):
        reply = QMessageBox.question(
            self, "PostgreSQL Login Setup",
            "Akan mengeset password user 'postgres' menjadi 'postgres' dan mengaktifkan "
            "autentikasi password (scram-sha-256) untuk koneksi localhost (agar bisa login via pgweb).\n\n"
            "Untuk server lokal/development.\nLanjutkan?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Skrip dijalankan sebagai root via pkexec (ditulis ke file, jadi tidak ada masalah paste/line-wrap)
        script = (
            "set -e\n"
            "if [ ! -f /var/lib/pgsql/data/PG_VERSION ]; then\n"
            "  postgresql-setup --initdb\n"
            "fi\n"
            "systemctl enable --now postgresql\n"
            "sudo -u postgres psql -c \"ALTER USER postgres PASSWORD 'postgres';\"\n"
            "python3 - <<'PYEOF'\n"
            "import re\n"
            "p = '/var/lib/pgsql/data/pg_hba.conf'\n"
            "s = open(p).read()\n"
            "s = re.sub(r'^(host\\s+all\\s+all\\s+(?:127\\.0\\.0\\.1/32|::1/128)\\s+)[\\w-]+', r'\\1scram-sha-256', s, flags=re.M)\n"
            "open(p, 'w').write(s)\n"
            "PYEOF\n"
            "systemctl reload postgresql\n"
        )

        def done(ok):
            if ok is True:
                QMessageBox.information(self, "PostgreSQL",
                    "Selesai! Login pgweb dengan:\n\n"
                    "  Host     : 127.0.0.1\n"
                    "  Port     : 5432\n"
                    "  Username : postgres\n"
                    "  Password : postgres\n"
                    "  Database : postgres\n"
                    "  SSL Mode : disable")
            else:
                QMessageBox.critical(self, "Error", "Gagal setup login PostgreSQL.")

        run_async(self, lambda: run_root_script(script), done)

    def setup_mariadb_passwordless(self):
        reply = QMessageBox.question(
            self, "MariaDB Passwordless",
            "Akan menjalankan MariaDB dan membuat user 'admin'@'127.0.0.1' TANPA password "
            "dengan hak akses penuh.\n\n"
            "Ini menurunkan keamanan — hanya untuk server lokal/development.\nLanjutkan?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        sql = ("CREATE USER IF NOT EXISTS 'admin'@'127.0.0.1' IDENTIFIED VIA mysql_native_password USING ''; "
               "GRANT ALL PRIVILEGES ON *.* TO 'admin'@'127.0.0.1' WITH GRANT OPTION; "
               "FLUSH PRIVILEGES;")
        script = (
            "systemctl enable --now mariadb\n"
            f'mariadb -e "{sql}"\n'
        )

        def done(ok):
            if ok is True:
                QMessageBox.information(self, "MariaDB",
                    "Selesai! Login phpMyAdmin dengan:\n\n"
                    "  Server   : 127.0.0.1\n  Username : admin\n  Password : (kosong)\n\n"
                    "Pastikan sudah klik 'Setup / Repair' phpMyAdmin agar AllowNoPassword aktif.")
            else:
                QMessageBox.critical(self, "Error", "Gagal setup passwordless MariaDB.")

        run_async(self, lambda: run_root_script(script), done)

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
        dom = self.inp_dom.text().strip()
        path = self.inp_path.text().strip()

        if not validate_domain(dom):
            QMessageBox.critical(self, "Error", "Domain tidak valid! (mis. myapp.test)")
            return
        if not validate_path(path):
            QMessageBox.critical(self, "Error", "Path tidak valid!")
            return
        if not os.path.exists(path):
            QMessageBox.critical(self, "Error", "Path tidak ditemukan di sistem!")
            return

        path_escaped = shlex.quote(path)
        # Marker '# loli-vhost' dipakai untuk mendata & menghapus domain bikinan panel
        vhost_content = (
            f"# loli-vhost {dom}\n"
            "<VirtualHost *:80>\n"
            f"    ServerName {dom}\n"
            f"    DocumentRoot {path}\n"
            f"    <Directory {path}>\n"
            "        Options Indexes FollowSymLinks\n"
            "        AllowOverride All\n"
            "        Require all granted\n"
            "    </Directory>\n"
            "</VirtualHost>\n"
        )
        script = (
            f"cat << 'LOLIEOF' > /etc/httpd/conf.d/{dom}.conf\n"
            f"{vhost_content}"
            "LOLIEOF\n"
            # tambahkan ke /etc/hosts bila belum ada (fixed-string, whole-line)
            f"grep -qxF '127.0.0.1 {dom}' /etc/hosts || echo '127.0.0.1 {dom}' >> /etc/hosts\n"
            f"command -v semanage >/dev/null 2>&1 && semanage fcontext -a -t httpd_sys_content_t {path_escaped}'(/.*)?' 2>/dev/null\n"
            f"command -v restorecon >/dev/null 2>&1 && restorecon -R {path_escaped}\n"
            "systemctl reload httpd\n"
        )

        def done(ok):
            if ok is True:
                QMessageBox.information(self, "Success",
                    f"Domain dibuat!\n\nhttp://{dom}\n(otomatis ditambahkan ke /etc/hosts)")
                self.inp_dom.clear()
            else:
                QMessageBox.critical(self, "Error", "Gagal membuat domain (lihat log).")
            self.refresh_domains()

        run_async(self, lambda: run_root_script(script), done)

    def refresh_domains(self):
        # Data domain dari file conf.d yang punya marker '# loli-vhost'
        self.dom_table.setRowCount(0)
        domains = []
        for conf in sorted(glob.glob("/etc/httpd/conf.d/*.conf")):
            try:
                with open(conf) as f:
                    text = f.read()
            except Exception:
                continue
            if "# loli-vhost" not in text:
                continue
            dom = ""
            root = ""
            for line in text.splitlines():
                ls = line.strip()
                if ls.startswith("ServerName"):
                    dom = ls.split(None, 1)[-1].strip()
                elif ls.startswith("DocumentRoot"):
                    root = ls.split(None, 1)[-1].strip().strip('"')
            if dom:
                domains.append((dom, root))
        for dom, root in domains:
            r = self.dom_table.rowCount(); self.dom_table.insertRow(r)
            self.dom_table.setItem(r, 0, QTableWidgetItem("  " + dom))
            self.dom_table.setItem(r, 1, QTableWidgetItem(root))
            b = QPushButton("Hapus"); b.setObjectName("BtnDanger"); b.setFixedWidth(80)
            b.clicked.connect(lambda _, d=dom: self.delete_domain(d))
            cell = QWidget(); cl = QHBoxLayout(cell); cl.setContentsMargins(6, 3, 6, 3); cl.addWidget(b)
            self.dom_table.setCellWidget(r, 2, cell)

    def delete_domain(self, dom: str):
        if not validate_domain(dom):
            return
        if QMessageBox.warning(self, "Hapus Domain", f"Hapus virtual host '{dom}' dan entri /etc/hosts-nya?",
                               QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        dom_sed = dom.replace('.', r'\.')
        script = (
            f"rm -f /etc/httpd/conf.d/{dom}.conf\n"
            f"sed -i '/^127\\.0\\.0\\.1[[:space:]]\\+{dom_sed}$/d' /etc/hosts\n"
            "systemctl reload httpd\n"
        )

        def done(ok):
            if ok is not True:
                QMessageBox.critical(self, "Error", "Gagal menghapus domain.")
            self.refresh_domains()

        run_async(self, lambda: run_root_script(script), done)

class ProjectsPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(); layout.setContentsMargins(20, 20, 20, 20); layout.setSpacing(15)
        header = QHBoxLayout()
        header.addWidget(title_block("Projects", "Manage your virtual hosts"))
        header.addStretch()
        btn_refresh = QPushButton(" Refresh"); btn_refresh.setObjectName("BtnGhost")
        if HAS_ICONS: btn_refresh.setIcon(app_icon("fa5s.sync", color="#334155"))
        btn_refresh.clicked.connect(self.scan)
        header.addWidget(btn_refresh)
        layout.addLayout(header)

        card = Card()
        self.lbl_root = QLabel(); self.lbl_root.setObjectName("Hint")
        card.layout.addWidget(self.lbl_root)
        self.table = QTableWidget(); self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Project", "Type", "Actions"])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(46)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        card.layout.addWidget(self.table)
        layout.addWidget(card)
        self.setLayout(layout)
        self.scan()

    def detect_type(self, path: str) -> str:
        def has(*names): return any(os.path.exists(os.path.join(path, n)) for n in names)
        if has("artisan"): return "Laravel"
        if has("wp-config.php", "wp-load.php", "wp-config-sample.php"): return "WordPress"
        if has("go.mod"): return "Go"
        if has("manage.py"): return "Django"
        if has("requirements.txt", "pyproject.toml"): return "Python"
        if has("composer.json"): return "PHP (Composer)"
        if has("package.json"): return "Node.js"
        try:
            files = os.listdir(path)
            if any(f.endswith(".php") for f in files): return "PHP"
            if any(f.endswith((".html", ".htm")) for f in files): return "Static"
        except Exception:
            pass
        return "Folder"

    def _action_btn(self, icon, tip, fn):
        b = QPushButton(); b.setFixedSize(32, 30); b.setCursor(Qt.CursorShape.PointingHandCursor); b.setToolTip(tip)
        b.setObjectName("BtnGhost")
        if HAS_ICONS: b.setIcon(app_icon(icon, color="#334155"))
        b.clicked.connect(fn)
        return b

    def scan(self):
        root = get_web_root()
        self.lbl_root.setText(f"Web root: {root}")
        self.table.setRowCount(0)
        try:
            entries = sorted([d for d in os.listdir(root)
                              if os.path.isdir(os.path.join(root, d)) and not d.startswith('.')])
        except Exception as e:
            entries = []
            logging.warning(f"Failed to list projects: {e}")
        for name in entries:
            path = os.path.join(root, name)
            r = self.table.rowCount(); self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem("  " + name))
            self.table.setItem(r, 1, QTableWidgetItem(self.detect_type(path)))
            cell = QWidget(); cl = QHBoxLayout(cell); cl.setContentsMargins(6, 4, 6, 4); cl.setSpacing(6)
            cl.addWidget(self._action_btn("fa5s.globe", "Buka di browser", lambda _, n=name: webbrowser.open(f"http://localhost/{n}/")))
            cl.addWidget(self._action_btn("fa5s.folder-open", "Buka folder", lambda _, p=path: open_path(p)))
            cl.addWidget(self._action_btn("fa5s.terminal", "Buka terminal", lambda _, p=path: open_terminal(p)))
            cl.addWidget(self._action_btn("fa5s.code", "Buka editor", lambda _, p=path: open_editor(p)))
            self.table.setCellWidget(r, 2, cell)


class DiscoveryPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(); layout.setContentsMargins(20, 20, 20, 20); layout.setSpacing(15)
        header = QHBoxLayout()
        header.addWidget(title_block("Discovery", "Detected sites & databases"))
        header.addStretch()
        btn_refresh = QPushButton(" Refresh"); btn_refresh.setObjectName("BtnGhost")
        if HAS_ICONS: btn_refresh.setIcon(app_icon("fa5s.sync", color="#334155"))
        btn_refresh.clicked.connect(self.scan)
        header.addWidget(btn_refresh)
        layout.addLayout(header)

        card = Card()
        self.table = QTableWidget(); self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Item", "Path", "Status", ""])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        card.layout.addWidget(self.table)
        layout.addWidget(card)
        self.setLayout(layout)
        self.scan()

    def items(self):
        return [
            ("Web Root", get_web_root()),
            ("Apache Config", "/etc/httpd/conf/httpd.conf"),
            ("Apache conf.d", "/etc/httpd/conf.d"),
            ("Nginx Config", "/etc/nginx/nginx.conf"),
            ("PHP ini", "/etc/php.ini"),
            ("PHP-FPM pool", "/etc/php-fpm.d/www.conf"),
            ("PHP ext dir", "/etc/php.d"),
            ("MariaDB Config", "/etc/my.cnf.d/mariadb-server.cnf"),
            ("MariaDB Data", "/var/lib/mysql"),
            ("PostgreSQL Data", "/var/lib/pgsql/data"),
            ("PostgreSQL Config", "/var/lib/pgsql/data/postgresql.conf"),
            ("Hosts File", "/etc/hosts"),
            ("pgweb binary", os.path.join(DATA_DIR, "pgweb_linux_amd64")),
            ("mailpit binary", os.path.join(DATA_DIR, "mailpit")),
            ("phpMyAdmin", os.path.join(DATA_DIR, "phpmyadmin")),
            ("php", shutil.which("php") or "php (tidak ada)"),
            ("mariadb", shutil.which("mariadb") or "mariadb (tidak ada)"),
            ("psql", shutil.which("psql") or "psql (tidak ada)"),
        ]

    def scan(self):
        self.table.setRowCount(0)
        for name, path in self.items():
            exists = os.path.exists(path)
            r = self.table.rowCount(); self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem("  " + name))
            self.table.setItem(r, 1, QTableWidgetItem(path))
            st = QTableWidgetItem("● Ada" if exists else "○ Tidak ada")
            st.setForeground(QColor("#27ae60") if exists else QColor("#94a3b8"))
            self.table.setItem(r, 2, st)
            if exists:
                b = QPushButton("Open"); b.setObjectName("BtnGhost"); b.setFixedWidth(80)
                b.clicked.connect(lambda _, p=path: open_path(p if os.path.isdir(p) else os.path.dirname(p)))
                cell = QWidget(); cl = QHBoxLayout(cell); cl.setContentsMargins(6, 3, 6, 3); cl.addWidget(b)
                self.table.setCellWidget(r, 3, cell)


class ProcessPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(); layout.setContentsMargins(20, 20, 20, 20); layout.setSpacing(15)
        header = QHBoxLayout()
        header.addWidget(title_block("Process Monitor", "Live processes & resource usage"))
        header.addStretch()
        self.search = QLineEdit(); self.search.setPlaceholderText("Filter nama proses..."); self.search.setFixedWidth(240)
        self.search.textChanged.connect(self.populate)
        btn_refresh = QPushButton(" Refresh"); btn_refresh.setObjectName("BtnGhost")
        if HAS_ICONS: btn_refresh.setIcon(app_icon("fa5s.sync", color="#334155"))
        btn_refresh.clicked.connect(self.refresh)
        header.addWidget(self.search); header.addWidget(btn_refresh)
        layout.addLayout(header)

        card = Card()
        self.table = QTableWidget(); self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["PID", "Name", "User", "CPU%", "MEM%", "Action"])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for i in (2, 3, 4, 5):
            h.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        card.layout.addWidget(self.table)
        layout.addWidget(card)
        self.setLayout(layout)
        self._procs = []
        self.refresh()

    def refresh(self):
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent']):
            try:
                info = p.info
                procs.append((info['pid'], info.get('name') or '?', info.get('username') or '?',
                              info.get('cpu_percent') or 0.0, info.get('memory_percent') or 0.0))
            except Exception:
                continue
        procs.sort(key=lambda x: x[4], reverse=True)
        self._procs = procs
        self.populate()

    def populate(self):
        flt = self.search.text().lower().strip()
        self.table.setRowCount(0)
        shown = 0
        for pid, name, user, cpu, mem in self._procs:
            if flt and flt not in name.lower():
                continue
            r = self.table.rowCount(); self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(pid)))
            self.table.setItem(r, 1, QTableWidgetItem(name))
            self.table.setItem(r, 2, QTableWidgetItem(user))
            self.table.setItem(r, 3, QTableWidgetItem(f"{cpu:.1f}"))
            self.table.setItem(r, 4, QTableWidgetItem(f"{mem:.1f}"))
            b = QPushButton("Kill"); b.setObjectName("BtnDanger"); b.setFixedWidth(70)
            b.clicked.connect(lambda _, pp=pid, nn=name: self.kill(pp, nn))
            cell = QWidget(); cl = QHBoxLayout(cell); cl.setContentsMargins(6, 3, 6, 3); cl.addWidget(b)
            self.table.setCellWidget(r, 5, cell)
            shown += 1
            if shown >= 400:
                break

    def kill(self, pid: int, name: str):
        if QMessageBox.warning(self, "Kill Process", f"Hentikan '{name}' (PID {pid})?",
                               QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            psutil.Process(pid).terminate()
            QTimer.singleShot(600, self.refresh)
        except psutil.AccessDenied:
            def work():
                return subprocess.run(["pkexec", "kill", "-9", str(pid)], timeout=30).returncode
            def done(_):
                self.refresh()
            run_async(self, work, done)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Gagal kill: {e}")


class LogsPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(); layout.setContentsMargins(20, 20, 20, 20); layout.setSpacing(15)
        header = QHBoxLayout()
        header.addWidget(title_block("Logs", "Server & application logs"))
        header.addStretch()
        btn_refresh = QPushButton(" Refresh"); btn_refresh.setObjectName("BtnGhost")
        if HAS_ICONS: btn_refresh.setIcon(app_icon("fa5s.sync", color="#334155"))
        btn_refresh.clicked.connect(self.load_current)
        header.addWidget(btn_refresh)
        layout.addLayout(header)

        card = Card()
        self.tabs = QTabWidget()
        sources = [
            ("Apache", ["journalctl", "-u", "httpd", "-n", "300", "--no-pager"]),
            ("PHP-FPM", ["journalctl", "-u", "php-fpm", "-n", "300", "--no-pager"]),
            ("MariaDB", ["journalctl", "-u", "mariadb", "-n", "300", "--no-pager"]),
            ("PostgreSQL", ["journalctl", "-u", "postgresql", "-n", "300", "--no-pager"]),
            ("Nginx", ["journalctl", "-u", "nginx", "-n", "300", "--no-pager"]),
        ]
        self.viewers = {}
        for title, cmd in sources:
            ed = QTextEdit(); ed.setReadOnly(True)
            ed.setStyleSheet("background-color:#1e1e1e; color:#dcdcdc; font-family:monospace; font-size:12px; border-radius:5px;")
            self.tabs.addTab(ed, title)
            self.viewers[title] = (ed, cmd)
        card.layout.addWidget(self.tabs)
        layout.addWidget(card)
        self.setLayout(layout)
        self.tabs.currentChanged.connect(lambda _: self.load_current())
        QTimer.singleShot(300, self.load_current)

    def load_current(self):
        title = self.tabs.tabText(self.tabs.currentIndex())
        ed, cmd = self.viewers[title]
        ed.setPlainText("Loading...")

        def work():
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            return (r.stdout or "") + (("\n" + r.stderr) if r.stderr else "")

        def done(out):
            if isinstance(out, Exception):
                ed.setPlainText(f"Error: {out}")
            else:
                ed.setPlainText(out or "(kosong)")
                ed.verticalScrollBar().setValue(ed.verticalScrollBar().maximum())

        run_async(self, work, done)


class AboutPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(); layout.setContentsMargins(20, 20, 20, 20); layout.setSpacing(15)
        layout.addWidget(title_block("About", "Loli — local development panel"))

        card = Card()
        inner = QVBoxLayout()
        inner.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        inner.setSpacing(8)
        logo = QLabel(); logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pm = load_logo_pixmap(96)
        if pm is not None and not pm.isNull():
            logo.setFixedHeight(104)
            logo.setPixmap(pm)
            inner.addWidget(logo)
        name = QLabel(APP_NAME); name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setStyleSheet("font-size: 22px; font-weight: bold; color: #1e293b;")
        inner.addWidget(name)
        ver = QLabel(f"Versi {APP_VERSION}"); ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setStyleSheet("font-size: 14px; color: #3b82f6; font-weight: bold;")
        inner.addWidget(ver)
        desc = QLabel("Panel desktop untuk mengelola environment web development lokal di Linux (Fedora-first).")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter); desc.setWordWrap(True); desc.setObjectName("Hint")
        inner.addWidget(desc)
        gh_row = QHBoxLayout()
        gh_row.addStretch()
        btn_gh = QPushButton(" github.com/s4rt4/loli")
        btn_gh.setObjectName("BtnGhost")
        btn_gh.setCursor(Qt.CursorShape.PointingHandCursor)
        if HAS_ICONS: btn_gh.setIcon(app_icon("fa5b.github", color="#1e293b"))
        btn_gh.clicked.connect(lambda: webbrowser.open("https://github.com/s4rt4/loli"))
        gh_row.addWidget(btn_gh)
        gh_row.addStretch()
        inner.addLayout(gh_row)
        card.layout.addLayout(inner)
        layout.addWidget(card)

        info = Card()
        info.layout.addWidget(QLabel("System Info", objectName="H1"))
        for k, v in self.sysinfo():
            row = QHBoxLayout()
            lk = QLabel(k); lk.setFixedWidth(140); lk.setStyleSheet("color: #7f8c8d;")
            lv = QLabel(v); lv.setStyleSheet("font-weight: 600; color: #1e293b;")
            row.addWidget(lk); row.addWidget(lv); row.addStretch()
            info.layout.addLayout(row)
        layout.addWidget(info)

        layout.addStretch()
        self.setLayout(layout)

    def sysinfo(self):
        import platform
        from PyQt6.QtCore import QT_VERSION_STR
        distro = "Linux"
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        distro = line.split("=", 1)[1].strip().strip('"')
                        break
        except Exception:
            pass
        return [
            ("Aplikasi", f"{APP_NAME}  v{APP_VERSION}"),
            ("OS", distro),
            ("Kernel", platform.release()),
            ("Python", platform.python_version()),
            ("Qt", QT_VERSION_STR),
        ]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        if os.path.exists(LOGO_PATH):
            self.setWindowIcon(QIcon(TRAY_ICON_PATH))
        self.resize(1050, 780)
        # minimum kecil supaya bisa di-snap/tiling (setengah layar) & di-resize bebas
        self.setMinimumSize(640, 520)
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
        
        brand = QWidget()
        brand_lay = QVBoxLayout(brand)
        brand_lay.setContentsMargins(0, 14, 0, 20)
        brand_lay.setSpacing(0)
        _logo_pm = load_logo_pixmap(60, path=TRAY_ICON_PATH)
        if _logo_pm is not None and not _logo_pm.isNull():
            logo_lbl = QLabel()
            logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_lbl.setFixedHeight(72)
            logo_lbl.setPixmap(_logo_pm)
            brand_lay.addWidget(logo_lbl)
        side_lay.addWidget(brand)
        
        self.menu_specs = [
            ("Dashboard", "fa5s.tachometer-alt", DashboardPage, "dashboard"),
            ("Projects", "fa5s.folder", ProjectsPage, "project"),
            ("Preferences", "fa5s.cogs", PrefsPage, "preference"),
            ("PHP Manager", "fa5b.php", PhpPage, "php"),
            ("Port Sniper", "fa5s.crosshairs", SniperPage, "port"),
            ("Processes", "fa5s.microchip", ProcessPage, "process"),
            ("Config Editor", "fa5s.edit", EditorPage, "config"),
            ("Logs", "fa5s.file-alt", LogsPage, "log"),
            ("Discovery", "fa5s.compass", DiscoveryPage, "discover"),
            ("Utilities", "fa5s.tools", UtilsPage, "utilities"),
            ("About", "fa5s.info-circle", AboutPage, "about"),
        ]
        self.menu_btns = []
        for label, icon, _cls, svg in self.menu_specs:
            b = self.mk_btn(label, icon, svg)
            self.menu_btns.append(b)
            side_lay.addWidget(b)

        side_lay.addStretch()

        sys_frame = QFrame()
        sys_lay = QVBoxLayout(sys_frame)
        sys_lay.setContentsMargins(15, 10, 15, 10)
        sys_lay.setSpacing(8)
        
        lbl_sys = QLabel("SYSTEM RESOURCES")
        lbl_sys.setStyleSheet("color: #7f8c8d; font-size: 11px; font-weight: bold; margin-bottom: 5px;")
        sys_lay.addWidget(lbl_sys)

        self.side_bars = {}
        for label, color in [("CPU", "#3b82f6"), ("RAM", "#22c55e"), ("DISK", "#f1c40f")]:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #cbd5e1; font-size: 10px; font-weight: bold;")
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
        for _label, _icon, cls, _svg in self.menu_specs:
            self.stack.addWidget(cls())
        # Bungkus konten dalam scroll area agar window bisa mengecil -> snap/tiling GNOME jalan
        content_scroll = QScrollArea()
        content_scroll.setWidgetResizable(True)
        content_scroll.setFrameShape(QFrame.Shape.NoFrame)
        content_scroll.setWidget(self.stack)
        main_lay.addWidget(content_scroll)

        for idx, b in enumerate(self.menu_btns):
            b.clicked.connect(lambda checked, i=idx: self.stack.setCurrentIndex(i))
        self.menu_btns[0].setChecked(True)
        
        self.setup_tray_icon()
        
        self.global_timer = QTimer()
        self.global_timer.timeout.connect(self.update_sidebar_resources)
        self.global_timer.start(2000)
        self.update_sidebar_resources()

        # XFCE / WM minimalis kadang tak menjalankan agen polkit -> pkexec gagal diam-diam. Cek sekali.
        QTimer.singleShot(1500, self._check_polkit_agent)

    def _check_polkit_agent(self):
        if not shutil.which("pkexec") or polkit_agent_running():
            return
        try:
            self.stack.widget(0).console.append(
                "[WARNING] Agen autentikasi polkit tidak terdeteksi — aksi root via pkexec mungkin gagal. "
                "Jalankan salah satu agen (mis. 'lxpolkit')."
            )
        except Exception:
            pass
        QMessageBox.warning(
            self, "Agen polkit tidak ditemukan",
            "Tidak terdeteksi agen autentikasi polkit yang berjalan.\n\n"
            "Loli memakai 'pkexec' untuk aksi yang butuh akses root (start/stop service, "
            "install paket, edit konfigurasi). Tanpa agen polkit, dialog password tidak muncul "
            "dan aksi tersebut akan gagal.\n\n"
            "Umum terjadi di XFCE / window manager minimalis. Jalankan salah satu agen, mis.:\n"
            "  • lxpolkit\n"
            "  • /usr/libexec/polkit-gnome-authentication-agent-1\n"
            "  • mate-polkit / xfce-polkit\n\n"
            "Tip: tambahkan ke autostart sesi desktop Anda."
        )

    @staticmethod
    def _load_color(v):
        if v < 60: return "#22c55e"
        if v < 85: return "#f1c40f"
        return "#ef4444"

    def update_sidebar_resources(self):
        try:
            vals = {
                "CPU": int(psutil.cpu_percent()),
                "RAM": int(psutil.virtual_memory().percent),
                "DISK": int(psutil.disk_usage('/').percent),
            }
            for key, v in vals.items():
                bar = self.side_bars[key]
                bar.setValue(v)
                c = self._load_color(v)
                if bar.property("barColor") != c:
                    bar.setProperty("barColor", c)
                    bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {c}; border-radius: 4px; }}")
        except Exception as e:
            logging.warning(f"Failed to update system resources: {e}")

    def mk_btn(self, text: str, icon: str, svg: str = None) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("MenuBtn")
        btn.setCheckable(True)
        btn.setAutoExclusive(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        normal = svg_icon(svg, "#cbd5e1") if svg else None
        if normal is not None:
            active = svg_icon(svg, "white") or normal
            btn.setIcon(normal)
            btn._nav_icons = (normal, active)
            btn.toggled.connect(lambda checked, b=btn: b.setIcon(b._nav_icons[1] if checked else b._nav_icons[0]))
        elif HAS_ICONS:
            btn.setIcon(app_icon(icon, color="white" if "php" in icon else "#cbd5e1"))
        return btn

    def setup_tray_icon(self):
        # GNOME modern sering tanpa system tray -> deteksi agar window tidak "hilang"
        self.has_tray = QSystemTrayIcon.isSystemTrayAvailable()
        self.tray_icon = QSystemTrayIcon(self)
        icon_path = TRAY_ICON_PATH if os.path.exists(TRAY_ICON_PATH) else LOGO_PATH
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            self.tray_icon.setIcon(QIcon.fromTheme("utilities-system-monitor", QIcon("")))
        self.tray_icon.setToolTip(APP_NAME)

        def add(menu, text, icon, fn):
            a = menu.addAction(text)
            if HAS_ICONS:
                a.setIcon(app_icon(icon, color="#1e293b"))
            a.triggered.connect(fn)
            return a

        menu = QMenu()
        add(menu, "Open Panel", "fa5s.window-maximize", self.show_panel)
        menu.addSeparator()
        add(menu, "Start All Services", "fa5s.play", self.start_all_services)
        add(menu, "Stop All Services", "fa5s.stop", self.stop_all_services)
        menu.addSeparator()
        add(menu, "Open Localhost", "fa5s.globe", lambda: webbrowser.open("http://localhost"))
        add(menu, "Open phpMyAdmin", "fa5s.database", lambda: webbrowser.open("http://localhost/phpmyadmin"))
        add(menu, "Open pgweb", "fa5s.table", lambda: webbrowser.open(f"http://localhost:{PGWEB_PORT}"))
        add(menu, "Open www Folder", "fa5s.folder-open", lambda: open_path(get_web_root()))
        add(menu, "Open Terminal", "fa5s.terminal", lambda: open_terminal(get_web_root()))
        menu.addSeparator()
        add(menu, "Quit Loli", "fa5s.power-off", self.force_quit)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_panel()

    def show_panel(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def start_all_services(self):
        # httpd (bukan nginx, hindari konflik :80) + database, satu prompt
        script = "for s in httpd mariadb postgresql valkey memcached mongod; do systemctl start $s 2>/dev/null || true; done\n"

        def done(_):
            self.tray_icon.showMessage(APP_NAME, "Start All Services dijalankan.",
                                       QSystemTrayIcon.MessageIcon.Information, 2500)

        run_async(self, lambda: run_root_script(script), done)

    def stop_all_services(self):
        script = "for s in httpd nginx mariadb postgresql valkey memcached mongod; do systemctl stop $s 2>/dev/null || true; done\n"

        def done(_):
            self.tray_icon.showMessage(APP_NAME, "Stop All Services dijalankan.",
                                       QSystemTrayIcon.MessageIcon.Information, 2500)

        run_async(self, lambda: run_root_script(script), done)

    def closeEvent(self, event):
        if self.is_quitting:
            if hasattr(self, 'global_timer'):
                self.global_timer.stop()
            event.accept()
            return
        if getattr(self, 'has_tray', False):
            # Ada system tray -> sembunyikan ke tray
            event.ignore()
            self.hide()
            self.tray_icon.showMessage("Berjalan di Background",
                                       "Loli disembunyikan ke tray. Klik ikon tray untuk membuka.",
                                       QSystemTrayIcon.MessageIcon.Information, 2500)
        else:
            # Tidak ada tray (GNOME default) -> minimize supaya window tidak hilang
            event.ignore()
            self.showMinimized()

    def force_quit(self):
        self.is_quitting = True
        dash = self.stack.widget(0)
        if hasattr(dash, 'stop_pgweb'):
            try: dash.stop_pgweb()
            except Exception as e: logging.warning(f"Failed to stop pgweb on quit: {e}")
        if hasattr(dash, 'stop_mailpit'):
            try: dash.stop_mailpit()
            except Exception as e: logging.warning(f"Failed to stop mailpit on quit: {e}")
        if hasattr(self, 'global_timer'):
            self.global_timer.stop()
        QApplication.instance().quit()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Identitas app -> GNOME/Wayland mencocokkan ke loli.desktop (ikon & nama di dock, bukan "python3")
    app.setApplicationName("Loli")
    app.setApplicationDisplayName(APP_NAME)
    app.setDesktopFileName("loli")
    if os.path.exists(LOGO_PATH):
        app.setWindowIcon(QIcon(TRAY_ICON_PATH))
    app.setQuitOnLastWindowClosed(False)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())