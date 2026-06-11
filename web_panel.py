#!/usr/bin/env python3
"""Entry-point shim — the implementation now lives in the ``loli`` package.

Kept at this path so existing launchers / .desktop files keep working; it simply
delegates to :func:`loli.app.main`. Distro selection happens inside the package
(``loli.platform_spec``), so this single entry point serves both Fedora and
Debian/Ubuntu.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loli.app import main

if __name__ == "__main__":
    main()
