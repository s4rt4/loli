"""Single source of truth for the application version.

Keep this in sync with packaging/loli.spec (Version:) and the Debian changelog.
The previous design hardcoded the version in several places; everything now
imports APP_VERSION from here.
"""

APP_VERSION = "1.0.1"
APP_NAME = "Loli — Localhost Linux"
