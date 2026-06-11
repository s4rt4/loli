"""Paths, ports and app metadata.

Assets (logo.svg, logo-tray.svg, icons/) live one level above the package
directory: in the dev tree that is the repo root; when installed they sit in
the share dir next to the ``loli/`` package (e.g. /usr/share/loli/).
"""

import os

from ._version import APP_NAME, APP_VERSION

PKG_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.dirname(PKG_DIR)

LOGO_PATH = os.path.join(ASSET_DIR, "logo.svg")
TRAY_ICON_PATH = os.path.join(ASSET_DIR, "logo-tray.svg")
ICON_DIR = os.path.join(ASSET_DIR, "icons")

# Tools downloaded at runtime (pgweb/mailpit/phpMyAdmin) need a writable home.
# From source ASSET_DIR is writable; once installed system-wide (read-only)
# fall back to a per-user data dir.
DATA_DIR = ASSET_DIR if os.access(ASSET_DIR, os.W_OK) else os.path.join(
    os.path.expanduser("~"), ".local", "share", "loli")
try:
    os.makedirs(DATA_DIR, exist_ok=True)
except OSError:
    DATA_DIR = ASSET_DIR

PGWEB_PORT = 8081
MAILPIT_UI_PORT = 8025
MAILPIT_SMTP_PORT = 1025

__all__ = [
    "APP_NAME", "APP_VERSION", "PKG_DIR", "ASSET_DIR", "LOGO_PATH",
    "TRAY_ICON_PATH", "ICON_DIR", "DATA_DIR", "PGWEB_PORT",
    "MAILPIT_UI_PORT", "MAILPIT_SMTP_PORT",
]
