"""Reusable Qt UI helpers: logo/icon rendering and small layout widgets."""

import logging
import os

from PyQt6.QtCore import QByteArray, QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
                             QLabel, QVBoxLayout, QWidget)

from .config import ICON_DIR, LOGO_PATH

try:
    import qtawesome as qta
    HAS_ICONS = True
except ImportError:
    HAS_ICONS = False


def load_logo_pixmap(size: int, path: str = LOGO_PATH):
    """Render an SVG logo to a full square pixmap (no QIcon.pixmap clipping)."""
    if not os.path.exists(path):
        return None
    try:
        renderer = QSvgRenderer(path)
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        renderer.render(painter)
        painter.end()
        return pm
    except Exception as e:
        logging.warning(f"Failed to render logo: {e}")
        pm = QIcon(path).pixmap(QSize(size, size))
        return pm if not pm.isNull() else None


# Font Awesome name -> local SVG file (icons/<name>.svg). Buttons using these
# names automatically pick up the bundled SVG when present.
_SVG_FOR_QTA = {
    "fa5s.play": "start",
    "fa5s.stop": "stop",
    "fa5s.sync": "restart",
    "fa5s.external-link-alt": "open",
}


def svg_icon(name, color="#cbd5e1", size=24):
    """Render a Lucide SVG (icons/<name>.svg) to a tinted QIcon by replacing
    'currentColor'. Returns None if the file is missing."""
    if not name:
        return None
    path = os.path.join(ICON_DIR, name + ".svg")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = f.read().replace("currentColor", color)
        renderer = QSvgRenderer(QByteArray(data.encode("utf-8")))
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        renderer.render(painter)
        painter.end()
        return QIcon(pm)
    except Exception as e:
        logging.warning(f"svg_icon failed for {name}: {e}")
        return None


def app_icon(qta_name, color="#334155", size=24):
    """Local SVG if a mapping exists and the file is present, else fall back to
    qtawesome (Font Awesome)."""
    svg = _SVG_FOR_QTA.get(qta_name)
    if svg:
        ic = svg_icon(svg, color, size)
        if ic is not None:
            return ic
    if HAS_ICONS:
        return qta.icon(qta_name, color=color)
    return QIcon()


class Card(QFrame):
    def __init__(self, layout_type="v"):
        super().__init__()
        self.setObjectName("Card")
        self.layout = QVBoxLayout() if layout_type == "v" else QHBoxLayout()
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(10)
        self.setLayout(self.layout)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(15, 23, 42, 28))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)


def title_block(title, subtitle):
    """Page title with a grey subtitle underneath, as one widget."""
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(2)
    v.addWidget(QLabel(title, objectName="PageTitle"))
    v.addWidget(QLabel(subtitle, objectName="PageSub"))
    return w
