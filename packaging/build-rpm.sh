#!/bin/bash
# Build the Loli .rpm. Requires: rpm-build (and rpmdevtools optional).
#   sudo dnf install -y rpm-build
# Usage: packaging/build-rpm.sh   (run from the repo root or anywhere)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC="$REPO_ROOT/packaging/loli.spec"
NAME=loli
VERSION="$(awk '/^Version:/{print $2}' "$SPEC")"
TOPDIR="$REPO_ROOT/build/rpm"
STAGE="$TOPDIR/SOURCES/${NAME}-${VERSION}"

echo ">> Building ${NAME} ${VERSION}"
rm -rf "$TOPDIR"
mkdir -p "$TOPDIR"/{BUILD,RPMS,SOURCES,SPECS,SRPMS} "$STAGE"

# Stage the files that go into the package
cp "$REPO_ROOT/web_panel.py"            "$STAGE/"
cp -r "$REPO_ROOT/loli"                 "$STAGE/"
rm -rf "$STAGE/loli/__pycache__"
cp "$REPO_ROOT/logo.svg"                "$STAGE/"
cp "$REPO_ROOT/logo-tray.svg"           "$STAGE/"
cp -r "$REPO_ROOT/icons"                "$STAGE/"
cp "$REPO_ROOT/packaging/loli.launcher" "$STAGE/"
cp "$REPO_ROOT/packaging/loli.desktop"  "$STAGE/"

# Source tarball
( cd "$TOPDIR/SOURCES" && tar czf "${NAME}-${VERSION}.tar.gz" "${NAME}-${VERSION}" )

# Build (binary only)
rpmbuild --define "_topdir $TOPDIR" -bb "$SPEC"

# Collect output
OUT="$REPO_ROOT/dist"
mkdir -p "$OUT"
find "$TOPDIR/RPMS" -name '*.rpm' -exec cp {} "$OUT/" \;
echo ">> Done. RPM(s) in: $OUT"
ls -1 "$OUT"/*.rpm
