"""Reusable Qt UI helpers: logo/icon rendering and small layout widgets."""

import logging
import os

from PyQt6.QtCore import QByteArray, QPoint, QRect, QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
                             QLabel, QLayout, QSizePolicy, QVBoxLayout, QWidget)

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


class FlowLayout(QLayout):
    """A layout that arranges children left-to-right and wraps to the next line
    when it runs out of horizontal space — the building block for a responsive
    card grid (column count follows the available width)."""

    def __init__(self, parent=None, margin=0, hspacing=12, vspacing=12):
        super().__init__(parent)
        self._items = []
        self._hspace = hspacing
        self._vspace = vspacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect, test_only):
        m = self.contentsMargins()
        x = rect.x() + m.left()
        y = rect.y() + m.top()
        right = rect.right() - m.right()
        line_height = 0
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._hspace
            if next_x - self._hspace > right and line_height > 0:
                x = rect.x() + m.left()
                y = y + line_height + self._vspace
                next_x = x + hint.width() + self._hspace
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + m.bottom()


def title_block(title, subtitle):
    """Page title with a grey subtitle underneath, as one widget."""
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(2)
    v.addWidget(QLabel(title, objectName="PageTitle"))
    v.addWidget(QLabel(subtitle, objectName="PageSub"))
    return w
