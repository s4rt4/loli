"""Main window, system tray, and the application entry point."""

import logging
import os
import shutil
import sys
import webbrowser

import psutil
from PyQt6.QtCore import Qt, QTimer, QSettings
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QPushButton, QFrame, QMessageBox,
                             QStackedWidget, QProgressBar, QScrollArea, QSystemTrayIcon,
                             QMenu)

from .config import APP_NAME, LOGO_PATH, TRAY_ICON_PATH, PGWEB_PORT
from .platform_spec import detect
from .services import (run_root_script, run_async, get_web_root, open_path,
                       open_terminal, polkit_agent_running)
from .theme import STYLESHEET
from .widgets import load_logo_pixmap, svg_icon, app_icon, HAS_ICONS
from .pages import (DashboardPage, SniperPage, PrefsPage, PhpPage, EditorPage,
                    UtilsPage, ProjectsPage, DiscoveryPage, ProcessPage, LogsPage,
                    AboutPage)

PLAT = detect()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        if os.path.exists(TRAY_ICON_PATH):
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
        self.sidebar = sidebar
        side_lay = QVBoxLayout()
        side_lay.setContentsMargins(0,20,0,20)

        # Tombol collapse/expand sidebar (hamburger), rata kanan saat expanded
        toggle_row = QHBoxLayout()
        toggle_row.setContentsMargins(12, 0, 12, 0)
        self.btn_collapse = QPushButton()
        self.btn_collapse.setObjectName("SidebarToggle")
        self.btn_collapse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_collapse.setToolTip("Collapse / expand sidebar")
        self.btn_collapse.clicked.connect(self.toggle_sidebar)
        toggle_row.addStretch()
        toggle_row.addWidget(self.btn_collapse)
        side_lay.addLayout(toggle_row)

        brand = QWidget()
        self.brand = brand
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
        self.sys_frame = sys_frame
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

        # Pulihkan kondisi sidebar (collapsed/expanded) dari sesi sebelumnya
        collapsed = QSettings("Loli", "Loli").value("sidebar/collapsed", False, type=bool)
        self.sidebar_collapsed = False
        self._apply_collapsed(collapsed)

        self.setup_tray_icon()
        
        self.global_timer = QTimer()
        self.global_timer.timeout.connect(self.update_sidebar_resources)
        self.global_timer.start(2000)
        self.update_sidebar_resources()

        # XFCE / WM minimalis kadang tak menjalankan agen polkit -> pkexec gagal diam-diam. Cek sekali.
        QTimer.singleShot(1500, self._check_polkit_agent)

    def toggle_sidebar(self):
        self._apply_collapsed(not self.sidebar_collapsed)

    def _apply_collapsed(self, collapsed: bool):
        self.sidebar_collapsed = collapsed
        self.sidebar.setFixedWidth(64 if collapsed else 230)
        # Logo & panel system resources hanya relevan saat lebar penuh
        self.brand.setVisible(not collapsed)
        self.sys_frame.setVisible(not collapsed)
        for b in self.menu_btns:
            b.setText("" if collapsed else b._full_text)
            b.setToolTip(b._full_text if collapsed else "")
            b.setProperty("collapsed", collapsed)
            b.style().unpolish(b)
            b.style().polish(b)
        icon = "fa5s.angle-double-right" if collapsed else "fa5s.angle-double-left"
        self.btn_collapse.setIcon(svg_icon(icon, "#cbd5e1") or app_icon(icon, color="#cbd5e1"))
        QSettings("Loli", "Loli").setValue("sidebar/collapsed", collapsed)

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
        btn._full_text = text
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
        # GNOME modern sering tanpa system tray -> deteksi agar window tidak "hilang".
        # Tanpa tray, JANGAN buat/`show()` QSystemTrayIcon: di GNOME hal itu memicu
        # "QDBusTrayIcon ... ServiceUnknown" karena tak ada StatusNotifier host.
        self.has_tray = QSystemTrayIcon.isSystemTrayAvailable()
        if not self.has_tray:
            self.tray_icon = None
            return
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
        add(menu, "Open www Folder", "fa5s.folder-open", lambda: open_path(get_web_root(PLAT)))
        add(menu, "Open Terminal", "fa5s.terminal", lambda: open_terminal(get_web_root(PLAT)))
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
        # web server (not nginx, avoid :80 conflict) + databases, one prompt
        script = PLAT.start_all_script()

        def done(_):
            if self.tray_icon is not None:
                self.tray_icon.showMessage(APP_NAME, "Start All Services dijalankan.",
                                           QSystemTrayIcon.MessageIcon.Information, 2500)

        run_async(self, lambda: run_root_script(script), done)

    def stop_all_services(self):
        script = PLAT.stop_all_script()

        def done(_):
            if self.tray_icon is not None:
                self.tray_icon.showMessage(APP_NAME, "Stop All Services dijalankan.",
                                           QSystemTrayIcon.MessageIcon.Information, 2500)

        run_async(self, lambda: run_root_script(script), done)

    def closeEvent(self, event):
        if self.is_quitting:
            if hasattr(self, 'global_timer'):
                self.global_timer.stop()
            event.accept()
            return
        # Re-check the tray live: has_tray is a startup snapshot, and hiding to a
        # tray whose host has since died would lose the window with no way back.
        if (getattr(self, 'has_tray', False) and self.tray_icon is not None
                and QSystemTrayIcon.isSystemTrayAvailable()):
            event.ignore()
            self.hide()
            self.tray_icon.showMessage("Berjalan di Background",
                                       "Loli disembunyikan ke tray. Klik ikon tray untuk membuka.",
                                       QSystemTrayIcon.MessageIcon.Information, 2500)
        else:
            # Tidak ada tray (GNOME default / host tray mati) -> minimize supaya window tidak hilang
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
        # Stop the Dashboard's own refresh timer too, else a queued tick can fire
        # against half-destroyed widgets during teardown.
        if hasattr(dash, 'timer'):
            try: dash.timer.stop()
            except Exception: pass
        # Wait for in-flight worker threads (pkexec/root scripts) so Qt doesn't
        # destroy a running QThread and orphan the spawned root process.
        for i in range(self.stack.count()):
            page = self.stack.widget(i)
            for w in list(getattr(page, '_workers', [])):
                try: w.wait(3000)
                except Exception: pass
        QApplication.instance().quit()

def main():
    # GNOME/Wayland kerap memunculkan warning kosmetik saat registrasi app-id ke
    # xdg-desktop-portal ("Could not register app ID ..."). Diamkan kategorinya.
    _rules = os.environ.get("QT_LOGGING_RULES", "")
    os.environ["QT_LOGGING_RULES"] = (_rules + ";qt.qpa.services=false").lstrip(";")
    app = QApplication(sys.argv)
    # Identitas app -> GNOME/Wayland mencocokkan ke loli.desktop (ikon & nama di dock, bukan "python3")
    app.setApplicationName("Loli")
    app.setApplicationDisplayName(APP_NAME)
    app.setDesktopFileName("loli")
    if os.path.exists(TRAY_ICON_PATH):
        app.setWindowIcon(QIcon(TRAY_ICON_PATH))
    app.setQuitOnLastWindowClosed(False)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
