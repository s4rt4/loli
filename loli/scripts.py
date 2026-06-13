"""Root-script builders.

Every privileged shell script the panel runs via pkexec is assembled here,
parametrized by a :class:`~loli.platform_spec.Platform`. Each builder reproduces
byte-for-byte what the original per-distro files generated (locked by
tests/test_scripts.py) so unifying the two files changes no behaviour.
"""

import shlex

from .services import validate_port


def prefs_apply(plat, ndir: str, ports: dict, php_ver: str) -> str:
    """Build the Preferences 'apply' script: optional custom docroot + per-service
    port changes. ``ports`` keys: nginx, apache2, mariadb, postgresql, mongod."""
    s = ""
    p_ng = ports.get("nginx", "")
    if ndir:
        ndir_escaped = shlex.quote(ndir)
        s += (f"sed -i 's|{plat.docroot_sed_anchor}DocumentRoot .*|DocumentRoot {ndir_escaped}|g' "
              f"{plat.apache_default_vhost}\n")
        s += (f"cat << 'EOF' > {plat.apache_conf_available}/custom-panel-dir.conf\n"
              f"<Directory {ndir_escaped}>\n    Options Indexes FollowSymLinks\n"
              "    AllowOverride All\n    Require all granted\n</Directory>\nEOF\n")
        s += plat.apache_enable_conf("custom-panel-dir")
        if p_ng and validate_port(p_ng):
            if plat.id == "debian":
                s += f"if [ -d /etc/nginx/sites-available ]; then\ncat << 'EOF' > /etc/nginx/sites-available/default\nserver {{\n    listen {p_ng} default_server;\n    root {ndir_escaped};\n    index index.php index.html index.htm;\n    server_name _;\n    location / {{ try_files $uri $uri/ =404; }}\n    location ~ \\.php$ {{\n        include snippets/fastcgi-php.conf;\n        fastcgi_pass unix:/run/php/php{php_ver}-fpm.sock;\n    }}\n}}\nEOF\nfi\n"
            else:
                s += f"if [ -d /etc/nginx/conf.d ]; then\ncat << 'EOF' > /etc/nginx/conf.d/custom-panel.conf\nserver {{\n    listen {p_ng};\n    root {ndir_escaped};\n    index index.php index.html index.htm;\n    server_name _;\n    location / {{ try_files $uri $uri/ =404; }}\n    location ~ \\.php$ {{\n        fastcgi_split_path_info ^(.+\\.php)(/.+)$;\n        fastcgi_pass unix:/run/php-fpm/www.sock;\n        fastcgi_index index.php;\n        include fastcgi_params;\n        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;\n    }}\n}}\nEOF\nfi\n"
        if ndir.startswith("/home/"):
            user_home = "/".join(ndir.split("/")[:3])
            user_home_escaped = shlex.quote(user_home)
            s += (f"chmod +x {user_home_escaped}\nchown -R {plat.web_user}:{plat.web_user} "
                  f"{ndir_escaped} || true\nchmod -R 755 {ndir_escaped} || true\n")
            if plat.has_selinux:
                s += (f"command -v semanage >/dev/null 2>&1 && semanage fcontext -a -t "
                      f"httpd_sys_content_t {ndir_escaped}'(/.*)?' 2>/dev/null; "
                      f"command -v restorecon >/dev/null 2>&1 && restorecon -R {ndir_escaped} || true\n")

    p_ap = ports.get("apache2", "")
    if p_ap and validate_port(p_ap):
        if plat.id == "debian":
            s += f"sed -i 's/^Listen .*/Listen {p_ap}/g' /etc/apache2/ports.conf\n"
            s += (f"sed -i -E 's/<VirtualHost \\*:.*>/<VirtualHost *:{p_ap}>/g' "
                  "/etc/apache2/sites-available/000-default.conf\n")
            s += "systemctl restart apache2 || true\n"
        else:
            s += f"sed -i 's/^Listen .*/Listen {p_ap}/g' /etc/httpd/conf/httpd.conf\n"
            s += (f"command -v semanage >/dev/null 2>&1 && semanage port -a -t http_port_t "
                  f"-p tcp {p_ap} 2>/dev/null || true\n")
            s += "systemctl restart httpd || true\n"

    p_ma = ports.get("mariadb", "")
    if p_ma and validate_port(p_ma):
        if plat.id == "debian":
            s += (f"sed -i -E 's/^port\\s*=.*/port = {p_ma}/g' "
                  "/etc/mysql/mariadb.conf.d/50-server.cnf\nsystemctl restart mariadb || true\n")
        else:
            s += (f"printf '[mysqld]\\nport = {p_ma}\\n' > /etc/my.cnf.d/custom-panel.cnf\n"
                  "systemctl restart mariadb || true\n")

    p_pg = ports.get("postgresql", "")
    if p_pg and validate_port(p_pg):
        s += (f"sed -i -E 's/^#?port = [0-9]+/port = {p_pg}/g' {plat.pg_conf_glob}\n"
              "systemctl restart postgresql || true\n")

    p_mg = ports.get("mongod", "")
    if p_mg and validate_port(p_mg):
        s += (f"sed -i -E 's/^  port: [0-9]+/  port: {p_mg}/g' /etc/mongod.conf\n"
              "systemctl restart mongod || true\n")

    if ndir or p_ng:
        s += "systemctl restart nginx || true\n"
    return s


def mongo_install(plat) -> str:
    """Register the MongoDB repo and install mongodb-org."""
    if plat.id == "debian":
        return (
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
    return (
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


def phpmyadmin_setup(plat, staging: str, served: str, served_q: str, tmp_q: str) -> str:
    """Relocate the downloaded copy under the web root, then drop the
    phpMyAdmin config + apache alias and fix ownership/labels.

    ``staging`` is the unprivileged download dir (may sit in $HOME, which Apache
    cannot traverse); ``served`` is the final web-served dir. ``served_q``/
    ``tmp_q`` are shlex.quote'd. On a fresh install the staging copy is moved to
    ``served``; on a repair (``served`` already populated) the move is skipped.
    """
    staging_q = shlex.quote(staging)
    s = (
        f"PMA={served_q}\n"
        f"STAGING={staging_q}\n"
        "mkdir -p \"$(dirname \"$PMA\")\"\n"
        "if [ -d \"$STAGING\" ] && [ ! -e \"$PMA/index.php\" ]; then "
        "rm -rf \"$PMA\"; mv \"$STAGING\" \"$PMA\"; fi\n"
        f"cp {tmp_q} \"$PMA/config.inc.php\"\n"
        "mkdir -p \"$PMA/tmp\"\n"
        f"cat << 'EOF' > {plat.phpmyadmin_conf}\n"
        f"Alias /phpmyadmin {served}\n"
        f"<Directory {served}>\n"
        "    Options FollowSymLinks\n"
        "    DirectoryIndex index.php\n"
        "    AllowOverride All\n"
        "    Require all granted\n"
        "</Directory>\n"
        "EOF\n"
    )
    s += plat.apache_enable_conf("phpmyadmin")
    s += f"chown -R {plat.web_user}:{plat.web_user} \"$PMA\"\n"
    s += "chmod 1777 \"$PMA/tmp\"\n"
    if plat.has_selinux:
        s += (f"command -v semanage >/dev/null 2>&1 && semanage fcontext -a -t "
              f"httpd_sys_content_t '{served}(/.*)?' 2>/dev/null\n")
        s += (f"command -v semanage >/dev/null 2>&1 && semanage fcontext -a -t "
              f"httpd_sys_rw_content_t '{served}/tmp(/.*)?' 2>/dev/null\n")
        s += "command -v restorecon >/dev/null 2>&1 && restorecon -R \"$PMA\"\n"
        s += ("command -v setsebool >/dev/null 2>&1 && setsebool -P "
              "httpd_can_network_connect_db on 2>/dev/null || true\n")
    s += plat.restart_web()
    return s


def pg_init(plat) -> str:
    """Ensure a postgres cluster exists, then enable+start the service."""
    return plat.pg_ensure_cluster() + "systemctl enable --now postgresql\n"


def pg_login(plat) -> str:
    """Set the postgres password and switch localhost auth to scram-sha-256."""
    return (
        "set -e\n"
        + plat.pg_ensure_cluster()
        + "systemctl enable --now postgresql\n"
        + "sudo -u postgres psql -c \"ALTER USER postgres PASSWORD 'postgres';\"\n"
        + plat.pg_hba_fix()
        + "systemctl reload postgresql\n"
    )


def mariadb_passwordless(sql: str) -> str:
    """Enable MariaDB and run the given SQL (distro-agnostic)."""
    return "systemctl enable --now mariadb\n" + f'mariadb -e "{sql}"\n'


def vhost_create(plat, dom: str, path_escaped: str, vhost_content: str) -> str:
    """Write a name-based vhost, register the host, fix SELinux labels."""
    s = f"cat << 'LOLIEOF' > {plat.apache_conf_dir}/{dom}.conf\n"
    s += vhost_content
    s += "LOLIEOF\n"
    s += plat.apache_enable_site(dom)
    s += f"grep -qxF '127.0.0.1 {dom}' /etc/hosts || echo '127.0.0.1 {dom}' >> /etc/hosts\n"
    s += plat.selinux_fcontext(path_escaped)
    s += plat.selinux_restorecon(path_escaped)
    s += plat.reload_web()
    return s


def vhost_delete(plat, dom: str, dom_sed: str) -> str:
    """Remove a generated vhost + its /etc/hosts entry."""
    s = plat.apache_disable_site(dom)
    s += f"rm -f {plat.apache_conf_dir}/{dom}.conf\n"
    s += f"sed -i '/^127\\.0\\.0\\.1[[:space:]]\\+{dom_sed}$/d' /etc/hosts\n"
    s += plat.reload_web()
    return s


def enable_ssl(plat) -> str:
    """Enable HTTPS for the default site (one-shot, returned as a string)."""
    if plat.id == "debian":
        return "a2enmod ssl && a2ensite default-ssl && systemctl restart apache2"
    return "dnf install -y mod_ssl && systemctl restart httpd"


def php_switch(plat, target: str) -> str:
    """Switch the active PHP version (Debian only; Fedora handles this with an
    info dialog and never calls this)."""
    if plat.id != "debian":
        return ""
    return (
        f"update-alternatives --set php /usr/bin/php{target} || true\n"
        "if command -v a2dismod >/dev/null 2>&1; then\n"
        "a2dismod php* 2>/dev/null || true\n"
        f"a2enmod php{target} 2>/dev/null || true\n"
        "systemctl restart apache2 || true\n"
        "fi\n"
        "systemctl stop php*-fpm 2>/dev/null || true\n"
        f"systemctl enable --now php{target}-fpm || true\n"
        "if [ -f /etc/nginx/sites-available/default ]; then\n"
        f"sed -i -E 's#fastcgi_pass unix:/run/php/php[0-9.]+-fpm\\.sock;#"
        f"fastcgi_pass unix:/run/php/php{target}-fpm.sock;#g' /etc/nginx/sites-available/default\n"
        "systemctl restart nginx || true\n"
        "fi\n"
    )


def php_mailcatcher(plat) -> str:
    """Install a fake sendmail that logs mail, and point php.ini at it."""
    return (
        "echo '#!/bin/bash\ncat >> /tmp/php-mail.log\necho -e \"\\n---END OF MAIL---\\n\" "
        ">> /tmp/php-mail.log' > /usr/local/bin/local-mailcatcher\n"
        "chmod +x /usr/local/bin/local-mailcatcher\n"
        "touch /tmp/php-mail.log && chmod 777 /tmp/php-mail.log\n"
        f"for ini in {plat.php_ini_glob}; do\n"
        "if [ -f \"$ini\" ]; then\n"
        "if grep -q \"sendmail_path\" \"$ini\"; then\n"
        "sed -i 's|^;*sendmail_path .*|sendmail_path = /usr/local/bin/local-mailcatcher|g' \"$ini\"\n"
        "else\n"
        "echo 'sendmail_path = /usr/local/bin/local-mailcatcher' >> \"$ini\"\n"
        "fi\n"
        "fi\n"
        "done\n"
        f"systemctl restart {plat.web_svc} || true\n"
        f"systemctl restart {plat.php_fpm_unit} || true"
    )
