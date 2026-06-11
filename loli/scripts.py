"""Root-script builders.

Every privileged shell script the panel runs via pkexec is assembled here,
parametrized by a :class:`~loli.platform_spec.Platform`. Each builder reproduces
byte-for-byte what the original per-distro files generated (locked by
tests/test_scripts.py) so unifying the two files changes no behaviour.
"""

import shlex


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


def phpmyadmin_setup(plat, pma: str, pma_q: str, tmp_q: str) -> str:
    """Drop the phpMyAdmin config + apache alias and fix ownership/labels.

    ``pma`` is the raw install dir, ``pma_q``/``tmp_q`` are shlex.quote'd.
    """
    s = (
        f"PMA={pma_q}\n"
        f"cp {tmp_q} \"$PMA/config.inc.php\"\n"
        "mkdir -p \"$PMA/tmp\"\n"
        f"cat << 'EOF' > {plat.phpmyadmin_conf}\n"
        f"Alias /phpmyadmin {pma}\n"
        f"<Directory {pma}>\n"
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
              f"httpd_sys_content_t '{pma}(/.*)?' 2>/dev/null\n")
        s += (f"command -v semanage >/dev/null 2>&1 && semanage fcontext -a -t "
              f"httpd_sys_rw_content_t '{pma}/tmp(/.*)?' 2>/dev/null\n")
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
