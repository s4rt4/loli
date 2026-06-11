"""Application stylesheet (Qt QSS).

Modern slate/Tailwind palette. Centralised here so a future re-theme touches one
file instead of being swept across the codebase.
"""

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
