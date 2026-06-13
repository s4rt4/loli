"""All panel pages.

Distro-specific behaviour is routed through PLAT (a Platform descriptor) and
loli.scripts. This module was unified from the per-distro web_panel.py /
web_panel_deb.py page classes; the ~10% that differed now lives behind PLAT.
"""

import glob
import logging
import os
import platform
import re
import shlex
import shutil
import socket
import subprocess
import tempfile
import webbrowser

import psutil
from PyQt6.QtCore import Qt, QSize, QTimer, QSettings
from PyQt6.QtGui import QColor, QFont, QIcon, QPixmap, QPainter
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QFrame, QMessageBox, QTextEdit, QLineEdit, QFileDialog,
                             QComboBox, QProgressBar, QGridLayout, QCheckBox, QScrollArea,
                             QStackedWidget, QButtonGroup,
                             QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget,
                             QSizePolicy)

from . import scripts
from .config import (APP_NAME, APP_VERSION, DATA_DIR, PMA_WEB_DIR, LOGO_PATH,
                     TRAY_ICON_PATH, ICON_DIR, PGWEB_PORT, MAILPIT_UI_PORT,
                     MAILPIT_SMTP_PORT)
from .platform_spec import detect
from .services import (validate_domain, validate_path, validate_port, validate_username,
                       run_root_script, run_async, get_web_root, port_in_use,
                       open_path, open_terminal, open_editor)
from .widgets import (Card, FlowLayout, title_block, svg_icon, app_icon,
                      load_logo_pixmap, HAS_ICONS)

PLAT = detect()


def _ensure_executable(path):
    """Make ``path`` runnable, tolerating files we don't own.

    The bundled pgweb/mailpit binaries may be owned by another user (e.g. root
    when they sit in a repo checkout under /var/www). chmod by a non-owner
    raises EPERM even when the file is already executable, so only chmod when
    the exec bit is actually missing, and never let a failed chmod abort start.
    """
    if os.access(path, os.X_OK):
        return
    try:
        os.chmod(path, 0o755)
    except OSError as e:
        logging.warning(f"Could not chmod {path}: {e}")


def _dl_arch():
    """Map the host CPU to the release-asset arch slug used by pgweb & mailpit
    (both ship linux amd64/arm64 builds). Returns None on unsupported arches so
    the caller can fail with a clear message instead of fetching an amd64 binary
    that won't run."""
    m = platform.machine().lower()
    if m in ("x86_64", "amd64"):
        return "amd64"
    if m in ("aarch64", "arm64"):
        return "arm64"
    return None


class DashboardPage(QWidget):
    def _cleanup_log(self, attr):
        """Delete and forget a tool's stderr temp log so /tmp doesn't accumulate
        one orphaned file per pgweb/mailpit start."""
        log = getattr(self, attr, None)
        if log is None:
            return
        try:
            if os.path.exists(log.name):
                os.remove(log.name)
        except OSError:
            pass
        setattr(self, attr, None)

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

        # Toggle tampilan list vs card (mirip Google Fonts) — mengatur kedua list
        self.view_mode = QSettings("Loli", "Loli").value("dashboard/view_mode", "list")
        if self.view_mode not in ("list", "card"):
            self.view_mode = "list"
        self.view_group = QButtonGroup(self)
        self.btn_view_list = QPushButton()
        self.btn_view_list.setObjectName("ViewToggle")
        self.btn_view_list.setCheckable(True)
        self.btn_view_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_view_list.setToolTip("List view")
        self.btn_view_card = QPushButton()
        self.btn_view_card.setObjectName("ViewToggle")
        self.btn_view_card.setCheckable(True)
        self.btn_view_card.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_view_card.setToolTip("Card view")
        self.view_group.addButton(self.btn_view_list)
        self.view_group.addButton(self.btn_view_card)
        self.btn_view_list.clicked.connect(lambda: self.set_view_mode("list"))
        self.btn_view_card.clicked.connect(lambda: self.set_view_mode("card"))
        view_box = QHBoxLayout()
        view_box.setSpacing(0)
        view_box.addWidget(self.btn_view_list)
        view_box.addWidget(self.btn_view_card)
        header.addLayout(view_box)
        header.addSpacing(10)

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

        self.card_db = Card()
        self.card_db.layout.addWidget(QLabel("Database Tools", objectName="H1"))
        self._db_body = None
        layout.addWidget(self.card_db)

        self.services = list(PLAT.services)
        # service -> package name for the Install button (when not yet installed)
        self.svc_packages = dict(PLAT.svc_packages)
        self.svc_widgets = {}

        self.card_svc = Card()
        self.card_svc.layout.addWidget(QLabel("Service Status", objectName="H1"))
        self._svc_body = None
        layout.addWidget(self.card_svc)

        # Bangun isi kedua card sesuai mode tampilan aktif (list / card)
        self._rebuild_dashboard_items()
        self.btn_view_list.setChecked(self.view_mode == "list")
        self.btn_view_card.setChecked(self.view_mode == "card")
        self._refresh_view_icons()

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

    # ----- List / Card view (toggle di header Dashboard) ------------------

    def set_view_mode(self, mode: str):
        if mode not in ("list", "card") or mode == self.view_mode:
            # Klik tombol yang sudah aktif: cukup sinkronkan state checked
            self.btn_view_list.setChecked(self.view_mode == "list")
            self.btn_view_card.setChecked(self.view_mode == "card")
            return
        self.view_mode = mode
        QSettings("Loli", "Loli").setValue("dashboard/view_mode", mode)
        self.btn_view_list.setChecked(mode == "list")
        self.btn_view_card.setChecked(mode == "card")
        self._refresh_view_icons()
        self._rebuild_dashboard_items()
        self.update_ui()

    def _refresh_view_icons(self):
        if not HAS_ICONS:
            return
        self.btn_view_list.setIcon(app_icon("fa5s.bars",
            color="white" if self.view_mode == "list" else "#64748b"))
        self.btn_view_card.setIcon(app_icon("fa5s.th-large",
            color="white" if self.view_mode == "card" else "#64748b"))

    def _rebuild_dashboard_items(self):
        db_specs = [self._create_pma_item(), self._create_pg_item(), self._create_mp_item()]
        self._fill_body(self.card_db, "_db_body", db_specs, self.view_mode)
        self.svc_widgets = {}
        svc_specs = [self._create_svc_item(s) for s in self.services]
        self._fill_body(self.card_svc, "_svc_body", svc_specs, self.view_mode)
        self.update_db_status()

    def _fill_body(self, card, attr, specs, mode):
        old = getattr(self, attr, None)
        if old is not None:
            card.layout.removeWidget(old)
            old.setParent(None)
            old.deleteLater()
        body = QWidget()
        if mode == "card":
            sp = body.sizePolicy()
            sp.setHeightForWidth(True)
            body.setSizePolicy(sp)
            flow = FlowLayout(body, margin=0, hspacing=12, vspacing=12)
            for spec in specs:
                flow.addWidget(self._arrange_card(spec))
        else:
            v = QVBoxLayout(body)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(0)
            for i, spec in enumerate(specs):
                v.addWidget(self._arrange_row(spec))
                if i < len(specs) - 1:
                    line = QFrame()
                    line.setFrameShape(QFrame.Shape.HLine)
                    line.setStyleSheet("color: #e2e8f0;")
                    v.addWidget(line)
        setattr(self, attr, body)
        card.layout.addWidget(body)

    def _arrange_row(self, spec):
        row = QHBoxLayout()
        row.setContentsMargins(8, 5, 8, 5)
        if spec["icon"] is not None:
            row.addWidget(spec["icon"])
        name = spec["name_label"]
        name.setWordWrap(False)
        name.setFixedWidth(spec["name_w"])
        row.addWidget(name)
        if spec["icon"] is not None:
            row.addSpacing(16)
        row.addWidget(spec["status"], 0, Qt.AlignmentFlag.AlignVCenter)
        row.addStretch()
        for b in spec["buttons"]:
            row.addWidget(b)
        f = QFrame(); f.setObjectName("Row"); f.setLayout(row)
        return f

    def _arrange_card(self, spec):
        card = QFrame(); card.setObjectName("ItemCard"); card.setFixedWidth(290)
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(12)
        top = QHBoxLayout(); top.setSpacing(8)
        if spec["icon"] is not None:
            top.addWidget(spec["icon"], 0, Qt.AlignmentFlag.AlignTop)
        name = spec["name_label"]
        name.setWordWrap(True)
        name.setFixedWidth(16777215)
        top.addWidget(name, 1)
        top.addWidget(spec["status"], 0, Qt.AlignmentFlag.AlignTop)
        v.addLayout(top)
        btnrow = QHBoxLayout(); btnrow.setSpacing(8)
        for b in spec["buttons"]:
            btnrow.addWidget(b)
        btnrow.addStretch()
        v.addLayout(btnrow)
        return card

    def _create_pma_item(self):
        name = QLabel("phpMyAdmin (MySQL/MariaDB)")
        name.setStyleSheet("font-weight: 600; font-size: 14px; color: #1e293b;")
        self.lbl_pma_status = QLabel("...")
        self.lbl_pma_status.setObjectName("StatusNA")
        self.lbl_pma_status.setFixedHeight(24)
        btn_open = QPushButton(" Open")
        btn_open.setObjectName("BtnPrimary")
        btn_open.setFixedWidth(92)
        if HAS_ICONS: btn_open.setIcon(app_icon("fa5s.external-link-alt", color="white"))
        btn_open.clicked.connect(lambda: webbrowser.open("http://localhost/phpmyadmin"))
        self.btn_pma_setup = QPushButton(" Setup / Repair")
        self.btn_pma_setup.setObjectName("BtnGhost")
        self.btn_pma_setup.setFixedWidth(148)
        if HAS_ICONS: self.btn_pma_setup.setIcon(app_icon("fa5s.wrench", color="#334155"))
        self.btn_pma_setup.clicked.connect(self.on_pma_action)
        return dict(name_label=name, name_w=224, icon=None,
                    status=self.lbl_pma_status, buttons=[btn_open, self.btn_pma_setup])

    def _create_pg_item(self):
        name = QLabel("pgweb (PostgreSQL)")
        name.setStyleSheet("font-weight: 600; font-size: 14px; color: #1e293b;")
        self.lbl_pg_status = QLabel("● STOPPED")
        self.lbl_pg_status.setObjectName("StatusStop")
        self.lbl_pg_status.setFixedHeight(24)
        self.btn_pg_toggle = QPushButton(" Start")
        self.btn_pg_toggle.setObjectName("BtnSuccess")
        self.btn_pg_toggle.setFixedWidth(92)
        if HAS_ICONS: self.btn_pg_toggle.setIcon(app_icon("fa5s.play", color="white"))
        self.btn_pg_toggle.clicked.connect(self.toggle_pgweb)
        btn_open = QPushButton(" Open")
        btn_open.setObjectName("BtnGhost")
        btn_open.setFixedWidth(92)
        if HAS_ICONS: btn_open.setIcon(app_icon("fa5s.external-link-alt", color="#334155"))
        btn_open.clicked.connect(lambda: webbrowser.open(f"http://localhost:{PGWEB_PORT}"))
        return dict(name_label=name, name_w=224, icon=None,
                    status=self.lbl_pg_status, buttons=[self.btn_pg_toggle, btn_open])

    def _create_mp_item(self):
        name = QLabel("Mailpit (SMTP Inbox)")
        name.setStyleSheet("font-weight: 600; font-size: 14px; color: #1e293b;")
        self.lbl_mp_status = QLabel("● STOPPED")
        self.lbl_mp_status.setObjectName("StatusStop")
        self.lbl_mp_status.setFixedHeight(24)
        self.btn_mp_toggle = QPushButton(" Start")
        self.btn_mp_toggle.setObjectName("BtnSuccess")
        self.btn_mp_toggle.setFixedWidth(92)
        if HAS_ICONS: self.btn_mp_toggle.setIcon(app_icon("fa5s.play", color="white"))
        self.btn_mp_toggle.clicked.connect(self.toggle_mailpit)
        btn_open = QPushButton(" Open")
        btn_open.setObjectName("BtnGhost")
        btn_open.setFixedWidth(92)
        if HAS_ICONS: btn_open.setIcon(app_icon("fa5s.external-link-alt", color="#334155"))
        btn_open.clicked.connect(lambda: webbrowser.open(f"http://localhost:{MAILPIT_UI_PORT}"))
        return dict(name_label=name, name_w=224, icon=None,
                    status=self.lbl_mp_status, buttons=[self.btn_mp_toggle, btn_open])

    def _create_svc_item(self, svc):
        sys_name, display_name, icon_name = svc
        lbl_icon = QLabel()
        if HAS_ICONS: lbl_icon.setPixmap(app_icon(icon_name, color="#334155").pixmap(24, 24))

        name = QLabel(display_name)
        name.setStyleSheet("font-weight: bold; font-size: 14px; color: #1e293b;")

        lbl_status = QLabel("Checking...")
        lbl_status.setObjectName("StatusNA")
        lbl_status.setFixedHeight(24)

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

        self.svc_widgets[sys_name] = {
            'status': lbl_status, 'action_stack': action_stack,
            'btn_restart': btn_restart, 'btn_install': btn_install,
            'icon': lbl_icon, 'icon_name': icon_name,
        }
        return dict(name_label=name, name_w=142, icon=lbl_icon,
                    status=lbl_status, buttons=[action_stack, btn_restart, btn_install])

    def open_root_dir(self):
        try:
            path = get_web_root(PLAT)
        except Exception as e:
            path = "/var/www/html"
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
        # MongoDB isn't in the base repos -> register the official repo first
        if svc == "mongod":
            self.console.append(f"\n> setup MongoDB repo + {PLAT.pkg_mgr} install mongodb-org...")
            script = scripts.mongo_install(PLAT)

            def done_mongo(ok):
                self.console.append("[SUCCESS] mongodb-org terpasang." if ok is True
                                    else "[ERROR] gagal install MongoDB (lihat dialog/izin).")
                self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())
                QTimer.singleShot(500, self.update_ui)

            run_async(self, lambda: run_root_script(script), done_mongo)
            return

        self.console.append(f"\n> {PLAT.pkg_mgr} install {pkg}...")

        def work():
            return subprocess.run(PLAT.install_pkg_argv(pkg),
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
            if svc == PLAT.web_svc and self.check_svc("nginx"):
                self.console.append("\n[WARNING] Matikan Nginx terlebih dahulu untuk mencegah konflik Port 80!")
                QMessageBox.warning(self, "Conflict", "Nginx sedang berjalan! Harap matikan Nginx sebelum menyalakan Apache.")
                return
            if svc == "nginx" and self.check_svc(PLAT.web_svc):
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

    @staticmethod
    def _pma_present():
        # Downloaded if it exists either in the unprivileged staging dir or in
        # the web-served location it gets relocated to during setup.
        return (os.path.exists(os.path.join(PMA_WEB_DIR, "index.php"))
                or os.path.exists(os.path.join(DATA_DIR, "phpmyadmin", "index.php")))

    def update_db_status(self):
        # phpMyAdmin: 3 state -> belum diunduh / belum setup / configured
        pma_present = self._pma_present()
        if not pma_present:
            self.lbl_pma_status.setText("○ NOT INSTALLED")
            self.lbl_pma_status.setObjectName("StatusNA")
            self.btn_pma_setup.setText(" Download")
            if HAS_ICONS: self.btn_pma_setup.setIcon(app_icon("fa5s.download", color="#334155"))
        elif PLAT.phpmyadmin_configured():
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
        dest = DATA_DIR

        def work():
            arch = _dl_arch()
            if arch is None:
                raise RuntimeError(f"arsitektur {platform.machine()} tidak didukung "
                                   "untuk Mailpit (hanya x86_64/arm64)")
            url = ("https://github.com/axllent/mailpit/releases/latest/download/"
                   f"mailpit-linux-{arch}.tar.gz")
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
        # A child we already spawned may still be binding the port; don't spawn
        # a second one and orphan the first.
        if self.mailpit_proc is not None and self.mailpit_proc.poll() is None:
            return
        binary = os.path.join(DATA_DIR, "mailpit")
        if not os.path.exists(binary):
            self.download_mailpit()
            return
        try:
            _ensure_executable(binary)
            self._cleanup_log("_mailpit_log")
            self._mailpit_log = tempfile.NamedTemporaryFile(mode='w+', suffix='.log', prefix='mailpit-', delete=False)
            self.mailpit_proc = subprocess.Popen(
                [binary, "--listen", f"127.0.0.1:{MAILPIT_UI_PORT}", "--smtp", f"127.0.0.1:{MAILPIT_SMTP_PORT}"],
                stdout=subprocess.DEVNULL, stderr=self._mailpit_log)
        except Exception as e:
            logging.error(f"Failed to start mailpit: {e}")
            QMessageBox.critical(self, "Error", f"Gagal menjalankan Mailpit: {str(e)}")
            return
        QTimer.singleShot(2500, self._check_mailpit_started)
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
            self._cleanup_log("_mailpit_log")
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
        self._cleanup_log("_mailpit_log")
        if port_in_use(MAILPIT_UI_PORT):
            try:
                subprocess.run(["pkill", "-f", os.path.join(DATA_DIR, "mailpit")], timeout=5)
            except Exception as e:
                logging.warning(f"Failed to pkill mailpit: {e}")
            if port_in_use(MAILPIT_UI_PORT):
                QMessageBox.warning(self, "Mailpit", "Port Mailpit masih dipakai proses "
                    "lain yang tidak bisa dihentikan dari sini (mungkin milik user/root lain).")
        self.update_db_status()

    def on_pma_action(self):
        # Tombol dinamis: Download bila belum ada, selain itu Setup/Repair
        if not self._pma_present():
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
            if not os.path.isfile(os.path.join(extracted, "index.php")):
                raise RuntimeError("arsip phpMyAdmin tidak lengkap (index.php tak ditemukan)")
            # Replace any previous staging copy so a re-download upgrades cleanly
            # instead of silently keeping the old tree and leaking the new one.
            if os.path.exists(target):
                shutil.rmtree(target, ignore_errors=True)
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
        staging = os.path.join(DATA_DIR, "phpmyadmin")
        # ``served`` is where Apache reads it from; the root script relocates the
        # staging copy here on a fresh install. config.inc.php must point at the
        # served location since that is where phpMyAdmin ultimately runs.
        served = PMA_WEB_DIR
        pma = served if os.path.exists(os.path.join(served, "index.php")) else staging
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
            f"$cfg['TempDir'] = '{served}/tmp';\n"
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

        served_q = shlex.quote(served)
        tmp_q = shlex.quote(tmp_path)
        script = scripts.phpmyadmin_setup(PLAT, staging, served, served_q, tmp_q)

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

        def work():
            import zipfile
            arch = _dl_arch()
            if arch is None:
                raise RuntimeError(f"arsitektur {platform.machine()} tidak didukung "
                                   "untuk pgweb (hanya x86_64/arm64)")
            url = ("https://github.com/sosedoff/pgweb/releases/latest/download/"
                   f"pgweb_linux_{arch}.zip")
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

        # A child we already spawned may still be binding the port; don't spawn
        # a second one and orphan the first.
        if self.pgweb_proc is not None and self.pgweb_proc.poll() is None:
            return

        binary = os.path.join(DATA_DIR, "pgweb_linux_amd64")
        if not os.path.exists(binary):
            QMessageBox.critical(self, "Error", f"Binary pgweb tidak ditemukan di:\n{binary}")
            return
        try:
            _ensure_executable(binary)
            # stderr ke file (bukan PIPE) supaya buffer tidak penuh & error bisa dibaca jika gagal
            self._cleanup_log("_pgweb_log")
            self._pgweb_log = tempfile.NamedTemporaryFile(mode='w+', suffix='.log', prefix='pgweb-', delete=False)
            self.pgweb_proc = subprocess.Popen(
                [binary, "--bind", "127.0.0.1", "--listen", str(PGWEB_PORT), "--sessions"],
                stdout=subprocess.DEVNULL, stderr=self._pgweb_log)
        except Exception as e:
            logging.error(f"Failed to start pgweb: {e}")
            QMessageBox.critical(self, "Error", f"Gagal menjalankan pgweb: {str(e)}")
            return
        # Cek setelah jeda: kalau proses sudah mati, tampilkan errornya
        QTimer.singleShot(2500, self._check_pgweb_started)
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
            self._cleanup_log("_pgweb_log")
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
        self._cleanup_log("_pgweb_log")
        # Bersihkan juga instance orphan yang masih memegang port
        if self._pgweb_running():
            try:
                subprocess.run(["pkill", "-f", os.path.join(DATA_DIR, "pgweb_linux_amd64")], timeout=5)
            except Exception as e:
                logging.warning(f"Failed to pkill pgweb: {e}")
            if self._pgweb_running():
                QMessageBox.warning(self, "pgweb", "Port pgweb masih dipakai proses "
                    "lain yang tidak bisa dihentikan dari sini (mungkin milik user/root lain).")
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
            out = subprocess.getoutput(f"grep -m 1 -i 'DocumentRoot' {PLAT.apache_default_vhost}")
            if "DocumentRoot" in out: self.inp_dir.setText(out.split()[-1].strip().strip('"'))
        except Exception as e:
            logging.warning(f"Failed to load document root: {e}")

        try:
            if "Listen" in (ap := subprocess.getoutput(f"grep -m 1 '^Listen' {PLAT.apache_ports_source}")): self.ports["apache2"].setText(ap.split()[-1].strip())
            if "listen" in (ng := subprocess.getoutput("grep -m 1 'listen' /etc/nginx/nginx.conf")): self.ports["nginx"].setText(ng.replace('listen','').replace(';','').strip().split()[0])
            if "port" in (ma := subprocess.getoutput(f"grep -m 1 -h '^port' {PLAT.mariadb_cnf}")): self.ports["mariadb"].setText(ma.split('=')[-1].strip())
            if "port" in (pg := subprocess.getoutput(f"grep -m 1 -h '^port' {PLAT.pg_conf_glob}")): self.ports["postgresql"].setText(pg.split('=')[-1].strip())
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
        
        php_ver = subprocess.getoutput("php -r \"echo PHP_MAJOR_VERSION.'.'.PHP_MINOR_VERSION;\" 2>/dev/null")
        if not re.match(r"^\d+\.\d+$", php_ver): php_ver = "8.4"
        ports = {k: self.ports[k].text() for k in ("nginx", "apache2", "mariadb", "postgresql", "mongod")}
        s = scripts.prefs_apply(PLAT, ndir, ports, php_ver)
        if run_root_script(s): 
            QMessageBox.information(self, "Success", "Konfigurasi disimpan! File conf telah diperbaiki.")
        else: 
            QMessageBox.critical(self, "Error", "Gagal menerapkan konfigurasi.")

    def enable_ssl(self):
        if run_root_script(scripts.enable_ssl(PLAT)):
            QMessageBox.information(self, "SSL Enabled", "SSL Berhasil diaktifkan (mod_ssl terpasang)!")
        else:
            QMessageBox.critical(self, "Error", "Gagal mengaktifkan SSL.")

    def setup_mailcatcher(self):
        script = scripts.php_mailcatcher(PLAT)
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

        if PLAT.id != "debian":
            QMessageBox.information(self, "Info",
                f"Fedora menggunakan satu PHP sistem (saat ini {target}) yang dikelola oleh dnf.\n\n"
                "Untuk berpindah versi, jalankan di terminal (mis. via repo Remi):\n"
                "  sudo dnf module reset php\n"
                "  sudo dnf module enable php:remi-8.3\n"
                "  sudo dnf install php\n\n"
                "Panel tidak mengubah versi otomatis untuk mencegah kerusakan sistem.")
            return

        if run_root_script(scripts.php_switch(PLAT, target)):
            QMessageBox.information(self, "Berhasil", f"PHP {target} sekarang aktif untuk Apache & Nginx!")
            self.check_status()
        else:
            QMessageBox.critical(self, "Error", "Gagal berpindah versi PHP.")

    def check_status(self):
        try:
            ver = subprocess.check_output(["php", "-r", "echo PHP_MAJOR_VERSION.'.'.PHP_MINOR_VERSION;"], text=True, timeout=5)
            if PLAT.id == "debian":
                ver = ver.strip()
                self.curr_ver = ver
                active = os.listdir(f"/etc/php/{ver}/cli/conf.d/")
            else:
                self.curr_ver = ver
                active = os.listdir("/etc/php.d/")
            for ext, chk in self.checks.items():
                chk.setChecked(any(ext in f for f in active))
        except Exception as e:
            logging.warning(f"Failed to check PHP status: {e}")

    def toggle_ext(self):
        chk = self.sender()
        ext = chk.text()
        if PLAT.id == "debian":
            ver = getattr(self, 'curr_ver', None) or (self.combo_php.currentText() if re.match(r'^\d+\.\d+$', self.combo_php.currentText()) else "8.2")
            act = "phpenmod" if chk.isChecked() else "phpdismod"
            try:
                res = subprocess.run(
                    ["pkexec", "sh", "-c",
                     f"{act} -v {shlex.quote(ver)} {shlex.quote(ext)} && (systemctl restart apache2 || true) && (systemctl restart php{shlex.quote(ver)}-fpm || true)"],
                    timeout=300)
                if res.returncode != 0:
                    QMessageBox.warning(self, "Gagal", f"Operasi '{act} {ext}' gagal (ekstensi tidak tersedia atau dibatalkan).")
            except Exception as e:
                logging.error(f"Failed to toggle extension: {e}")
                QMessageBox.critical(self, "Error", f"Gagal toggle extension: {str(e)}")
            self.check_status()
            return
        # Fedora: extension -> package map. None = built-in, can't toggle separately.
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
        
        self.files = PLAT.config_files()

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
        script = scripts.pg_init(PLAT)

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

        script = scripts.pg_login(PLAT)

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
        script = scripts.mariadb_passwordless(sql)

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
            f"    DocumentRoot {path_escaped}\n"
            f"    <Directory {path_escaped}>\n"
            "        Options Indexes FollowSymLinks\n"
            "        AllowOverride All\n"
            "        Require all granted\n"
            "    </Directory>\n"
            "</VirtualHost>\n"
        )
        script = scripts.vhost_create(PLAT, dom, path_escaped, vhost_content)

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
        for conf in sorted(glob.glob(f"{PLAT.apache_conf_dir}/*.conf")):
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
        script = scripts.vhost_delete(PLAT, dom, dom_sed)

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
        root = get_web_root(PLAT)
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
        return [("Web Root", get_web_root(PLAT))] + PLAT.reference_paths() + [
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
        sources = PLAT.log_units()
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
        desc = QLabel("Panel desktop untuk mengelola environment web development lokal di Linux.")
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


