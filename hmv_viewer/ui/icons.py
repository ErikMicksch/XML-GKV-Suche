"""Linien-Symbole als SVG (eigene Zeichnung, 24 × 24, scharf in jeder Größe) – in QML: image://icon/<name>/<farbe>."""
from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtQuick import QQuickImageProvider
from PySide6.QtSvg import QSvgRenderer

_HEAD = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
         'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">')
_DOT = '<circle cx="{x}" cy="{y}" r="1.1" fill="currentColor" stroke="none"/>'
_STAR = "12 2.6 14.9 8.6 21.5 9.5 16.7 14.1 17.9 20.6 12 17.5 6.1 20.6 7.3 14.1 2.5 9.5 9.1 8.6"

ICONS = {
    "search": '<circle cx="11" cy="11" r="7"/><path d="M20.5 20.5 16 16"/>',
    "home": '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"/>',
    "box": '<path d="M21 8 12 3 3 8v8l9 5 9-5z"/><path d="M3 8l9 5 9-5M12 13v8"/>',
    "history": '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/>',
    "comment": '<path d="M5 4h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H10l-5 4v-4H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"/>',
    "star": f'<polygon points="{_STAR}"/>',
    "starFilled": f'<polygon points="{_STAR}" fill="currentColor"/>',
    "list": '<path d="M9 6h12M9 12h12M9 18h12"/>' + "".join(_DOT.format(x=4.5, y=y) for y in (6, 12, 18)),
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "close": '<path d="M6 6l12 12M18 6 6 18"/>',
    "copy": '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1"/>',
    "import": '<path d="M12 3v12M7 10l5 5 5-5M4 17v3h16v-3"/>',
    "export": '<path d="M12 15V3M7 8l5-5 5 5M4 17v3h16v-3"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "menu": '<path d="M4 6h16M4 12h16M4 18h16"/>',
    "help": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6v.6"/>'
            + _DOT.format(x=12, y=17),
    "bell": '<path d="M6 16v-5a6 6 0 0 1 12 0v5l2 2H4z"/><path d="M10 21h4"/>',
    "tag": '<path d="M3 12V4a1 1 0 0 1 1-1h8l9 9-9 9z"/><circle cx="7.5" cy="7.5" r="1.5"/>',
    "save": '<path d="M5 3h11l5 5v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M8 3v5h7M7 21v-7h10v7"/>',
    "paste": '<rect x="5" y="4" width="14" height="17" rx="2"/><rect x="9" y="2" width="6" height="4" rx="1"/>',
    "compare": '<rect x="3" y="4" width="7" height="16" rx="1.5"/><rect x="14" y="4" width="7" height="16" rx="1.5"/>',
    "undo": '<path d="M9 14 4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/>',
    "table": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M3 15h18M9 10v10"/>',
    "cards": '<rect x="3" y="3" width="8" height="8" rx="1.5"/><rect x="13" y="3" width="8" height="8" rx="1.5"/>'
             '<rect x="3" y="13" width="8" height="8" rx="1.5"/><rect x="13" y="13" width="8" height="8" rx="1.5"/>',
    "folder": '<path d="M3 6a1 1 0 0 1 1-1h5l2 2h9a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z"/>',
    "trash": '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
    "edit": '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13 7l4 4"/>',
    "chevronRight": '<path d="M9 6l6 6-6 6"/>',
    "chevronDown": '<path d="M6 9l6 6 6-6"/>',
    "chevronUp": '<path d="M6 15l6-6 6 6"/>',
    "arrowUp": '<path d="M12 19V5M5 12l7-7 7 7"/>',
    "arrowDown": '<path d="M12 5v14M5 12l7 7 7-7"/>',
    "filter": '<path d="M4 5h16l-6 7v6l-4 2v-8z"/>',
    "settings": '<path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1"/>'
                '<circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="18" r="2"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6"/>' + _DOT.format(x=12, y=7.5),
    "check": '<path d="M5 12l5 5 9-10"/>',
    "alert": '<path d="M12 3 2 20h20z"/><path d="M12 9v5"/>' + _DOT.format(x=12, y=17),
    "database": '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/>'
                '<path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
    "external": '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    "palette": '<path d="M12 3a9 9 0 1 0 0 18c1 0 1.5-.8 1.5-1.5 0-.4-.2-.8-.4-1-.3-.3-.4-.6-.4-1 0-.8.7-1.5 1.5-1.5H16'
               'a5 5 0 0 0 5-5c0-4.4-4-8-9-8z"/>' + "".join(_DOT.format(x=x, y=y) for x, y in ((7.5, 11), (10, 7), (15, 7))),
    "keyboard": '<rect x="2" y="6" width="20" height="12" rx="2"/><path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10"/>',
    "refresh": '<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/>',
    "dots": "".join(_DOT.format(x=x, y=12) for x in (5, 12, 19)),
    "zap": '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
    "drag": "".join(_DOT.format(x=x, y=y) for x in (9, 15) for y in (6, 12, 18)),
}


def svg(name):
    return _HEAD + ICONS.get(name, ICONS["dots"]) + "</svg>"


class IconProvider(QQuickImageProvider):
    """image://icon/<name>/<RRGGBB oder AARRGGBB> – Farbe ohne „#“ (sonst Teil der URL)."""

    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Image)

    def requestImage(self, ident, size, requested):
        name, _, color = ident.partition("/")
        color = "#" + (color or "000000")[-6:]   # SVG kennt kein #AARRGGBB – Deckkraft regelt QML
        w = requested.width() if requested.width() > 0 else 48
        h = requested.height() if requested.height() > 0 else w
        img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        renderer = QSvgRenderer(QByteArray(svg(name).replace("currentColor", color).encode()))
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(p, QRectF(0, 0, w, h))
        p.end()
        if size is not None:
            size.setWidth(w)
            size.setHeight(h)
        return img
