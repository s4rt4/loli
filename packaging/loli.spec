Name:           loli
Version:        1.0.0
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
install -Dm0644 logo.svg       %{buildroot}%{_datadir}/loli/logo.svg
install -Dm0644 logo-tray.svg  %{buildroot}%{_datadir}/loli/logo-tray.svg
install -Dm0755 loli.launcher  %{buildroot}%{_bindir}/loli
install -Dm0644 loli.desktop   %{buildroot}%{_datadir}/applications/loli.desktop
install -Dm0644 logo.svg       %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/loli.svg

%files
%dir %{_datadir}/loli
%{_datadir}/loli/web_panel.py
%{_datadir}/loli/logo.svg
%{_datadir}/loli/logo-tray.svg
%{_bindir}/loli
%{_datadir}/applications/loli.desktop
%{_datadir}/icons/hicolor/scalable/apps/loli.svg

%changelog
* Sun Jun 07 2026 s4rt4 <surat.sarta@gmail.com> - 1.0.0-1
- Initial RPM: full UI, service management, DB tools, multi-page panel.
