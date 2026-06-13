<p align="center">
  <img src="logo.svg" alt="Loli" width="110">
</p>

<h1 align="center">Loli — Localhost Linux</h1>

<p align="center">
  Panel desktop ringan untuk mengelola environment web development lokal di <b>Linux</b>.
</p>

---

Loli adalah panel kontrol GUI (PyQt6) bergaya Laragon/XAMPP untuk Linux: kontrol service, kelola database, lihat proses, dan utilitas dev lokal dalam satu jendela. Satu entry point (`web_panel.py`) melayani kedua keluarga distro; perbedaannya dipilih otomatis saat runtime lewat `loli/platform_spec.py`:

- **Fedora / RHEL** — httpd, php-fpm tunggal, `dnf`, SELinux ditangani otomatis, valkey.
- **Debian / Ubuntu** — apache2, multi-versi PHP via `a2enmod`/`update-alternatives`, `apt`, redis-server.

Deteksi memakai `/etc/os-release`; paksa salah satu dengan env `LOLI_PLATFORM=fedora` atau `LOLI_PLATFORM=debian`.

## Fitur

- **Dashboard** — start/stop/restart service (Apache, Nginx, MariaDB, PostgreSQL, Redis, Memcached, MongoDB), lengkap dengan tombol *Install* untuk service yang belum terpasang.
- **Database Tools** — phpMyAdmin (setup otomatis), pgweb, dan Mailpit (unduh & jalankan saat dibutuhkan).
- **Projects** — scan web root, deteksi tipe project (Laravel, WordPress, Node.js, Go, Python, PHP), aksi cepat: browser, file manager, terminal, editor.
- **PHP Manager** — info versi + toggle ekstensi. Di Debian: berpindah versi PHP (Apache & Nginx) otomatis.
- **Port Sniper** — pindai port aktif & hentikan prosesnya.
- **Process Monitor** — daftar proses + filter + kill.
- **Config Editor** — edit file konfigurasi server.
- **Logs** — penampil log tab (journalctl: Apache, PHP-FPM, MariaDB, PostgreSQL, Nginx).
- **Discovery** — peta path penting yang terdeteksi otomatis.
- **Utilities** — fix permission, virtual host `.test`/`.local` (auto update `/etc/hosts`), dan setup database (Init PostgreSQL, PostgreSQL Login, MariaDB Passwordless).
- **UI** — status pill, bar resource berwarna sesuai beban, hover, dan system tray (menu ala-Laragon).

## Instalasi (Fedora — .rpm)

Ambil dari [Releases](https://github.com/s4rt4/loli/releases):

```bash
sudo dnf install -y https://github.com/s4rt4/loli/releases/download/v1.0.0/loli-1.0.0-1.fc43.noarch.rpm
loli   # atau buka "Loli" dari menu aplikasi
```

Membangun ulang dari sumber: `sudo dnf install -y rpm-build` lalu `bash packaging/build-rpm.sh` (hasil di `dist/`).

## Menjalankan dari sumber

```bash
python3 -m pip install --user PyQt6 psutil qtawesome
python3 web_panel.py        # distro terdeteksi otomatis (Fedora / Debian / Ubuntu)
```

Aset pihak ketiga (tidak disertakan di repo) diunduh otomatis lewat tombol *Download* di aplikasi: `pgweb`, `phpmyadmin/`, `mailpit`. Saat Loli terinstal sistem (read-only), unduhan disimpan per-user di `~/.local/share/loli`.

## Kompatibilitas desktop

| Desktop | Status |
|---------|--------|
| **GNOME** | Berjalan. Tray butuh ekstensi `gnome-shell-extension-appindicator` agar ikon tray tampil; tanpa itu Loli minimize biasa. |
| **KDE Plasma** | Berjalan mulus; tray native berfungsi penuh. |
| **XFCE / LXQt / WM minimalis** | Berjalan. Aksi root memakai `pkexec`, jadi **perlu agen autentikasi polkit** (mis. `lxpolkit`, `polkit-gnome`). Loli mendeteksi & memperingatkan bila agen tidak berjalan. |

## Arsitektur

- Operasi privileged dijalankan via `pkexec` di **background thread** (`run_async`) agar UI tidak freeze.
- Logo: `logo.svg`. Packaging RPM: `packaging/`.
- Ditujukan untuk server lokal/development, bukan produksi.

## Lisensi

MIT.
