"""Golden tests for the Platform descriptor.

Every assertion pins output to the EXACT strings/data the original
``web_panel.py`` (Fedora) and ``web_panel_deb.py`` (Debian) produced, so the
unified code provably changes no behaviour for either distro.

Run standalone: ``python3 tests/test_platform.py``  (also works under pytest).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loli.platform_spec import FEDORA, DEBIAN, detect  # noqa: E402


def test_service_rows():
    assert FEDORA.services == (
        ("httpd", "Apache Web Server", "fa5s.server"),
        ("nginx", "Nginx Web Server", "fa5s.server"),
        ("mariadb", "MariaDB Database", "fa5s.database"),
        ("postgresql", "PostgreSQL", "fa5s.database"),
        ("valkey", "Valkey (Redis)", "fa5s.bolt"),
        ("memcached", "Memcached", "fa5s.memory"),
        ("mongod", "MongoDB", "fa5s.database"),
    )
    assert DEBIAN.services == (
        ("apache2", "Apache Web Server", "fa5s.server"),
        ("nginx", "Nginx Web Server", "fa5s.server"),
        ("mariadb", "MariaDB Database", "fa5s.database"),
        ("postgresql", "PostgreSQL", "fa5s.database"),
        ("redis-server", "Redis", "fa5s.bolt"),
        ("memcached", "Memcached", "fa5s.memory"),
        ("mongod", "MongoDB", "fa5s.database"),
    )


def test_svc_packages():
    assert FEDORA.svc_packages == {
        "httpd": "httpd", "nginx": "nginx", "mariadb": "mariadb-server",
        "postgresql": "postgresql-server", "valkey": "valkey", "memcached": "memcached",
        "mongod": "mongodb-org",
    }
    assert DEBIAN.svc_packages == {
        "apache2": "apache2", "nginx": "nginx", "mariadb": "mariadb-server",
        "postgresql": "postgresql", "redis-server": "redis-server", "memcached": "memcached",
        "mongod": "mongodb-org",
    }


def test_start_stop_all_scripts():
    assert FEDORA.start_all_script() == (
        "for s in httpd mariadb postgresql valkey memcached mongod; "
        "do systemctl start $s 2>/dev/null || true; done\n")
    assert FEDORA.stop_all_script() == (
        "for s in httpd nginx mariadb postgresql valkey memcached mongod; "
        "do systemctl stop $s 2>/dev/null || true; done\n")
    assert DEBIAN.start_all_script() == (
        "for s in apache2 mariadb postgresql redis-server memcached mongod; "
        "do systemctl start $s 2>/dev/null || true; done\n")
    assert DEBIAN.stop_all_script() == (
        "for s in apache2 nginx mariadb postgresql redis-server memcached mongod; "
        "do systemctl stop $s 2>/dev/null || true; done\n")


def test_install_pkg_argv():
    assert FEDORA.install_pkg_argv("mongodb-org") == ["pkexec", "dnf", "install", "-y", "mongodb-org"]
    assert DEBIAN.install_pkg_argv("mongodb-org") == [
        "pkexec", "sh", "-c",
        "apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y mongodb-org",
    ]


def test_apache_helpers():
    # Fedora uses the drop-in model -> no enable/disable commands
    assert FEDORA.apache_enable_site("myapp.test") == ""
    assert FEDORA.apache_disable_site("myapp.test") == ""
    assert FEDORA.apache_enable_conf("phpmyadmin") == ""
    # Debian uses a2ensite/a2enconf
    assert DEBIAN.apache_enable_site("myapp.test") == "a2ensite myapp.test.conf || true\n"
    assert DEBIAN.apache_disable_site("myapp.test") == "a2dissite myapp.test.conf || true\n"
    assert DEBIAN.apache_enable_conf("phpmyadmin") == "a2enconf phpmyadmin || true\n"


def test_reload_restart_web():
    assert FEDORA.reload_web() == "systemctl reload httpd\n"
    assert FEDORA.restart_web() == "systemctl restart httpd\n"
    assert DEBIAN.reload_web() == "systemctl reload apache2\n"
    assert DEBIAN.restart_web() == "systemctl restart apache2\n"


def test_php_fpm_sock():
    assert FEDORA.php_fpm_sock("8.2") == "/run/php-fpm/www.sock"
    assert DEBIAN.php_fpm_sock("8.2") == "/run/php/php8.2-fpm.sock"


def test_selinux_snippets():
    p = "/var/www/html/app"
    assert DEBIAN.selinux_fcontext(p) == ""
    assert DEBIAN.selinux_restorecon(p) == ""
    assert DEBIAN.selinux_net_db() == ""
    assert FEDORA.selinux_fcontext(p) == (
        "command -v semanage >/dev/null 2>&1 && "
        "semanage fcontext -a -t httpd_sys_content_t /var/www/html/app'(/.*)?' 2>/dev/null\n")
    assert FEDORA.selinux_fcontext(p, rw=True) == (
        "command -v semanage >/dev/null 2>&1 && "
        "semanage fcontext -a -t httpd_sys_rw_content_t /var/www/html/app'(/.*)?' 2>/dev/null\n")
    assert FEDORA.selinux_restorecon(p) == (
        "command -v restorecon >/dev/null 2>&1 && restorecon -R /var/www/html/app\n")
    assert FEDORA.selinux_net_db() == (
        "command -v setsebool >/dev/null 2>&1 && "
        "setsebool -P httpd_can_network_connect_db on 2>/dev/null || true\n")


def test_docroot_grep_argv():
    assert FEDORA.docroot_grep_argv() == [
        "grep", "-m1", "^DocumentRoot", "/etc/httpd/conf/httpd.conf"]
    assert DEBIAN.docroot_grep_argv() == [
        "grep", "-m1", "-i", "DocumentRoot", "/etc/apache2/sites-available/000-default.conf"]


def test_detect_override():
    old = os.environ.get("LOLI_PLATFORM")
    try:
        os.environ["LOLI_PLATFORM"] = "debian"
        assert detect().id == "debian"
        os.environ["LOLI_PLATFORM"] = "fedora"
        assert detect().id == "fedora"
    finally:
        if old is None:
            os.environ.pop("LOLI_PLATFORM", None)
        else:
            os.environ["LOLI_PLATFORM"] = old


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\nAll {len(fns)} platform golden tests passed.")
