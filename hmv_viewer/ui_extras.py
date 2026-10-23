"""Bausteine der Oberfläche: gezeichnete Icons, Hinweis-Einblendung (Toast), aufklappbare Abschnitte, Befehlspalette,
Vergleich, Nummernliste, Startseite (Kacheln + Diagramm), Kartenansicht, Kommentare und kleine Dialoge.

Farben kommen zur Laufzeit aus gui.py (dort stellt apply_theme die Farbwelt um), daher immer über _c().
"""
from __future__ import annotations

import html
import re

from PySide6.QtCore import QEasingCurve, QEvent, QPointF, QPropertyAnimation, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QDialog, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton, QSizePolicy, QTableWidget,
    QTableWidgetItem, QTextBrowser, QToolButton, QVBoxLayout, QWidget,
)

NUMMER_RE = re.compile(r"(?<!\d)(\d{2})\.?(\d{2})\.?(\d{2})\.?(\d)\.?(\d{3})(?!\d)")


def _c(name):
    from . import gui   # Farbwelt zur Laufzeit (nach apply_theme)
    return getattr(gui, name)


# ---------------------------------------------------------------------------------------------- Icons
def make_icon(name, color=None, size=18):
    """Einfache Linien-Icons, mit QPainter gezeichnet (keine Bilddateien, keine Emojis)."""
    scale = 2
    pix = QPixmap(size * scale, size * scale)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size * scale / 24, size * scale / 24)   # Zeichnung im 24er-Raster
    col = QColor(color or _c("TEXT"))
    pen = QPen(col, 1.9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath()

    def star(filled):
        import math
        pts = []
        for i in range(10):
            r = 9.5 if i % 2 == 0 else 4.2
            a = -math.pi / 2 + i * math.pi / 5
            pts.append(QPointF(12 + r * math.cos(a), 12.5 + r * math.sin(a)))
        sp = QPainterPath(pts[0])
        for pt in pts[1:]:
            sp.lineTo(pt)
        sp.closeSubpath()
        if filled:
            p.setBrush(col)
        p.drawPath(sp)

    if name == "star":
        star(True)
    elif name == "star_outline":
        star(False)
    elif name == "list":
        for y in (6, 12, 18):
            p.drawLine(QPointF(9, y), QPointF(20, y))
            p.drawPoint(QPointF(4.5, y))
            p.drawEllipse(QPointF(4.5, y), 0.8, 0.8)
    elif name == "note":
        p.drawRoundedRect(QRectF(4, 3, 16, 18), 2, 2)
        for y in (8, 12, 16):
            p.drawLine(QPointF(8, y), QPointF(16, y))
    elif name == "comment":
        path.addRoundedRect(QRectF(3, 4, 18, 13), 3, 3)
        p.drawPath(path)
        p.drawLine(QPointF(8, 17), QPointF(6, 21))
        p.drawLine(QPointF(6, 21), QPointF(11, 17))
    elif name == "copy":
        p.drawRoundedRect(QRectF(8, 8, 12, 13), 2, 2)
        p.drawPolyline([QPointF(5, 16), QPointF(4, 16), QPointF(4, 4), QPointF(15, 4), QPointF(15, 6)])
    elif name in ("export", "import"):
        p.drawPolyline([QPointF(4, 14), QPointF(4, 20), QPointF(20, 20), QPointF(20, 14)])
        if name == "export":
            p.drawLine(QPointF(12, 15), QPointF(12, 3))
            p.drawPolyline([QPointF(7, 8), QPointF(12, 3), QPointF(17, 8)])
        else:
            p.drawLine(QPointF(12, 3), QPointF(12, 15))
            p.drawPolyline([QPointF(7, 10), QPointF(12, 15), QPointF(17, 10)])
    elif name == "search":
        p.drawEllipse(QPointF(10.5, 10.5), 6.5, 6.5)
        p.drawLine(QPointF(15.5, 15.5), QPointF(20.5, 20.5))
    elif name == "user":
        p.drawEllipse(QPointF(12, 8), 4, 4)
        path.moveTo(4, 21)
        path.cubicTo(5, 14, 19, 14, 20, 21)
        p.drawPath(path)
    elif name == "menu":
        for y in (6, 12, 18):
            p.drawLine(QPointF(4, y), QPointF(20, y))
    elif name == "home":
        p.drawPolyline([QPointF(3, 11), QPointF(12, 3), QPointF(21, 11)])
        p.drawPolyline([QPointF(6, 9), QPointF(6, 21), QPointF(18, 21), QPointF(18, 9)])
        p.drawRect(QRectF(10, 14, 4, 7))
    elif name == "box":
        p.drawPolygon([QPointF(12, 3), QPointF(21, 7.5), QPointF(12, 12), QPointF(3, 7.5)])
        p.drawPolyline([QPointF(3, 7.5), QPointF(3, 16.5), QPointF(12, 21), QPointF(21, 16.5), QPointF(21, 7.5)])
        p.drawLine(QPointF(12, 12), QPointF(12, 21))
    elif name == "history":
        p.drawArc(QRectF(3.5, 3.5, 17, 17), 100 * 16, 300 * 16)
        p.drawPolyline([QPointF(3, 5), QPointF(4.2, 9), QPointF(8, 8)])
        p.drawPolyline([QPointF(12, 8), QPointF(12, 12.5), QPointF(15, 14.5)])
    elif name == "compare":
        p.drawRoundedRect(QRectF(3, 4, 7.5, 16), 1.5, 1.5)
        p.drawRoundedRect(QRectF(13.5, 4, 7.5, 16), 1.5, 1.5)
    elif name == "undo":
        p.drawPolyline([QPointF(8, 5), QPointF(4, 9), QPointF(8, 13)])
        path.moveTo(4, 9)
        path.cubicTo(16, 9, 21, 12, 19, 19)
        p.drawPath(path)
    elif name == "cards":
        for x, y in ((3, 3), (13, 3), (3, 13), (13, 13)):
            p.drawRoundedRect(QRectF(x, y, 8, 8), 1.5, 1.5)
    elif name == "table":
        p.drawRoundedRect(QRectF(3, 4, 18, 16), 2, 2)
        p.drawLine(QPointF(3, 9.5), QPointF(21, 9.5))
        p.drawLine(QPointF(3, 15), QPointF(21, 15))
        p.drawLine(QPointF(9, 9.5), QPointF(9, 20))
    elif name == "bell":
        path.moveTo(6, 17)
        path.lineTo(6, 11)
        path.cubicTo(6, 4, 18, 4, 18, 11)
        path.lineTo(18, 17)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(QPointF(4, 17), QPointF(20, 17))
        p.drawArc(QRectF(10, 18, 4, 4), 180 * 16, 180 * 16)
    elif name == "plus":
        p.drawLine(QPointF(12, 5), QPointF(12, 19))
        p.drawLine(QPointF(5, 12), QPointF(19, 12))
    elif name == "info":
        p.drawEllipse(QPointF(12, 12), 9, 9)
        p.drawLine(QPointF(12, 11), QPointF(12, 17))
        p.drawPoint(QPointF(12, 7.5))
    elif name == "save":
        p.drawRoundedRect(QRectF(4, 4, 16, 16), 2, 2)
        p.drawRect(QRectF(8, 4, 8, 5))
        p.drawRect(QRectF(7.5, 13, 9, 7))
    elif name == "paste":
        p.drawRoundedRect(QRectF(5, 5, 14, 16), 2, 2)
        p.drawRoundedRect(QRectF(9, 3, 6, 4), 1, 1)
        p.drawLine(QPointF(9, 12), QPointF(15, 12))
        p.drawLine(QPointF(9, 16), QPointF(15, 16))
    elif name == "tag":
        p.drawPolygon([QPointF(3, 3), QPointF(12, 3), QPointF(21, 12), QPointF(12, 21), QPointF(3, 12)])
        p.drawEllipse(QPointF(8, 8), 1.4, 1.4)
    elif name == "chevron_right":
        p.drawPolyline([QPointF(9, 6), QPointF(15, 12), QPointF(9, 18)])
    elif name == "chevron_down":
        p.drawPolyline([QPointF(6, 9), QPointF(12, 15), QPointF(18, 9)])
    elif name == "command":
        p.drawRoundedRect(QRectF(3, 5, 18, 14), 3, 3)
        p.drawPolyline([QPointF(7, 10), QPointF(10, 12), QPointF(7, 14)])
        p.drawLine(QPointF(12, 14.5), QPointF(17, 14.5))
    p.end()
    pix.setDevicePixelRatio(scale)
    return QIcon(pix)


# ---------------------------------------------------------------------------------------------- Animation
def fade_in(widget, ms=170):
    """Sanftes Einblenden; der Effekt wird danach entfernt (sonst bremst er das Zeichnen)."""
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(ms)
    anim.setStartValue(0.35)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


# ---------------------------------------------------------------------------------------------- Toast
class Toast(QFrame):
    """Kurze Einblendung unten rechts, optional mit Aktion (z. B. „Rückgängig“)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("toast")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 10, 10, 10)
        self.label = QLabel(objectName="toastText", wordWrap=True)
        self.label.setMaximumWidth(420)
        self.button = QPushButton(objectName="toastButton")
        self.button.clicked.connect(self._run)
        lay.addWidget(self.label, 1)
        lay.addWidget(self.button)
        self._action = None
        self.timer = QTimer(self, singleShot=True, timeout=self.hide)
        parent.installEventFilter(self)
        self.hide()

    def show_message(self, text, action_text=None, action=None, ms=4500):
        self.label.setText(text)
        self._action = action
        self.button.setVisible(bool(action))
        self.button.setText(action_text or "")
        self.adjustSize()
        self._place()
        self.show()
        self.raise_()
        fade_in(self, 140)
        self.timer.start(ms)

    def _run(self):
        action, self._action = self._action, None
        self.hide()
        if action:
            action()

    def _place(self):
        par = self.parentWidget()
        self.move(par.width() - self.width() - 24, par.height() - self.height() - 44)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize and self.isVisible():
            self._place()
        return False


# ---------------------------------------------------------------------------------------------- Abschnitt
class CollapsibleSection(QWidget):
    linkActivated = Signal(str)

    def __init__(self, title, expanded=True):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(4)
        self.header = QToolButton(text=title, checkable=True, checked=expanded, objectName="sectionHeader")
        self.header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.header.toggled.connect(self._toggle)
        self.body = QLabel(wordWrap=True, objectName="sectionBody")
        self.body.setTextFormat(Qt.TextFormat.RichText)
        self.body.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.body.linkActivated.connect(self.linkActivated)
        lay.addWidget(self.header)
        lay.addWidget(self.body)
        self._toggle(expanded)

    def _toggle(self, on):
        self.body.setVisible(on)
        self.header.setIcon(make_icon("chevron_down" if on else "chevron_right", _c("MUTED"), 14))

    def set_html(self, text):
        self.body.setText(text)
        self.setVisible(bool(text))


# ---------------------------------------------------------------------------------------------- Befehlspalette
class CommandPalette(QDialog):
    """Strg+K: ein Feld für alles – Produkte, Gruppen, Listen und Funktionen."""

    def __init__(self, parent, provider):
        super().__init__(parent)
        self.setWindowTitle("Schnellzugriff")
        self.setMinimumSize(640, 460)
        self.provider = provider
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 12)
        self.edit = QLineEdit(objectName="search", clearButtonEnabled=True,
                              placeholderText="Produkt, Nummer, Gruppe, Liste oder Funktion …")
        self.edit.addAction(make_icon("search", _c("MUTED")), QLineEdit.ActionPosition.LeadingPosition)
        self.list = QListWidget(objectName="palette")
        self.list.setIconSize(QSize(18, 18))
        self.list.itemActivated.connect(self._run)
        self.hint = QLabel("↑↓ auswählen · Enter ausführen · Esc schließen", objectName="muted")
        lay.addWidget(self.edit)
        lay.addWidget(self.list, 1)
        lay.addWidget(self.hint)
        self.timer = QTimer(self, singleShot=True, interval=120, timeout=self._refresh)
        self.edit.textChanged.connect(lambda: self.timer.start())
        self.edit.installEventFilter(self)
        self._refresh()

    def _refresh(self):
        self.list.clear()
        for icon, title, sub, fn in self.provider(self.edit.text().strip())[:60]:
            item = QListWidgetItem(icon, f"{title}" + (f"   ·   {sub}" if sub else ""))
            item.setData(Qt.ItemDataRole.UserRole, fn)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                row = self.list.currentRow() + (1 if event.key() == Qt.Key.Key_Down else -1)
                self.list.setCurrentRow(max(0, min(self.list.count() - 1, row)))
                return True
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.list.currentItem():
                    self._run(self.list.currentItem())
                return True
        return super().eventFilter(obj, event)

    def _run(self, item):
        fn = item.data(Qt.ItemDataRole.UserRole)
        self.accept()
        if fn:
            QTimer.singleShot(0, fn)


# ---------------------------------------------------------------------------------------------- Vergleich
from .merkmale import parse_merkmale  # noqa: E402 – eine Zerlegung für Detail, Suche und Vergleich


class CompareDialog(QDialog):
    """Vergleichstabelle: links die Eigenschaften, je Produkt eine Spalte; Abschnitte „Allgemein“ und „Merkmale“.

    products: Liste von dicts (Produktzeile + nummer_fmt, aufnahme, status); on_add(): weitere Produkte wählen.
    """

    GENERAL = (("Hilfsmittelnummer", "nummer_fmt"), ("Bezeichnung", "bezeichnung"), ("Hersteller", "hersteller"),
               ("Produktart", None), ("Aufnahme", "aufnahme"), ("Status", "status"))

    def __init__(self, parent, products, names, on_add=None):
        super().__init__(parent)
        self.names, self.on_add = names, on_add
        self.setMinimumSize(900, 600)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 12)
        top = QHBoxLayout()
        self.title = QLabel(objectName="cardTitle")
        top.addWidget(self.title, 1)
        from PySide6.QtWidgets import QCheckBox
        self.only_diff = QCheckBox("Nur Unterschiede anzeigen")
        self.only_diff.toggled.connect(lambda *_: self._build())
        top.addWidget(self.only_diff)
        lay.addLayout(top)
        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ContiguousSelection)
        self.table.setWordWrap(True)
        self.table.setShowGrid(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self.table, 1)
        self.legend = QLabel(objectName="muted")
        lay.addWidget(self.legend)
        row = QHBoxLayout()
        if on_add:
            add = QPushButton("Weiteres Produkt hinzufügen …", clicked=self._add)
            add.setIcon(make_icon("plus", _c("GREEN"), 16))
            row.addWidget(add)
        copy = QPushButton("Als Tabelle kopieren", clicked=self._copy)
        copy.setIcon(make_icon("copy", _c("GREEN"), 16))
        row.addWidget(copy)
        row.addStretch(1)
        row.addWidget(QPushButton("Schließen", objectName="primary", clicked=self.accept))
        lay.addLayout(row)
        self.set_products(products)

    def set_products(self, products):
        self.products = products[:6]
        self.setWindowTitle(f"Vergleich von {len(self.products)} Produkten")
        self.title.setText(f"Vergleich von {len(self.products)} Produkten")
        self.resize(min(1500, 260 + 290 * len(self.products)), 700)
        self._build()

    def _rows(self):
        """[(Abschnitt oder None, Eigenschaft, [Werte je Produkt])]"""
        out = [("Allgemein", None, None)]
        for label, key in self.GENERAL:
            values = [(self.names.path(p)["art"] if key is None else str(p.get(key) or "")) for p in self.products]
            out.append((None, label, values))
        merk = [parse_merkmale(p.get("merkmale")) for p in self.products]
        keys = []
        for m in merk:
            keys += [k for k in m if k not in keys]
        if keys:
            out.append(("Merkmale", None, None))
            out += [(None, k, [m.get(k, "–") for m in merk]) for k in keys]
        return out

    def _build(self):
        rows = self._rows()
        if self.only_diff.isChecked():
            rows = [r for r in rows if r[0] or len(set(r[2])) > 1]
        n = len(self.products)
        self.table.clear()
        self.table.setColumnCount(n + 1)
        self.table.setRowCount(len(rows))
        self.table.setHorizontalHeaderLabels(["Eigenschaft"] + [p["nummer_fmt"] for p in self.products])
        diff_bg = QColor(_c("TAG_COLORS")["GEAENDERT"])
        section_bg = QColor(_c("MINT"))
        bold = self.table.font()
        bold.setBold(True)
        n_diff = 0
        for r, (section, label, values) in enumerate(rows):
            if section:
                item = QTableWidgetItem(section)
                item.setFont(bold)
                item.setForeground(QColor(_c("GREEN")))
                for c in range(n + 1):
                    cell = item if c == 0 else QTableWidgetItem("")
                    cell.setBackground(section_bg)
                    self.table.setItem(r, c, cell)
                self.table.setSpan(r, 0, 1, n + 1)
                continue
            differs = len(set(values)) > 1
            n_diff += differs
            head = QTableWidgetItem(label)
            head.setFont(bold)
            head.setForeground(QColor(_c("MUTED")))
            self.table.setItem(r, 0, head)
            for c, v in enumerate(values, start=1):
                cell = QTableWidgetItem(v)
                if differs:
                    cell.setBackground(diff_bg)
                self.table.setItem(r, c, cell)
        self.table.setColumnWidth(0, 200)
        for c in range(1, n + 1):
            self.table.setColumnWidth(c, 280)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.resizeRowsToContents()
        self.legend.setText(f"{n_diff} Eigenschaft(en) unterscheiden sich – farbig hinterlegt.")

    def _add(self):
        more = self.on_add([p["nummer"] for p in self.products]) if self.on_add else None
        if more:
            self.set_products(self.products + more)

    def _copy(self):
        lines = ["\t".join(["Eigenschaft"] + [p["nummer_fmt"] for p in self.products])]
        for section, label, values in self._rows():
            lines.append(section if section else "\t".join([label] + [" ".join(v.split()) for v in values]))
        QApplication.clipboard().setText("\n".join(lines))
        self.legend.setText("Vergleich als Tabelle kopiert – in Excel oder eine E-Mail einfügen.")


class ProductPicker(QDialog):
    """Popup: Produkt(e) zum Vergleichen suchen und auswählen."""

    def __init__(self, parent, base_label, search_fn, initial_fn, max_sel=3):
        super().__init__(parent)
        self.setWindowTitle("Produkt zum Vergleichen wählen")
        self.setMinimumSize(720, 520)
        self.search_fn, self.initial_fn, self.max_sel = search_fn, initial_fn, max_sel
        self.result = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.addWidget(QLabel(f"Vergleichen mit <b>{html.escape(base_label)}</b>", objectName="cardTitle"))
        self.edit = QLineEdit(clearButtonEnabled=True,
                              placeholderText="Bezeichnung, Hersteller oder Nummer suchen … (leer = gleiche Produktart)")
        self.edit.addAction(make_icon("search", _c("MUTED")), QLineEdit.ActionPosition.LeadingPosition)
        lay.addWidget(self.edit)
        self.info = QLabel(objectName="muted")
        lay.addWidget(self.info)
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.setIconSize(QSize(16, 16))
        self.list.itemSelectionChanged.connect(self._update)
        self.list.itemDoubleClicked.connect(lambda *_: self._accept())
        lay.addWidget(self.list, 1)
        self.ok = QPushButton("Vergleichen", objectName="primary", clicked=self._accept)
        self.ok.setIcon(make_icon("compare", "#FFFFFF", 16))
        row = QHBoxLayout()
        row.addWidget(QLabel(f"Bis zu {max_sel} Produkte markieren (Strg/Umschalt + Klick)", objectName="muted"))
        row.addStretch(1)
        row.addWidget(QPushButton("Abbrechen", clicked=self.reject))
        row.addWidget(self.ok)
        lay.addLayout(row)
        self.timer = QTimer(self, singleShot=True, interval=200, timeout=self._fill)
        self.edit.textChanged.connect(lambda: self.timer.start())
        self._fill()

    def _fill(self):
        text = self.edit.text().strip()
        items = self.search_fn(text) if text else self.initial_fn()
        self.info.setText(f"{len(items)} Treffer" if text else f"Produkte derselben Produktart ({len(items)})")
        self.list.clear()
        for nummer, label in items:
            it = QListWidgetItem(make_icon("box", _c("MUTED")), label)
            it.setData(Qt.ItemDataRole.UserRole, nummer)
            self.list.addItem(it)
        self._update()

    def _update(self):
        n = len(self.list.selectedItems())
        self.ok.setEnabled(0 < n <= self.max_sel)
        self.ok.setText(f"Vergleichen ({n})" if n else "Vergleichen")

    def _accept(self):
        sel = [it.data(Qt.ItemDataRole.UserRole) for it in self.list.selectedItems()][:self.max_sel]
        if sel:
            self.result = sel
            self.accept()


# ---------------------------------------------------------------------------------------------- Nummernliste
def parse_numbers(text):
    """Alle Hilfsmittelnummern (10-stellig, mit oder ohne Punkte) in Reihenfolge, ohne Dubletten."""
    seen, out = set(), []
    for m in NUMMER_RE.finditer(text or ""):
        k = "".join(m.groups())
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


class PasteNumbersDialog(QDialog):
    """Viele Nummern auf einmal einfügen (aus Excel, E-Mail …) und prüfen."""

    def __init__(self, parent, lookup):
        super().__init__(parent)
        self.setWindowTitle("Nummernliste einfügen")
        self.setMinimumSize(620, 520)
        self.lookup = lookup        # nummern -> (aktiv, entfernt, unbekannt)
        self.result = None          # ("show"|"add", gefundene Nummern)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.addWidget(QLabel("Hilfsmittelnummern einfügen (beliebiger Text, z. B. aus Excel oder einer E-Mail):",
                             objectName="cardTitle", wordWrap=True))
        self.edit = QPlainTextEdit(placeholderText="01.24.01.0001\n0124010003\n…")
        clip = QApplication.clipboard().text()
        if parse_numbers(clip):
            self.edit.setPlainText(clip)
        self.edit.textChanged.connect(self._check)
        lay.addWidget(self.edit, 1)
        self.info = QLabel(wordWrap=True)
        self.info.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(self.info)
        self.btn_show = QPushButton("Gefundene anzeigen", objectName="primary", clicked=lambda: self._done("show"))
        self.btn_add = QPushButton("Zu Liste hinzufügen …", clicked=lambda: self._done("add"))
        row = QHBoxLayout()
        row.addWidget(QPushButton("Abbrechen", clicked=self.reject))
        row.addStretch(1)
        row.addWidget(self.btn_add)
        row.addWidget(self.btn_show)
        lay.addLayout(row)
        self._check()

    def _check(self):
        nums = parse_numbers(self.edit.toPlainText())
        active, removed, unknown = self.lookup(nums)
        self.found = active + removed
        text = f"<b>{len(nums)}</b> Nummern erkannt: <b>{len(active)}</b> aktiv"
        if removed:
            text += f", <span style='color:{_c('DANGER')}'><b>{len(removed)}</b> entfernt</span>"
        if unknown:
            shown = ", ".join(f"{u[:2]}.{u[2:4]}.{u[4:6]}.{u[6:]}" for u in unknown[:12])
            text += (f", <span style='color:{_c('DANGER')}'><b>{len(unknown)}</b> unbekannt</span>"
                     f"<br><span style='color:{_c('MUTED')}'>Unbekannt: {shown}{' …' if len(unknown) > 12 else ''}</span>")
        self.info.setText(text)
        for b in (self.btn_show, self.btn_add):
            b.setEnabled(bool(self.found))

    def _done(self, mode):
        self.result = (mode, self.found)
        self.accept()


# ---------------------------------------------------------------------------------------------- Startseite
class BarChart(QWidget):
    """Gestapelte Balken: Neu / Geändert / Wieder aufgenommen / Entfernt je Version."""

    def __init__(self):
        super().__init__()
        self.data = []   # (Beschriftung, {Typ: Anzahl})
        self.setMinimumHeight(220)

    def set_data(self, data):
        self.data = data
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        types = ("NEU", "GEAENDERT", "REAKTIVIERT", "UMGRUPPIERT", "ENTFERNT")
        colors = {t: QColor(_c("TAG_COLORS")[t]).darker(115) for t in types}
        p.setPen(QColor(_c("MUTED")))
        if not self.data:
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Noch keine Änderungen – ab dem zweiten Import sichtbar.")
            return
        fm = p.fontMetrics()   # Abstände nach Schriftgröße, sonst wird bei großer Schrift abgeschnitten
        lh = fm.height()
        top, bottom, left = 10, 2 * lh + 8, max(44, fm.horizontalAdvance('00000') + 8)
        mx = max(1, max(sum(d.values()) for _, d in self.data))
        n = len(self.data)
        slot = (w - left - 10) / n
        bw = min(46, slot * 0.6)
        p.drawLine(left, h - bottom, w - 10, h - bottom)
        p.drawText(QRectF(0, top - 6, left - 6, lh), Qt.AlignmentFlag.AlignRight, f"{mx}")
        for i, (label, counts) in enumerate(self.data):
            x = left + i * slot + (slot - bw) / 2
            y = h - bottom
            for t in types:
                v = counts.get(t, 0)
                if not v:
                    continue
                bh = (h - bottom - top) * v / mx
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(colors[t])
                p.drawRoundedRect(QRectF(x, y - bh, bw, bh), 3, 3)
                y -= bh
            p.setPen(QColor(_c("MUTED")))
            p.drawText(QRectF(x - 20, h - bottom + 4, bw + 40, lh), Qt.AlignmentFlag.AlignCenter, label)
        lx = left
        for t, name in zip(types, ("Neu", "Geändert", "Wieder aufgen.", "Umgruppiert", "Entfernt")):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(colors[t])
            p.drawRoundedRect(QRectF(lx, h - lh / 2 - 7, 10, 10), 2, 2)
            p.setPen(QColor(_c("MUTED")))
            p.drawText(QRectF(lx + 14, h - lh - 2, fm.horizontalAdvance(name) + 4, lh), Qt.AlignmentFlag.AlignLeft, name)
            lx += fm.horizontalAdvance(name) + 34
        p.end()


def stat_tile(title, icon_name):
    frame = QFrame(objectName="card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(18, 14, 18, 14)
    head = QHBoxLayout()
    ic = QLabel()
    ic.setPixmap(make_icon(icon_name, _c("GREEN"), 22).pixmap(22, 22))
    head.addWidget(ic)
    head.addWidget(QLabel(title, objectName="muted"), 1)
    lay.addLayout(head)
    value = QLabel("–", objectName="tileValue")
    lay.addWidget(value)
    sub = QLabel("", objectName="muted", wordWrap=True)
    lay.addWidget(sub)
    frame.value, frame.sub = value, sub
    return frame


class ClickList(QListWidget):
    """Liste auf der Startseite: Klick führt eine hinterlegte Aktion aus."""

    def __init__(self):
        super().__init__(objectName="clickList")
        self.setIconSize(QSize(16, 16))
        self.itemClicked.connect(lambda it: (it.data(Qt.ItemDataRole.UserRole) or (lambda: None))())

    def set_items(self, items, empty_text):
        self.clear()
        for icon, text, fn in items:
            it = QListWidgetItem(icon, text)
            it.setData(Qt.ItemDataRole.UserRole, fn)
            self.addItem(it)
        if not items:
            it = QListWidgetItem(empty_text)
            it.setFlags(Qt.ItemFlag.NoItemFlags)
            self.addItem(it)


# ---------------------------------------------------------------------------------------------- Karten
class CardView(QListWidget):
    """Kartenansicht der Produkte (gleiche Daten und Auswahl wie die Tabelle)."""
    nummerSelected = Signal(str)

    def __init__(self):
        super().__init__(objectName="cards")
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.setSpacing(8)
        self.setUniformItemSizes(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.itemSelectionChanged.connect(self._emit)

    def _emit(self):
        items = self.selectedItems()
        if items:
            self.nummerSelected.emit(items[0].data(Qt.ItemDataRole.UserRole))

    def clear_cards(self):
        self.clear()

    def add_card(self, nummer, title, subtitle, chips, comment, star, cat_color):
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, nummer)
        item.setSizeHint(QSize(300, 150))
        self.addItem(item)
        card = QFrame(objectName="productCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(4)
        top = QHBoxLayout()
        t = QLabel(f"<b>{html.escape(title)}</b>", wordWrap=True)
        t.setMaximumHeight(40)
        top.addWidget(t, 1)
        if cat_color:
            dot = QLabel()
            dot.setPixmap(make_icon("tag", cat_color, 16).pixmap(16, 16))
            top.addWidget(dot)
        if star:
            s = QLabel()
            s.setPixmap(make_icon("star" if star == "★" else "star_outline", _c("GOLD"), 16).pixmap(16, 16))
            top.addWidget(s)
        lay.addLayout(top)
        lay.addWidget(QLabel(subtitle, objectName="muted", textFormat=Qt.TextFormat.PlainText))
        chip_row = QHBoxLayout()
        chip_row.setSpacing(4)
        for text, color in chips:
            ch = QLabel(text, objectName="chip", textFormat=Qt.TextFormat.PlainText)
            ch.setStyleSheet(f"background: {color}; color: {_c('TEXT')};")
            chip_row.addWidget(ch)
        chip_row.addStretch(1)
        lay.addLayout(chip_row)
        if comment:
            c = QLabel(comment, objectName="muted", textFormat=Qt.TextFormat.PlainText)
            c.setMaximumHeight(34)
            c.setWordWrap(True)
            lay.addWidget(c)
        lay.addStretch(1)
        self.setItemWidget(item, card)

    def select_nummer(self, nummer):
        for i in range(self.count()):
            if self.item(i).data(Qt.ItemDataRole.UserRole) == nummer:
                self.setCurrentRow(i)
                return


# ---------------------------------------------------------------------------------------------- Kommentare
class CommentsWidget(QWidget):
    """Kommentarverlauf je Produkt (für alle sichtbar) mit Eingabe; eigene Kommentare lassen sich löschen."""
    send = Signal(str)
    delete = Signal(int)

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.view = QTextBrowser(openLinks=False, objectName="comments")
        self.view.setMinimumHeight(70)
        self.view.anchorClicked.connect(lambda url: self.delete.emit(int(url.toString().split(":")[1])))
        self.input = QPlainTextEdit(placeholderText="Kommentar für alle schreiben … (Strg+Enter senden)")
        self.input.setMaximumHeight(60)
        self.input.installEventFilter(self)
        self.btn = QPushButton("Senden", objectName="primary", clicked=self._send)
        self.btn.setIcon(make_icon("comment", "#FFFFFF", 16))
        row = QHBoxLayout()
        row.addWidget(self.input, 1)
        row.addWidget(self.btn, 0, Qt.AlignmentFlag.AlignBottom)
        lay.addWidget(self.view, 1)
        lay.addLayout(row)

    def eventFilter(self, obj, event):
        if (event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self._send()
            return True
        return super().eventFilter(obj, event)

    def _send(self):
        text = self.input.toPlainText().strip()
        if text:
            self.send.emit(text)

    def set_comments(self, rows, me, fmt_when):
        if not rows:
            self.view.setHtml(f"<p style='color:{_c('MUTED')}'>Noch keine Kommentare.</p>")
            return
        parts = []
        for r in rows:
            mine = (r["user"] or "") == (me or "")
            bg = _c("MINT") if mine else _c("ALT")
            delete = (f" &nbsp;<a href='del:{r['id']}' style='color:{_c('MUTED')}'>löschen</a>" if mine else "")
            parts.append(f"<table width='100%' cellpadding='6' style='background:{bg}; margin-bottom:4px'><tr><td>"
                         f"<b>{html.escape(r['user'] or '?')}</b> <span style='color:{_c('MUTED')}'>"
                         f"{fmt_when(r['at'])}</span>{delete}<br>{html.escape(r['text']).replace(chr(10), '<br>')}"
                         "</td></tr></table>")
        self.view.setHtml("".join(parts))
        sb = self.view.verticalScrollBar()
        sb.setValue(sb.maximum())


# ---------------------------------------------------------------------------------------------- kleine Dialoge
class TextDialog(QDialog):
    """Dialog mit HTML-Inhalt (Verlauf, Info, Neuigkeiten) und optionalen Buttons."""

    def __init__(self, parent, title, html_text, buttons=(), on_link=None, size=(720, 520)):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(*size)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        self.view = QTextBrowser(openLinks=False)
        self.view.setHtml(html_text)
        if on_link:
            self.view.anchorClicked.connect(lambda url: (self.accept(), on_link(url.toString())))
        lay.addWidget(self.view, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        for text, fn, primary in buttons:
            b = QPushButton(text, objectName="primary" if primary else "")
            b.clicked.connect(lambda _=False, fn=fn: fn(self))
            row.addWidget(b)
        row.addWidget(QPushButton("Schließen", clicked=self.accept))
        lay.addLayout(row)


def grid_html(rows):
    return "<table cellpadding='4'>" + "".join(
        f"<tr><td style='color:{_c('MUTED')}; padding-right:16px'>{html.escape(k)}</td><td>{v}</td></tr>"
        for k, v in rows) + "</table>"
