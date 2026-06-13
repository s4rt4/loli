"""System-level helpers: input validation, privileged execution, background
worker, and small environment probes. No Qt widgets here (only QThread)."""

import logging
import os
import re
import shlex
import shutil
import socket
import subprocess
import tempfile

import psutil
from PyQt6.QtCore import QThread, pyqtSignal


# ---------------------------------------------------------------- validation
def validate_domain(domain: str) -> bool:
    if not domain or len(domain) > 253:
        return False
    pattern = r'^(?!-)[a-zA-Z0-9-]{1,63}(?<!-)(\.[a-zA-Z0-9-]{1,63})*$'
    return bool(re.match(pattern, domain))


def validate_path(path: str) -> bool:
    if not path:
        return False
    # Reject control characters (newlines, etc.): they are never valid in a
    # docroot and would otherwise let a path inject extra lines into the
    # root-written Apache/nginx config files.
    if any(ord(c) < 32 for c in path):
        return False
    return os.path.isabs(path) and '..' not in path


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


# ------------------------------------------------------------ privileged run
def run_root_script(script_content: str) -> bool:
    """Write a bash script to a temp file and run it once via pkexec."""
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write("#!/bin/bash\n" + script_content)
            temp_path = f.name
        # 0o700, not 0o755: the script may embed DB passwords (pg_login,
        # mariadb_passwordless). pkexec runs it as root, which can read/exec an
        # owner-only file, so there is no need to expose it to other local users.
        os.chmod(temp_path, 0o700)
        subprocess.run(["pkexec", temp_path], check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Root script failed: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error in run_root_script: {e}")
        return False
    finally:
        try:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception as e:
            logging.warning(f"Failed to cleanup temp file: {e}")


# -------------------------------------------------------------- async worker
class _Worker(QThread):
    """Run a blocking fn (subprocess/pkexec) off the GUI thread."""
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
    """Run fn() on a worker thread; call on_done(result) back on the GUI thread."""
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


# --------------------------------------------------------------- env probes
def get_web_root(plat) -> str:
    try:
        out = subprocess.run(plat.docroot_grep_argv(),
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
    """True if a polkit authentication agent is likely available (for pkexec's
    password dialog). GNOME/KDE fold the agent into their shell (no separate
    process); XFCE/LXQt/minimal WMs need a standalone agent."""
    try:
        for p in psutil.process_iter(['name', 'cmdline']):
            name = (p.info.get('name') or '').lower()
            if name == 'gnome-shell':
                return True
            if ('polkit' in name and name != 'polkitd') or 'policykit' in name:
                return True
            cmd = ' '.join(p.info.get('cmdline') or []).lower()
            if any(k in cmd for k in ('authentication-agent', 'lxpolkit', 'xfce-polkit', 'policykit-agent')):
                return True
    except Exception as e:
        logging.warning(f"polkit agent check failed: {e}")
    de = (os.environ.get('XDG_CURRENT_DESKTOP', '') + ':' + os.environ.get('XDG_SESSION_DESKTOP', '')).lower()
    return any(k in de for k in ('gnome', 'kde', 'plasma', 'cinnamon', 'unity', 'pantheon', 'deepin', 'mate', 'ukui'))
