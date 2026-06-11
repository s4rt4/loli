"""Golden tests for loli.scripts.

Each expected string is transcribed from the ORIGINAL web_panel.py (Fedora) and
web_panel_deb.py (Debian) so the unified builders provably match both.

Run standalone: ``python3 tests/test_scripts.py``  (also works under pytest).
"""

import os
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loli import scripts as S  # noqa: E402
from loli.platform_spec import FEDORA, DEBIAN  # noqa: E402
from loli.services import validate_port  # noqa: E402


# --- Verbatim copies of the ORIGINAL save_prefs() script-building logic, used as
#     ground truth for prefs_apply. Transcribed from web_panel.py (Fedora) and
#     web_panel_deb.py (Debian). DO NOT "clean up" — they must mirror the originals.
def _ref_fedora_prefs(ndir, ports, php_ver):
    s = ""
    p_ng = ports["nginx"]
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
            s += f"command -v semanage >/dev/null 2>&1 && semanage fcontext -a -t httpd_sys_content_t {ndir_escaped}'(/.*)?' 2>/dev/null; command -v restorecon >/dev/null 2>&1 && restorecon -R {ndir_escaped} || true\n"
    if p_ap := ports["apache2"]:
        if validate_port(p_ap):
            s += f"sed -i 's/^Listen .*/Listen {p_ap}/g' /etc/httpd/conf/httpd.conf\n"
            s += f"command -v semanage >/dev/null 2>&1 && semanage port -a -t http_port_t -p tcp {p_ap} 2>/dev/null || true\n"
            s += "systemctl restart httpd || true\n"
    if p_ma := ports["mariadb"]:
        if validate_port(p_ma):
            s += f"printf '[mysqld]\\nport = {p_ma}\\n' > /etc/my.cnf.d/custom-panel.cnf\nsystemctl restart mariadb || true\n"
    if p_pg := ports["postgresql"]:
        if validate_port(p_pg):
            s += f"sed -i -E 's/^#?port = [0-9]+/port = {p_pg}/g' /var/lib/pgsql/data/postgresql.conf\nsystemctl restart postgresql || true\n"
    if p_mg := ports["mongod"]:
        if validate_port(p_mg):
            s += f"sed -i -E 's/^  port: [0-9]+/  port: {p_mg}/g' /etc/mongod.conf\nsystemctl restart mongod || true\n"
    if ndir or p_ng:
        s += "systemctl restart nginx || true\n"
    return s


def _ref_debian_prefs(ndir, ports, php_ver):
    s = ""
    p_ng = ports["nginx"]
    if ndir:
        ndir_escaped = shlex.quote(ndir)
        s += f"sed -i 's|DocumentRoot .*|DocumentRoot {ndir_escaped}|g' /etc/apache2/sites-available/000-default.conf\n"
        s += f"cat << 'EOF' > /etc/apache2/conf-available/custom-panel-dir.conf\n<Directory {ndir_escaped}>\n    Options Indexes FollowSymLinks\n    AllowOverride All\n    Require all granted\n</Directory>\nEOF\n"
        s += "a2enconf custom-panel-dir || true\n"
        if p_ng and validate_port(p_ng):
            s += f"if [ -d /etc/nginx/sites-available ]; then\ncat << 'EOF' > /etc/nginx/sites-available/default\nserver {{\n    listen {p_ng} default_server;\n    root {ndir_escaped};\n    index index.php index.html index.htm;\n    server_name _;\n    location / {{ try_files $uri $uri/ =404; }}\n    location ~ \\.php$ {{\n        include snippets/fastcgi-php.conf;\n        fastcgi_pass unix:/run/php/php{php_ver}-fpm.sock;\n    }}\n}}\nEOF\nfi\n"
        if ndir.startswith("/home/"):
            user_home = "/".join(ndir.split("/")[:3])
            user_home_escaped = shlex.quote(user_home)
            s += f"chmod +x {user_home_escaped}\nchown -R www-data:www-data {ndir_escaped} || true\nchmod -R 755 {ndir_escaped} || true\n"
    if p_ap := ports["apache2"]:
        if validate_port(p_ap):
            s += f"sed -i 's/^Listen .*/Listen {p_ap}/g' /etc/apache2/ports.conf\n"
            s += f"sed -i -E 's/<VirtualHost \\*:.*>/<VirtualHost *:{p_ap}>/g' /etc/apache2/sites-available/000-default.conf\n"
            s += "systemctl restart apache2 || true\n"
    if p_ma := ports["mariadb"]:
        if validate_port(p_ma):
            s += f"sed -i -E 's/^port\\s*=.*/port = {p_ma}/g' /etc/mysql/mariadb.conf.d/50-server.cnf\nsystemctl restart mariadb || true\n"
    if p_pg := ports["postgresql"]:
        if validate_port(p_pg):
            s += f"sed -i -E 's/^#?port = [0-9]+/port = {p_pg}/g' /etc/postgresql/*/main/postgresql.conf\nsystemctl restart postgresql || true\n"
    if p_mg := ports["mongod"]:
        if validate_port(p_mg):
            s += f"sed -i -E 's/^  port: [0-9]+/  port: {p_mg}/g' /etc/mongod.conf\nsystemctl restart mongod || true\n"
    if ndir or p_ng:
        s += "systemctl restart nginx || true\n"
    return s


_PREFS_CASES = [
    ("/home/u/www", {"nginx": "8080", "apache2": "8081", "mariadb": "3307",
                     "postgresql": "5433", "mongod": "27018"}, "8.2"),
    ("/var/www/site", {"nginx": "", "apache2": "", "mariadb": "",
                       "postgresql": "", "mongod": ""}, "8.4"),
    ("", {"nginx": "9000", "apache2": "8000", "mariadb": "", "postgresql": "5432",
          "mongod": ""}, "7.4"),
    ("", {"nginx": "", "apache2": "", "mariadb": "", "postgresql": "", "mongod": ""}, "8.4"),
    ("/home/dev/app", {"nginx": "bad", "apache2": "70000", "mariadb": "3306",
                       "postgresql": "", "mongod": "27017"}, "8.1"),
]


def test_prefs_apply():
    for ndir, ports, php_ver in _PREFS_CASES:
        assert S.prefs_apply(FEDORA, ndir, ports, php_ver) == _ref_fedora_prefs(ndir, ports, php_ver), \
            f"fedora prefs mismatch for {ndir!r} {ports!r}"
        assert S.prefs_apply(DEBIAN, ndir, ports, php_ver) == _ref_debian_prefs(ndir, ports, php_ver), \
            f"debian prefs mismatch for {ndir!r} {ports!r}"


def test_mongo_install():
    assert S.mongo_install(FEDORA) == (
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
    assert S.mongo_install(DEBIAN) == (
        "set -e\n"
        "export DEBIAN_FRONTEND=noninteractive\n"
        "apt-get install -y gnupg curl\n"
        ". /etc/os-release\n"
        "curl -fsSL https://pgp.mongodb.com/server-8.0.asc | "
        "gpg -o /usr/share/keyrings/mongodb-server-8.0.gpg --dearmor --yes\n"
        "echo \"deb [ signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg ] "
        "https://repo.mongodb.org/apt/debian ${VERSION_CODENAME}/mongodb-org/8.0 main\" "
        "> /etc/apt/sources.list.d/mongodb-org-8.0.list\n"
        "apt-get update\n"
        "apt-get install -y mongodb-org\n"
    )


def test_phpmyadmin_setup():
    pma, pma_q, tmp_q = "/data/phpmyadmin", "/data/phpmyadmin", "/tmp/abc.php"
    head = (
        f"PMA={pma_q}\n"
        f"cp {tmp_q} \"$PMA/config.inc.php\"\n"
        "mkdir -p \"$PMA/tmp\"\n"
    )
    body = (
        f"Alias /phpmyadmin {pma}\n"
        f"<Directory {pma}>\n"
        "    Options FollowSymLinks\n"
        "    DirectoryIndex index.php\n"
        "    AllowOverride All\n"
        "    Require all granted\n"
        "</Directory>\n"
        "EOF\n"
    )
    assert S.phpmyadmin_setup(FEDORA, pma, pma_q, tmp_q) == (
        head
        + "cat << 'EOF' > /etc/httpd/conf.d/phpMyAdmin.conf\n"
        + body
        + "chown -R apache:apache \"$PMA\"\n"
        + "chmod 1777 \"$PMA/tmp\"\n"
        + "command -v semanage >/dev/null 2>&1 && semanage fcontext -a -t httpd_sys_content_t "
          "'/data/phpmyadmin(/.*)?' 2>/dev/null\n"
        + "command -v semanage >/dev/null 2>&1 && semanage fcontext -a -t httpd_sys_rw_content_t "
          "'/data/phpmyadmin/tmp(/.*)?' 2>/dev/null\n"
        + "command -v restorecon >/dev/null 2>&1 && restorecon -R \"$PMA\"\n"
        + "command -v setsebool >/dev/null 2>&1 && setsebool -P httpd_can_network_connect_db "
          "on 2>/dev/null || true\n"
        + "systemctl restart httpd\n"
    )
    assert S.phpmyadmin_setup(DEBIAN, pma, pma_q, tmp_q) == (
        head
        + "cat << 'EOF' > /etc/apache2/conf-available/phpmyadmin.conf\n"
        + body
        + "a2enconf phpmyadmin || true\n"
        + "chown -R www-data:www-data \"$PMA\"\n"
        + "chmod 1777 \"$PMA/tmp\"\n"
        + "systemctl restart apache2\n"
    )


def test_pg_init():
    assert S.pg_init(FEDORA) == (
        "if [ ! -f /var/lib/pgsql/data/PG_VERSION ]; then\n"
        "  postgresql-setup --initdb\n"
        "fi\n"
        "systemctl enable --now postgresql\n"
    )
    assert S.pg_init(DEBIAN) == (
        "if ! pg_lsclusters -h 2>/dev/null | grep -q .; then\n"
        "  V=$(ls /usr/lib/postgresql 2>/dev/null | sort -V | tail -1)\n"
        "  [ -n \"$V\" ] && pg_createcluster \"$V\" main || true\n"
        "fi\n"
        "systemctl enable --now postgresql\n"
    )


def test_pg_login():
    assert S.pg_login(FEDORA) == (
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
        "s = re.sub(r'^(host\\s+all\\s+all\\s+(?:127\\.0\\.0\\.1/32|::1/128)\\s+)[\\w-]+', "
        "r'\\1scram-sha-256', s, flags=re.M)\n"
        "open(p, 'w').write(s)\n"
        "PYEOF\n"
        "systemctl reload postgresql\n"
    )
    assert S.pg_login(DEBIAN) == (
        "set -e\n"
        "if ! pg_lsclusters -h 2>/dev/null | grep -q .; then\n"
        "  V=$(ls /usr/lib/postgresql 2>/dev/null | sort -V | tail -1)\n"
        "  [ -n \"$V\" ] && pg_createcluster \"$V\" main || true\n"
        "fi\n"
        "systemctl enable --now postgresql\n"
        "sudo -u postgres psql -c \"ALTER USER postgres PASSWORD 'postgres';\"\n"
        "for p in /etc/postgresql/*/main/pg_hba.conf; do\n"
        "  [ -f \"$p\" ] && sed -i -E 's#^(host[[:space:]]+all[[:space:]]+all[[:space:]]+"
        "(127\\.0\\.0\\.1/32|::1/128)[[:space:]]+)[[:alnum:]_-]+#\\1scram-sha-256#' \"$p\"\n"
        "done\n"
        "systemctl reload postgresql\n"
    )


def test_mariadb_passwordless():
    sql = ("CREATE USER IF NOT EXISTS 'admin'@'127.0.0.1' IDENTIFIED VIA mysql_native_password USING ''; "
           "GRANT ALL PRIVILEGES ON *.* TO 'admin'@'127.0.0.1' WITH GRANT OPTION; "
           "FLUSH PRIVILEGES;")
    expected = "systemctl enable --now mariadb\n" + f'mariadb -e "{sql}"\n'
    assert S.mariadb_passwordless(sql) == expected


def test_vhost_create():
    dom, path_escaped, vc = "myapp.test", "/var/www/html/app", "# loli-vhost myapp.test\n<VirtualHost *:80>\n</VirtualHost>\n"
    assert S.vhost_create(FEDORA, dom, path_escaped, vc) == (
        "cat << 'LOLIEOF' > /etc/httpd/conf.d/myapp.test.conf\n"
        + vc
        + "LOLIEOF\n"
        + "grep -qxF '127.0.0.1 myapp.test' /etc/hosts || echo '127.0.0.1 myapp.test' >> /etc/hosts\n"
        + "command -v semanage >/dev/null 2>&1 && semanage fcontext -a -t httpd_sys_content_t "
          "/var/www/html/app'(/.*)?' 2>/dev/null\n"
        + "command -v restorecon >/dev/null 2>&1 && restorecon -R /var/www/html/app\n"
        + "systemctl reload httpd\n"
    )
    assert S.vhost_create(DEBIAN, dom, path_escaped, vc) == (
        "cat << 'LOLIEOF' > /etc/apache2/sites-available/myapp.test.conf\n"
        + vc
        + "LOLIEOF\n"
        + "a2ensite myapp.test.conf || true\n"
        + "grep -qxF '127.0.0.1 myapp.test' /etc/hosts || echo '127.0.0.1 myapp.test' >> /etc/hosts\n"
        + "systemctl reload apache2\n"
    )


def test_vhost_delete():
    dom, dom_sed = "myapp.test", "myapp\\.test"
    assert S.vhost_delete(FEDORA, dom, dom_sed) == (
        "rm -f /etc/httpd/conf.d/myapp.test.conf\n"
        "sed -i '/^127\\.0\\.0\\.1[[:space:]]\\+myapp\\.test$/d' /etc/hosts\n"
        "systemctl reload httpd\n"
    )
    assert S.vhost_delete(DEBIAN, dom, dom_sed) == (
        "a2dissite myapp.test.conf || true\n"
        "rm -f /etc/apache2/sites-available/myapp.test.conf\n"
        "sed -i '/^127\\.0\\.0\\.1[[:space:]]\\+myapp\\.test$/d' /etc/hosts\n"
        "systemctl reload apache2\n"
    )


def test_enable_ssl():
    assert S.enable_ssl(FEDORA) == "dnf install -y mod_ssl && systemctl restart httpd"
    assert S.enable_ssl(DEBIAN) == "a2enmod ssl && a2ensite default-ssl && systemctl restart apache2"


def test_php_mailcatcher():
    common = (
        "echo '#!/bin/bash\ncat >> /tmp/php-mail.log\necho -e \"\\n---END OF MAIL---\\n\" "
        ">> /tmp/php-mail.log' > /usr/local/bin/local-mailcatcher\n"
        "chmod +x /usr/local/bin/local-mailcatcher\n"
        "touch /tmp/php-mail.log && chmod 777 /tmp/php-mail.log\n"
    )
    loop_tail = (
        "if [ -f \"$ini\" ]; then\n"
        "if grep -q \"sendmail_path\" \"$ini\"; then\n"
        "sed -i 's|^;*sendmail_path .*|sendmail_path = /usr/local/bin/local-mailcatcher|g' \"$ini\"\n"
        "else\n"
        "echo 'sendmail_path = /usr/local/bin/local-mailcatcher' >> \"$ini\"\n"
        "fi\n"
        "fi\n"
        "done\n"
    )
    assert S.php_mailcatcher(FEDORA) == (
        common + "for ini in /etc/php.ini; do\n" + loop_tail
        + "systemctl restart httpd || true\n"
        + "systemctl restart php-fpm || true"
    )
    assert S.php_mailcatcher(DEBIAN) == (
        common + "for ini in /etc/php/*/apache2/php.ini /etc/php/*/fpm/php.ini; do\n" + loop_tail
        + "systemctl restart apache2 || true\n"
        + "systemctl restart php*-fpm || true"
    )


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\nAll {len(fns)} script golden tests passed.")
