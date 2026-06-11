"""Distro abstraction layer.

The panel originally shipped as two ~2,500-line files kept in sync by hand
(``web_panel.py`` for Fedora, ``web_panel_deb.py`` for Debian/Ubuntu). ~90% was
identical; the ~10% that differed is captured here as a :class:`Platform`
descriptor so the rest of the app is distro-agnostic.

Selection happens at runtime from ``/etc/os-release``; set ``LOLI_PLATFORM`` to
``fedora`` or ``debian`` to force one (used by the test-suite to exercise both
code paths on a single machine).
"""

from __future__ import annotations

import glob
import os
import re
import shlex
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Platform:
    id: str                      # "fedora" | "debian"
    web_svc: str                 # apache service unit
    redis_svc: str               # redis/valkey service unit
    web_user: str                # user apache/php run as
    pkg_mgr: str                 # "dnf" | "apt"
    has_selinux: bool

    # Filesystem layout
    apache_main_conf: str        # main apache config (for Config Editor)
    apache_conf_dir: str         # dir we drop generated *.conf into
    apache_default_vhost: str    # file holding the default DocumentRoot
    apache_ports_source: str     # file to read the listen port from
    mariadb_cnf: str
    pg_data_dir: str
    pg_conf_glob: str            # glob for postgresql.conf
    pg_hba_glob: str             # glob for pg_hba.conf
    nginx_site: str              # nginx site file we write
    phpmyadmin_conf: str         # apache conf file we write for phpMyAdmin
    php_ini_glob: str            # shell glob(s) of php.ini files to patch
    php_fpm_unit: str            # systemctl unit name for php-fpm
    pg_log_unit: str             # journalctl unit for postgresql
    apache_conf_available: str   # dir for drop-in confs (conf.d / conf-available)
    docroot_sed_anchor: str      # "^" on Fedora, "" on Debian (DocumentRoot sed)

    # Dashboard service rows: (unit, label, icon)
    services: tuple = field(default_factory=tuple)
    # unit -> package name for the Install button
    svc_packages: dict = field(default_factory=dict)

    # ---- derived service lists (kept explicit for byte-exact scripts) ----
    @property
    def start_services(self) -> list[str]:
        return [self.web_svc, "mariadb", "postgresql", self.redis_svc, "memcached", "mongod"]

    @property
    def stop_services(self) -> list[str]:
        return [self.web_svc, "nginx", "mariadb", "postgresql", self.redis_svc, "memcached", "mongod"]

    def start_all_script(self) -> str:
        units = " ".join(self.start_services)
        return f"for s in {units}; do systemctl start $s 2>/dev/null || true; done\n"

    def stop_all_script(self) -> str:
        units = " ".join(self.stop_services)
        return f"for s in {units}; do systemctl stop $s 2>/dev/null || true; done\n"

    # ---- package install ----
    def install_pkg_argv(self, pkg: str) -> list[str]:
        if self.pkg_mgr == "dnf":
            return ["pkexec", "dnf", "install", "-y", pkg]
        return ["pkexec", "sh", "-c",
                f"apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y {shlex.quote(pkg)}"]

    # ---- apache helpers (no-ops on Fedora's drop-in model) ----
    def apache_enable_site(self, dom: str) -> str:
        return f"a2ensite {shlex.quote(dom)}.conf || true\n" if self.id == "debian" else ""

    def apache_disable_site(self, dom: str) -> str:
        return f"a2dissite {shlex.quote(dom)}.conf || true\n" if self.id == "debian" else ""

    def apache_enable_conf(self, name: str) -> str:
        return f"a2enconf {name} || true\n" if self.id == "debian" else ""

    def reload_web(self) -> str:
        return f"systemctl reload {self.web_svc}\n"

    def restart_web(self) -> str:
        return f"systemctl restart {self.web_svc}\n"

    # ---- Logs page: journalctl tabs ----
    def log_units(self) -> list:
        def jc(unit):
            return ["journalctl", "-u", unit, "-n", "300", "--no-pager"]
        return [
            ("Apache", jc(self.web_svc)),
            ("PHP-FPM", jc(self.php_fpm_unit)),
            ("MariaDB", jc("mariadb")),
            ("PostgreSQL", jc(self.pg_log_unit)),
            ("Nginx", jc("nginx")),
        ]

    # ---- Config Editor: label -> file path (some entries are globbed live) ----
    def config_files(self) -> dict:
        if self.id == "debian":
            files = {
                "Apache: Main Config": "/etc/apache2/apache2.conf",
                "Apache: Ports Config": "/etc/apache2/ports.conf",
                "Apache: Default VHost": "/etc/apache2/sites-available/000-default.conf",
                "Apache: Panel VHost": "/etc/apache2/conf-available/custom-panel-dir.conf",
                "Nginx: Main Config": "/etc/nginx/nginx.conf",
                "Nginx: Default VHost": "/etc/nginx/sites-available/default",
                "MariaDB: Server Config": "/etc/mysql/mariadb.conf.d/50-server.cnf",
                "MongoDB: Main Config": "/etc/mongod.conf",
                "OS: Hosts File": "/etc/hosts",
            }
            for php_ini in sorted(glob.glob("/etc/php/*/apache2/php.ini")
                                  + glob.glob("/etc/php/*/fpm/php.ini")
                                  + glob.glob("/etc/php/*/cli/php.ini")):
                m = re.search(r"/etc/php/([^/]+)/([^/]+)/php\.ini", php_ini)
                if m:
                    files[f"PHP {m.group(1)}: {m.group(2)} php.ini"] = php_ini
            for fpm_pool in sorted(glob.glob("/etc/php/*/fpm/pool.d/www.conf")):
                m = re.search(r"/etc/php/([^/]+)/", fpm_pool)
                if m:
                    files[f"PHP {m.group(1)}: FPM Pool (www)"] = fpm_pool
            pg = sorted(glob.glob("/etc/postgresql/*/main/postgresql.conf"))
            if pg:
                files["PostgreSQL: Config"] = pg[0]
            return files
        files = {
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
            "OS: Hosts File": "/etc/hosts",
        }
        pg = glob.glob("/var/lib/pgsql/data/postgresql.conf") + glob.glob("/var/lib/pgsql/*/data/postgresql.conf")
        if pg:
            files["PostgreSQL: Config"] = pg[0]
        return files

    # ---- read the server DocumentRoot (grep differs per distro) ----
    def docroot_grep_argv(self) -> list[str]:
        if self.id == "debian":
            return ["grep", "-m1", "-i", "DocumentRoot", self.apache_default_vhost]
        return ["grep", "-m1", "^DocumentRoot", self.apache_default_vhost]

    # ---- php-fpm socket path ----
    def php_fpm_sock(self, ver: str = "") -> str:
        if self.id == "debian":
            return f"/run/php/php{ver}-fpm.sock"
        return "/run/php-fpm/www.sock"

    # ---- SELinux snippets (empty on Debian) ----
    def selinux_fcontext(self, path_escaped: str, rw: bool = False) -> str:
        if not self.has_selinux:
            return ""
        t = "httpd_sys_rw_content_t" if rw else "httpd_sys_content_t"
        return (f"command -v semanage >/dev/null 2>&1 && "
                f"semanage fcontext -a -t {t} {path_escaped}'(/.*)?' 2>/dev/null\n")

    def selinux_restorecon(self, target: str) -> str:
        if not self.has_selinux:
            return ""
        return f"command -v restorecon >/dev/null 2>&1 && restorecon -R {target}\n"

    def selinux_net_db(self) -> str:
        if not self.has_selinux:
            return ""
        return ("command -v setsebool >/dev/null 2>&1 && "
                "setsebool -P httpd_can_network_connect_db on 2>/dev/null || true\n")

    # ---- postgresql cluster init + pg_hba auth fix (structurally distinct) ----
    def pg_ensure_cluster(self) -> str:
        if self.id == "debian":
            return ("if ! pg_lsclusters -h 2>/dev/null | grep -q .; then\n"
                    "  V=$(ls /usr/lib/postgresql 2>/dev/null | sort -V | tail -1)\n"
                    "  [ -n \"$V\" ] && pg_createcluster \"$V\" main || true\n"
                    "fi\n")
        return ("if [ ! -f /var/lib/pgsql/data/PG_VERSION ]; then\n"
                "  postgresql-setup --initdb\n"
                "fi\n")

    def pg_hba_fix(self) -> str:
        if self.id == "debian":
            return ("for p in /etc/postgresql/*/main/pg_hba.conf; do\n"
                    "  [ -f \"$p\" ] && sed -i -E 's#^(host[[:space:]]+all[[:space:]]+all[[:space:]]+"
                    "(127\\.0\\.0\\.1/32|::1/128)[[:space:]]+)[[:alnum:]_-]+#\\1scram-sha-256#' \"$p\"\n"
                    "done\n")
        return ("python3 - <<'PYEOF'\n"
                "import re\n"
                "p = '/var/lib/pgsql/data/pg_hba.conf'\n"
                "s = open(p).read()\n"
                "s = re.sub(r'^(host\\s+all\\s+all\\s+(?:127\\.0\\.0\\.1/32|::1/128)\\s+)[\\w-]+', "
                "r'\\1scram-sha-256', s, flags=re.M)\n"
                "open(p, 'w').write(s)\n"
                "PYEOF\n")


FEDORA = Platform(
    id="fedora",
    web_svc="httpd",
    redis_svc="valkey",
    web_user="apache",
    pkg_mgr="dnf",
    has_selinux=True,
    apache_main_conf="/etc/httpd/conf/httpd.conf",
    apache_conf_dir="/etc/httpd/conf.d",
    apache_default_vhost="/etc/httpd/conf/httpd.conf",
    apache_ports_source="/etc/httpd/conf/httpd.conf",
    mariadb_cnf="/etc/my.cnf.d/mariadb-server.cnf",
    pg_data_dir="/var/lib/pgsql/data",
    pg_conf_glob="/var/lib/pgsql/data/postgresql.conf",
    pg_hba_glob="/var/lib/pgsql/data/pg_hba.conf",
    nginx_site="/etc/nginx/conf.d/custom-panel.conf",
    phpmyadmin_conf="/etc/httpd/conf.d/phpMyAdmin.conf",
    php_ini_glob="/etc/php.ini",
    php_fpm_unit="php-fpm",
    pg_log_unit="postgresql",
    apache_conf_available="/etc/httpd/conf.d",
    docroot_sed_anchor="^",
    services=(
        ("httpd", "Apache Web Server", "fa5s.server"),
        ("nginx", "Nginx Web Server", "fa5s.server"),
        ("mariadb", "MariaDB Database", "fa5s.database"),
        ("postgresql", "PostgreSQL", "fa5s.database"),
        ("valkey", "Valkey (Redis)", "fa5s.bolt"),
        ("memcached", "Memcached", "fa5s.memory"),
        ("mongod", "MongoDB", "fa5s.database"),
    ),
    svc_packages={
        "httpd": "httpd", "nginx": "nginx", "mariadb": "mariadb-server",
        "postgresql": "postgresql-server", "valkey": "valkey", "memcached": "memcached",
        "mongod": "mongodb-org",
    },
)

DEBIAN = Platform(
    id="debian",
    web_svc="apache2",
    redis_svc="redis-server",
    web_user="www-data",
    pkg_mgr="apt",
    has_selinux=False,
    apache_main_conf="/etc/apache2/apache2.conf",
    apache_conf_dir="/etc/apache2/sites-available",
    apache_default_vhost="/etc/apache2/sites-available/000-default.conf",
    apache_ports_source="/etc/apache2/ports.conf",
    mariadb_cnf="/etc/mysql/mariadb.conf.d/50-server.cnf",
    pg_data_dir="/var/lib/postgresql",
    pg_conf_glob="/etc/postgresql/*/main/postgresql.conf",
    pg_hba_glob="/etc/postgresql/*/main/pg_hba.conf",
    nginx_site="/etc/nginx/sites-available/default",
    phpmyadmin_conf="/etc/apache2/conf-available/phpmyadmin.conf",
    php_ini_glob="/etc/php/*/apache2/php.ini /etc/php/*/fpm/php.ini",
    php_fpm_unit="php*-fpm",
    pg_log_unit="postgresql*",
    apache_conf_available="/etc/apache2/conf-available",
    docroot_sed_anchor="",
    services=(
        ("apache2", "Apache Web Server", "fa5s.server"),
        ("nginx", "Nginx Web Server", "fa5s.server"),
        ("mariadb", "MariaDB Database", "fa5s.database"),
        ("postgresql", "PostgreSQL", "fa5s.database"),
        ("redis-server", "Redis", "fa5s.bolt"),
        ("memcached", "Memcached", "fa5s.memory"),
        ("mongod", "MongoDB", "fa5s.database"),
    ),
    svc_packages={
        "apache2": "apache2", "nginx": "nginx", "mariadb": "mariadb-server",
        "postgresql": "postgresql", "redis-server": "redis-server", "memcached": "memcached",
        "mongod": "mongodb-org",
    },
)

_BY_ID = {"fedora": FEDORA, "debian": DEBIAN}


def detect() -> Platform:
    """Pick a platform from ``LOLI_PLATFORM`` or ``/etc/os-release``.

    Defaults to Fedora only as a last resort; Debian/Ubuntu and RHEL-likes are
    matched via ``ID`` and ``ID_LIKE``.
    """
    forced = os.environ.get("LOLI_PLATFORM", "").strip().lower()
    if forced in _BY_ID:
        return _BY_ID[forced]

    ids: set[str] = set()
    try:
        with open("/etc/os-release", encoding="utf-8") as f:
            for line in f:
                if line.startswith(("ID=", "ID_LIKE=")):
                    val = line.split("=", 1)[1].strip().strip('"')
                    ids.update(val.replace("-", " ").split())
    except OSError:
        pass

    if ids & {"debian", "ubuntu"}:
        return DEBIAN
    if ids & {"fedora", "rhel", "centos"}:
        return FEDORA
    return FEDORA
