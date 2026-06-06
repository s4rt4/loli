<p align="center">
  <img src="logo.svg" alt="Loli" width="110">
</p>

<h1 align="center">Loli — Localhost Linux</h1>

<p align="center">
  Panel desktop ringan untuk mengelola environment web development lokal di <b>Linux (Fedora-first)</b>.
</p>

---

Loli adalah panel kontrol GUI (PyQt6) bergaya Laragon/XAMPP untuk Linux: kontrol service, kelola database, lihat proses, dan utilitas dev lokal dalam satu jendela. Dibangun dan dioptimalkan untuk **Fedora** (httpd, php-fpm, MariaDB, PostgreSQL, dll).

## Fitur

- **Dashboard** — start/stop/restart service (Apache/httpd, Nginx, MariaDB, PostgreSQL, Valkey/Redis, Memcached, MongoDB), termasuk tombol *Install* untuk service yang belum ada.
- **Database Tools** — phpMyAdmin (setup otomatis: alias Apache + SELinux + AllowNoPassword), pgweb, dan Mailpit (unduh & jalankan).
- **Projects** — scan web root, deteksi tipe project (Laravel, WordPress, Node.js, Go, Python, PHP), aksi cepat: browser, file manager, terminal, editor.
- **PHP Manager** — info versi + toggle ekstensi (via dnf).
- **Port Sniper** — pindai port aktif & hentikan prosesnya.
- **Process Monitor** — daftar proses + filter + kill.
- **Config Editor** — edit file konfigurasi server.
- **Logs** — penampil log tab (journalctl: Apache, PHP-FPM, MariaDB, PostgreSQL, Nginx).
- **Discovery** — peta path penting yang terdeteksi otomatis.
- **Utilities** — fix permission, virtual host `.test`/`.local` (auto update `/etc/hosts`), dan setup database (Init PostgreSQL, PostgreSQL Login, MariaDB Passwordless).

## Arsitektur

- Satu file: `web_panel.py` (PyQt6).
- Operasi privileged dijalankan via `pkexec` di **background thread** (`run_async`) agar UI tidak freeze.
- Logo: `logo.svg`.

## Menjalankan

```bash
python3 web_panel.py
```

### Dependensi

```bash
python3 -m pip install --user PyQt6 psutil qtawesome
```

Aset pihak ketiga (tidak disertakan di repo): letakkan di folder yang sama —
- `pgweb_linux_amd64` (client PostgreSQL web)
- `phpmyadmin/` (sumber phpMyAdmin)
- `mailpit` (otomatis diunduh lewat tombol Download)

## Catatan

- **Fedora-first.** Versi Debian/Ubuntu (`web_panel_deb.py`) menyusul.
- Ditujukan untuk server lokal/development, bukan produksi.

## Lisensi

MIT.
