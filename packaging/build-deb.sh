#!/bin/bash
# Build the Loli .deb. Requires: dpkg-dev debhelper
#   sudo apt-get install -y dpkg-dev debhelper
# Usage: packaging/build-deb.sh   (run from the repo root or anywhere)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VERSION="$(dpkg-parsechangelog -SVersion)"
echo ">> Building loli ${VERSION}"

# Binary-only build, unsigned. Artifacts land in the parent dir by default.
dpkg-buildpackage -us -uc -b

# Collect output into dist/ (matches build-rpm.sh)
OUT="$REPO_ROOT/dist"
mkdir -p "$OUT"
find "$REPO_ROOT/.." -maxdepth 1 -name "loli_${VERSION}_*.deb" -exec cp {} "$OUT/" \;
echo ">> Done. .deb(s) in: $OUT"
ls -1 "$OUT"/*.deb 2>/dev/null || true
