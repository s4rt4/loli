Name:           loli
Version:        1.0.5
Release:        1%{?dist}
Summary:        Loli — Localhost Linux web development panel

License:        MIT
URL:            https://github.com/s4rt4/loli
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

Requires:       python3
Requires:       python3-pyqt6
Requires:       python3-psutil
# Fedora ships this as python3-QtAwesome (capital QtA); needed for the UI icons.
Requires:       python3-QtAwesome
# Privileged actions use pkexec, which needs a polkit authentication agent.
# GNOME/KDE bundle their own; pull a lightweight one for XFCE/minimal sessions.
Recommends:     polkit-gnome

%description
Loli is a desktop control panel for managing a local web development
environment on Linux: Apache/Nginx, PHP-FPM, MariaDB, PostgreSQL, Redis,
Memcached and MongoDB, plus bundled-on-demand phpMyAdmin, pgweb and Mailpit.
Downloadable tools are stored per-user in ~/.local/share/loli.

%prep
%autosetup -n %{name}-%{version}

%build
# Pure Python — nothing to compile.

%install
install -Dm0644 web_panel.py   %{buildroot}%{_datadir}/loli/web_panel.py
install -dm0755 %{buildroot}%{_datadir}/loli/loli
install -m0644 loli/*.py       %{buildroot}%{_datadir}/loli/loli/
install -Dm0644 logo.svg       %{buildroot}%{_datadir}/loli/logo.svg
install -Dm0644 logo-tray.svg  %{buildroot}%{_datadir}/loli/logo-tray.svg
install -dm0755 %{buildroot}%{_datadir}/loli/icons
install -m0644 icons/*.svg     %{buildroot}%{_datadir}/loli/icons/
install -Dm0755 loli.launcher  %{buildroot}%{_bindir}/loli
install -Dm0644 loli.desktop   %{buildroot}%{_datadir}/applications/loli.desktop
install -Dm0644 logo-tray.svg  %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/loli.svg

%files
%dir %{_datadir}/loli
%{_datadir}/loli/web_panel.py
%{_datadir}/loli/loli/
%{_datadir}/loli/logo.svg
%{_datadir}/loli/logo-tray.svg
%{_datadir}/loli/icons/
%{_bindir}/loli
%{_datadir}/applications/loli.desktop
%{_datadir}/icons/hicolor/scalable/apps/loli.svg

%changelog
* Sat Jun 13 2026 s4rt4 <surat.sarta@gmail.com> - 1.0.5-1
- pgweb/mailpit: perbaiki "Operation not permitted" (EPERM) saat start. Binary
  yang sudah executable namun dimiliki user lain (mis. root pada checkout di
  /var/www) gagal di-chmod oleh user; kini chmod dilewati bila bit exec sudah
  ada dan kegagalan chmod tidak lagi membatalkan start.
- phpMyAdmin: kini juga disajikan di bawah nginx. Setup menulis snippet
  /etc/nginx/default.d/phpmyadmin.conf (location + php-fpm) sehingga /phpmyadmin
  bekerja baik saat Apache maupun nginx yang aktif. Sebelumnya nginx membalas 404.

* Sat Jun 13 2026 s4rt4 <surat.sarta@gmail.com> - 1.0.4-1
- phpMyAdmin: perbaiki "403 Forbidden" pada instalasi RPM. Karena DATA_DIR jatuh
  ke ~/.local/share/loli, phpMyAdmin terunduh ke dalam $HOME (mode 0700) yang tak
  bisa di-traverse Apache. Setup kini memindahkannya ke /var/www/loli/phpmyadmin
  (label SELinux httpd_sys_content_t otomatis benar) lalu mengarahkan Alias ke sana.
- Deteksi status phpMyAdmin kini mengenali lokasi staging maupun lokasi tersaji,
  sehingga tidak lagi salah menampilkan "NOT INSTALLED" setelah relokasi.

* Sat Jun 13 2026 s4rt4 <surat.sarta@gmail.com> - 1.0.3-1
- Sidebar: tombol collapse/expand (230px <-> 64px). Saat collapse hanya ikon yang
  tampil; teks menu jadi tooltip, logo & panel System Resources disembunyikan.
  Kondisi terakhir diingat antar sesi (QSettings).
- Dashboard: toggle tampilan List/Card (mirip Google Fonts) untuk Database Tools
  dan Service Status sekaligus. Mode Card memakai grid responsif (jumlah kolom
  mengikuti lebar window). Pilihan tampilan diingat antar sesi.
- Hilangkan warning kosmetik di terminal: tidak membuat tray icon saat sesi tanpa
  system tray (GNOME), dan mendiamkan log registrasi xdg-desktop-portal.

* Thu Jun 11 2026 s4rt4 <surat.sarta@gmail.com> - 1.0.2-1
- Internal refactor (no user-facing changes): the two hand-maintained
  per-distro files are unified into a single `loli/` package. Distro differences
  live behind a Platform descriptor (loli/platform_spec.py) selected at runtime;
  all privileged scripts are centralized in loli/scripts.py and locked by a
  golden test-suite. web_panel.py is now a thin entry-point shim.

* Thu Jun 11 2026 s4rt4 <surat.sarta@gmail.com> - 1.0.1-1
- UI refresh: modern slate/Tailwind palette, softer radii, card drop shadows.
- Page headers gain subtitles; status pills and inputs polished.
- Custom Lucide SVG icons for the sidebar (recolored, active-state tint) and
  dashboard start/stop/restart/open actions, with Font Awesome fallback.
- Sidebar brand simplified to a recolored logo only (text removed).
- App/launcher/dock/window icon now uses the clean recolored lollipop.
- About page reports the correct version (1.0.1).

* Sun Jun 07 2026 s4rt4 <surat.sarta@gmail.com> - 1.0.0-1
- Initial RPM: full UI, service management, DB tools, multi-page panel.
