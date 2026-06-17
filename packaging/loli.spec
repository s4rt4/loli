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
* Wed Jun 17 2026 s4rt4 <surat.sarta@gmail.com> - 1.0.5-1
- Further reduce resize flicker: the content viewport, page stack and each page
  now fill a solid background colour, so a rapid resize erases exposed areas to
  the panel background instead of flashing black.

* Wed Jun 17 2026 s4rt4 <surat.sarta@gmail.com> - 1.0.4-1
- UI polish: animated sidebar collapse, slim global scrollbars, :pressed/:disabled
  button states, busy feedback on service action buttons, and corrected stray
  Flat-UI accent colors in the system-resource panel.
- Fix dark-mode bugs: tray-menu icons now follow the desktop palette (were dark
  on a dark menu), and the Logs page tab bar gets explicit colors so its text is
  readable in dark mode.
- Fix UI flicker on rapid window resize by dropping the per-card drop-shadow
  graphics effect in favor of a lightweight styled border.

* Sat Jun 13 2026 s4rt4 <surat.sarta@gmail.com> - 1.0.3-1
- Sidebar can now collapse to an icon-only rail (toggle at the top); the nav
  menu scrolls so the system-resource bars stay pinned and never overlap.
- Fix dashboard service-status action buttons (Start/Stop/Restart) stretching
  wide when the sidebar is collapsed.

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
