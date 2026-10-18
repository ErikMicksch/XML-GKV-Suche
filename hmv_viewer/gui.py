"""Qt-Oberfläche (PySide6): Produkte einsehen, Favoriten & Notizen, Versionshistorie, Import und Excel-Export.

Farbwelt angelehnt an die AOK (dunkles Grün, Mint), ohne Logo.
"""
from __future__ import annotations

import datetime as dt
import difflib
import json
import os
import getpass
import html
import sqlite3
import sys
import threading
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QSettings, QSize, QStandardPaths, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QIcon, QKeySequence, QPainter, QPalette, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox, QCompleter, QDialog, QFileDialog, QFrame,
    QColorDialog, QHBoxLayout, QInputDialog, QListWidget, QListWidgetItem, QHeaderView, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QProgressDialog,
    QPushButton, QRadioButton, QScrollArea, QSizePolicy, QSplitter, QStackedWidget, QTableWidget, QTableWidgetItem, QTabWidget,
    QTextBrowser, QToolButton, QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator, QVBoxLayout, QWidget,
)

from . import __version__, db, exporter, importer, queries
from .favorites import FILE_NAME, FavoriteStore, legacy_db_keys
from .model import CHANGE_LABELS, ENTFERNT, FIELD_LABELS, GEAENDERT, NEU, REAKTIVIERT, format_nummer
from .parser import SourceError
from .queries import ProductFilter
from .ui_extras import (BarChart, CardView, ClickList, CollapsibleSection, CommandPalette, CommentsWidget,
                        CompareDialog, PasteNumbersDialog, ProductPicker, TextDialog, Toast, fade_in, grid_html, make_icon, stat_tile)

PAGE_SIZE = 500
STATUS_CHOICES = {"Nur aktive": "aktiv", "Nur entfernte": "entfernt", "Alle": "alle"}
TYPE_CHOICES = {"Alle Änderungstypen": None, **{CHANGE_LABELS[t]: t for t in (NEU, GEAENDERT, ENTFERNT, REAKTIVIERT)}}
ALL_VERSIONS = "Alle Versionen"
ALL_HERSTELLER = "Alle Hersteller"

PRODUCT_COLUMNS = (
    # id, Überschrift, Breite, Sortier-Schlüssel (None = nicht sortierbar)
    ("fav", "★", 36, "fav"),
    ("kat", "", 30, "kat"),
    ("nummer", "Hilfsmittelnummer", 125, "nummer"),
    ("bezeichnung", "Bezeichnung", 300, "bezeichnung"),
    ("hersteller", "Hersteller", 190, "hersteller"),
    ("notiz", "Meine Notiz", 170, None),
    ("gnotiz", "Kommentare", 190, None),
    ("art", "Produktart", 250, "art"),
    ("aufnahme", "Aufnahme", 90, "aufnahme"),
    ("aenderung", "Änderung (HMV)", 115, "aenderung"),
    ("version", "Version / Status", 150, "version"),
)
COL = {c[0]: i for i, c in enumerate(PRODUCT_COLUMNS)}

# Farbwelten. Die Namen (GREEN = Akzentfarbe usw.) sind Modul-Variablen, die apply_theme() umstellt;
# f-Strings und build_qss() lesen sie erst beim Aufruf, daher genügt nach dem Umschalten ein Neuaufbau der Inhalte.
THEMES = {
    "Classic": dict(  # angelehnt an die AOK: dunkelgrüner Kopf, Mint-Flächen
        GREEN="#005E3F", GREEN_DARK="#00472F", MINT="#E3F2EA", MINT_HOVER="#D0EADC", SELECT="#C7E5D5",
        BG="#F2F5F3", SURFACE="#FFFFFF", LINE="#DCE5E0", TEXT="#1B2A23", MUTED="#5E6E66", GOLD="#C98A00",
        ALT="#F7FAF8", HOVER="#EEF6F1", DISABLED_BG="#EEF2F0", DISABLED_FG="#A3B4AB", SCROLL="#C5D3CB",
        SCROLL_HOVER="#9FB5A9", HEADER="#005E3F", HEADER_FG="#FFFFFF", HEADER_SUB="#B9DFCB",
        HEADER_BTN="rgba(255,255,255,0.12)", HEADER_BTN_HOVER="rgba(255,255,255,0.24)",
        HEADER_BTN_BORDER="rgba(255,255,255,0.28)", HEADER_PRIMARY_BG="#FFFFFF", HEADER_PRIMARY_FG="#005E3F",
        DIFF_ADD="#E6FFED", DIFF_DEL="#FFEEF0", DANGER="#B3261E",
        TAG_COLORS={NEU: "#d9f2d0", GEAENDERT: "#fff2b3", ENTFERNT: "#f6c9c0", REAKTIVIERT: "#cfe3f7"}),
    "Hell": dict(  # neutral und hell, grüner Akzent, weißer Kopf
        GREEN="#0B7A55", GREEN_DARK="#08603F", MINT="#EEF1F4", MINT_HOVER="#E1E6EB", SELECT="#DCEFE6",
        BG="#F7F8FA", SURFACE="#FFFFFF", LINE="#E3E6EA", TEXT="#1F2328", MUTED="#656D76", GOLD="#C98A00",
        ALT="#FAFBFC", HOVER="#F2F5F7", DISABLED_BG="#F3F4F6", DISABLED_FG="#A8AFB7", SCROLL="#CDD3DA",
        SCROLL_HOVER="#A9B1BA", HEADER="#FFFFFF", HEADER_FG="#1F2328", HEADER_SUB="#656D76",
        HEADER_BTN="#F3F4F6", HEADER_BTN_HOVER="#E7EAEE", HEADER_BTN_BORDER="#E3E6EA",
        HEADER_PRIMARY_BG="#0B7A55", HEADER_PRIMARY_FG="#FFFFFF",
        DIFF_ADD="#E6FFED", DIFF_DEL="#FFEEF0", DANGER="#B3261E",
        TAG_COLORS={NEU: "#dcf5e3", GEAENDERT: "#fff4c2", ENTFERNT: "#fbd9d3", REAKTIVIERT: "#dbeafb"}),
    "Dunkel": dict(  # dunkle Flächen, helle Schrift, grüner Akzent
        GREEN="#4FC08D", GREEN_DARK="#3BA677", MINT="#24332C", MINT_HOVER="#2E4238", SELECT="#2F5544",
        BG="#15191C", SURFACE="#1E2428", LINE="#2E363B", TEXT="#E6EAE8", MUTED="#98A39D", GOLD="#E8B931",
        ALT="#222A2E", HOVER="#283137", DISABLED_BG="#232A2E", DISABLED_FG="#5E6A64", SCROLL="#3A454B",
        SCROLL_HOVER="#52606A", HEADER="#0F2A20", HEADER_FG="#E6EAE8", HEADER_SUB="#8FBFA8",
        HEADER_BTN="rgba(255,255,255,0.08)", HEADER_BTN_HOVER="rgba(255,255,255,0.16)",
        HEADER_BTN_BORDER="rgba(255,255,255,0.18)", HEADER_PRIMARY_BG="#4FC08D", HEADER_PRIMARY_FG="#0F2A20",
        DIFF_ADD="#1F3A2A", DIFF_DEL="#432427", DANGER="#FF8A80",
        TAG_COLORS={NEU: "#1F4730", GEAENDERT: "#4D4216", ENTFERNT: "#552A27", REAKTIVIERT: "#1F3B57"}),
}
THEME_NAMES = tuple(THEMES)
DENSITY = {"Kompakt": 24, "Normal": 30, "Groß": 38}   # Zeilenhöhe der Tabellen
FONT_SIZES = (9, 10, 11, 12)
ROW_H = 30
FONT_PT = 10


def apply_view(density, font_pt):
    """Zeilenhöhe und Schriftgröße (je Benutzer gespeichert) – wirkt mit dem nächsten apply_theme."""
    global ROW_H, FONT_PT
    ROW_H = DENSITY.get(density, 30)
    FONT_PT = int(font_pt) if str(font_pt).isdigit() and int(font_pt) in FONT_SIZES else 10
TAG_COLORS = {}


def apply_theme_colors(name):
    """Setzt die Farb-Variablen dieses Moduls auf die gewählte Farbwelt."""
    theme = THEMES.get(name, THEMES["Classic"])
    for key, value in theme.items():
        if key == "TAG_COLORS":
            TAG_COLORS.clear()
            TAG_COLORS.update(value)
        else:
            globals()[key] = value


apply_theme_colors("Classic")
STAR = "★"
UD = Qt.ItemDataRole.UserRole
ENTRY_ROLE = int(Qt.ItemDataRole.UserRole) + 1   # (Liste, Präfix) bei Gruppen-Einträgen

SHORTCUTS = (
    ("Strg+F", "Produktsuche (findet auch Text in Ihren Notizen)"),
    ("Strg+G", "Produktgruppen filtern"),
    ("Strg+H", "Hersteller filtern"),
    ("↓ in der Suche", "in die Trefferliste springen"),
    ("Esc in der Suche", "Suche leeren"),
    ("Strg+D", "Favorit an/aus (auch für mehrere markierte Zeilen)"),
    ("Strg+B", "Favoriten anzeigen"),
    ("Strg+N", "Notiz zum Produkt bearbeiten"),
    ("Strg+A, Strg+C", "Zeilen markieren und als Tabelle kopieren (für Excel/E-Mail)"),
    ("Strg+I / Strg+E", "Import / Excel-Export"),
    ("Strg+K", "Schnellzugriff: Produkte, Gruppen, Listen und Funktionen"),
    ("Strg+Z", "letzte Änderung an Favoriten/Listen/Kategorien rückgängig"),
    ("Strg+Umschalt+V", "Nummernliste einfügen"),
    ("Strg+0 / 1 / 2 / 3", "Startseite / Produkte / Versionen / Änderungen anderer"),
    ("F5", "neu laden"),
)


def build_qss():
    return f"""
* {{ font-family: "Segoe UI", "Helvetica Neue", Arial; font-size: {FONT_PT}pt; color: {TEXT}; }}
QMainWindow, #page {{ background: {BG}; }}
QDialog, QMessageBox, QInputDialog {{ background: {SURFACE}; }}
#header {{ background: {HEADER}; border-bottom: 1px solid {LINE}; }}
#header QLabel#title {{ color: {HEADER_FG}; font-size: 17pt; font-weight: 700; }}
#header QLabel#subtitle {{ color: {HEADER_SUB}; }}
#search {{ background: {SURFACE}; border: 1px solid {LINE}; border-radius: 19px; padding: 8px 16px; font-size: 11pt; }}
#search:focus {{ border: 2px solid {GREEN}; }}
#header QPushButton {{ background: {HEADER_BTN}; color: {HEADER_FG}; border: 1px solid {HEADER_BTN_BORDER};
    border-radius: 18px; padding: 7px 16px; font-weight: 600; }}
#header QPushButton:hover {{ background: {HEADER_BTN_HOVER}; }}
#header QPushButton::menu-indicator {{ width: 0; }}
#header QPushButton#primary {{ background: {HEADER_PRIMARY_BG}; color: {HEADER_PRIMARY_FG}; border: none; }}
#nav {{ background: {SURFACE}; border-right: 1px solid {LINE}; }}
#nav QToolButton {{ border: none; border-radius: 12px; padding: 10px 8px; color: {MUTED}; font-weight: 600; }}
#nav QToolButton:hover {{ background: {HOVER}; }}
#nav QToolButton:checked {{ background: {MINT}; color: {GREEN}; }}
#card {{ background: {SURFACE}; border: 1px solid {LINE}; border-radius: 14px; }}
QLabel#cardTitle {{ font-size: 12pt; font-weight: 700; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#chip {{ border-radius: 9px; padding: 2px 9px; font-size: 9pt; }}
QLabel#empty {{ color: {MUTED}; font-size: 11pt; }}
QLineEdit, QPlainTextEdit {{ background: {SURFACE}; border: 1px solid {LINE}; border-radius: 10px; padding: 6px 10px;
    selection-background-color: {SELECT}; selection-color: {TEXT}; }}
QLineEdit:focus, QPlainTextEdit:focus {{ border: 2px solid {GREEN}; }}
QPlainTextEdit:disabled {{ background: {BG}; }}
QComboBox {{ background: {SURFACE}; border: 1px solid {LINE}; border-radius: 10px; padding: 5px 10px; }}
QComboBox:hover, QComboBox:focus {{ border-color: {GREEN}; }}
QComboBox QLineEdit {{ border: none; padding: 0; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView, QListView#completer {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {LINE};
    outline: 0; selection-background-color: {MINT}; selection-color: {GREEN}; padding: 4px; }}
QComboBox QAbstractItemView::item {{ min-height: 26px; padding: 2px 8px; }}
QComboBox QAbstractItemView::item:hover, QComboBox QAbstractItemView::item:selected {{ background: {MINT}; color: {GREEN}; }}
QPushButton {{ background: {MINT}; color: {GREEN}; border: none; border-radius: 10px; padding: 7px 14px; font-weight: 600; }}
QPushButton:hover {{ background: {MINT_HOVER}; }}
QPushButton:disabled {{ background: {DISABLED_BG}; color: {DISABLED_FG}; }}
QPushButton#primary {{ background: {GREEN}; color: {SURFACE}; }}
QPushButton#primary:hover {{ background: {GREEN_DARK}; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 15px; height: 15px; border: 1px solid {SCROLL_HOVER}; background: {SURFACE}; }}
QCheckBox::indicator {{ border-radius: 4px; }}
QRadioButton::indicator {{ border-radius: 8px; }}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{ background: {GREEN}; border: 3px solid {MINT_HOVER}; }}
QTableWidget, QTreeWidget, QListWidget {{ border: none; background: {SURFACE}; alternate-background-color: {ALT};
    selection-background-color: {SELECT}; selection-color: {TEXT}; outline: 0; }}
QTableWidget::item, QTreeWidget::item, QListWidget::item {{ padding: 4px 6px; }}
QTreeWidget::item:hover, QTableWidget::item:hover, QListWidget::item:hover {{ background: {HOVER}; }}
QTreeWidget::item:selected, QTableWidget::item:selected, QListWidget::item:selected {{ background: {SELECT}; color: {TEXT}; }}
QHeaderView::section {{ background: {SURFACE}; border: none; border-bottom: 2px solid {LINE}; padding: 8px 6px;
    font-weight: 700; color: {MUTED}; }}
QHeaderView::section:hover {{ color: {GREEN}; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; border: none; padding: 8px 16px; color: {MUTED}; font-weight: 600; }}
QTabBar::tab:selected {{ color: {GREEN}; border-bottom: 3px solid {GREEN}; }}
QTextBrowser {{ border: none; background: {SURFACE}; }}
QStatusBar {{ background: {SURFACE}; color: {MUTED}; border-top: 1px solid {LINE}; }}
QStatusBar QLabel {{ color: {MUTED}; padding: 0 8px; }}
QSplitter::handle {{ background: transparent; }}
QScrollBar:vertical {{ width: 10px; background: transparent; margin: 2px; }}
QScrollBar:horizontal {{ height: 10px; background: transparent; margin: 2px; }}
QScrollBar::handle {{ background: {SCROLL}; border-radius: 4px; min-height: 30px; min-width: 30px; }}
QScrollBar::handle:hover {{ background: {SCROLL_HOVER}; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ width: 0; height: 0; background: none; }}
QMenu {{ background: {SURFACE}; border: 1px solid {LINE}; border-radius: 8px; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; color: {TEXT}; }}
QMenu::item:selected {{ background: {MINT}; color: {GREEN}; }}
QMenu::separator {{ height: 1px; background: {LINE}; margin: 4px 8px; }}
QToolTip {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {LINE}; padding: 6px; }}
QProgressBar {{ border: none; background: {MINT}; border-radius: 6px; height: 12px; text-align: center; }}
QProgressBar::chunk {{ background: {GREEN}; border-radius: 6px; }}
#toast {{ background: {TEXT}; border-radius: 12px; }}
#toast QLabel#toastText {{ color: {SURFACE}; }}
#toast QPushButton#toastButton {{ background: transparent; color: {GOLD}; font-weight: 700; padding: 4px 10px; }}
QLabel#tileValue {{ font-size: {FONT_PT + 12}pt; font-weight: 700; color: {GREEN}; }}
QLabel#greeting {{ font-size: {FONT_PT + 8}pt; font-weight: 700; }}
QLabel#detailTitle {{ font-size: {FONT_PT + 4}pt; font-weight: 700; }}
QToolButton#sectionHeader {{ border: none; font-weight: 700; color: {GREEN}; text-align: left; padding: 4px 0; }}
QLabel#sectionBody {{ padding-left: 18px; }}
#productCard {{ background: {SURFACE}; border: 1px solid {LINE}; border-radius: 12px; }}
QListWidget#cards {{ background: {BG}; border: none; }}
QListWidget#cards::item {{ background: transparent; border: none; }}
QListWidget#cards::item:selected {{ background: {SELECT}; border-radius: 12px; }}
QListWidget#palette::item, QListWidget#clickList::item {{ padding: 7px 8px; border-radius: 8px; }}
QListWidget#clickList {{ background: {SURFACE}; }}
QToolButton#viewToggle {{ border: 1px solid {LINE}; border-radius: 8px; padding: 4px 8px; background: {SURFACE}; }}
QToolButton#viewToggle:checked {{ background: {MINT}; border-color: {GREEN}; }}
QTextBrowser#comments {{ border: 1px solid {LINE}; border-radius: 10px; }}
"""


def build_palette():
    """Feste Palette der Farbwelt – sonst übernimmt Qt z. B. den Windows-Dunkelmodus für Listen und Menüs."""
    pal = QPalette()
    for role, color in ((QPalette.ColorRole.Window, BG), (QPalette.ColorRole.WindowText, TEXT),
                        (QPalette.ColorRole.Base, SURFACE), (QPalette.ColorRole.AlternateBase, ALT),
                        (QPalette.ColorRole.Text, TEXT), (QPalette.ColorRole.Button, MINT),
                        (QPalette.ColorRole.ButtonText, GREEN), (QPalette.ColorRole.Highlight, SELECT),
                        (QPalette.ColorRole.HighlightedText, TEXT), (QPalette.ColorRole.ToolTipBase, SURFACE),
                        (QPalette.ColorRole.ToolTipText, TEXT), (QPalette.ColorRole.PlaceholderText, MUTED),
                        (QPalette.ColorRole.Link, GREEN), (QPalette.ColorRole.Light, SURFACE),
                        (QPalette.ColorRole.Midlight, LINE), (QPalette.ColorRole.Mid, SCROLL),
                        (QPalette.ColorRole.Dark, SCROLL_HOVER), (QPalette.ColorRole.Shadow, BG)):
        pal.setColor(role, QColor(color))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(DISABLED_FG))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(DISABLED_FG))
    return pal


def apply_theme(name):
    """Farbwelt für die ganze Anwendung setzen (Palette + Stylesheet)."""
    apply_theme_colors(name)
    app = QApplication.instance()
    if hasattr(app.styleHints(), "setColorScheme"):   # Qt >= 6.8: Windows-Hell/Dunkel nicht übernehmen
        app.styleHints().setColorScheme(Qt.ColorScheme.Dark if name == "Dunkel" else Qt.ColorScheme.Light)
    app.setPalette(build_palette())
    app.setStyleSheet(build_qss())


def color_icon(color, size=14):
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(QColor(0, 0, 0, 60))
    painter.drawRoundedRect(1, 1, size - 2, size - 2, 4, 4)
    painter.end()
    return QIcon(pix)


def fmt_date(iso):
    if not iso:
        return ""
    try:
        return dt.date.fromisoformat(iso[:10]).strftime("%d.%m.%Y")
    except ValueError:
        return iso


def _dots(n):
    return f"{n:,}".replace(",", ".")


def _key_tuple(key):
    return tuple(sorted(key.items()))


def prune(nodes, term):
    """Behält passende Knoten (mit allen Kindern) und die Pfade dorthin (aufgeklappt)."""
    out = []
    for n in nodes:
        if term in n["label"].casefold():
            out.append(n)
        else:
            kids = prune(n["children"], term)
            if kids:
                out.append(dict(n, children=kids, open=True))
    return out


def diff_parts(old, new):
    """[(Text, Tag)] mit Tag add/del/hunk/muted – kurze Werte als alt/neu, lange als Zeilen-Diff."""
    old_s = "" if old is None else str(old)
    new_s = "" if new is None else str(new)
    if "\n" not in old_s and "\n" not in new_s and len(old_s) <= 160 and len(new_s) <= 160:
        return [(f"alt:  {old_s or '(leer)'}", "del"), (f"neu:  {new_s or '(leer)'}", "add")]
    parts = []
    for line in list(difflib.unified_diff(old_s.splitlines(), new_s.splitlines(), lineterm="", n=2))[2:]:
        tag = "add" if line.startswith("+") else "del" if line.startswith("-") else "hunk" if line.startswith("@@") else None
        parts.append((line, tag))
    return parts or [("(nur Leerraum geändert)", "muted")]


def _card(title=None):
    frame = QFrame(objectName="card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(14, 12, 14, 12)
    lay.setSpacing(8)
    if title:
        lay.addWidget(QLabel(title, objectName="cardTitle"))
    return frame, lay


def _row(*widgets, stretch_at=None):
    lay = QHBoxLayout()
    lay.setSpacing(8)
    for i, w in enumerate(widgets):
        if i == stretch_at:
            lay.addStretch(1)
        lay.addWidget(w)
    if stretch_at is not None and stretch_at >= len(widgets):
        lay.addStretch(1)
    return lay


def _table(columns):
    t = QTableWidget(0, len(columns))
    t.setHorizontalHeaderLabels([c[1] for c in columns])
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(ROW_H)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setAlternatingRowColors(True)
    t.setShowGrid(False)
    t.setWordWrap(False)
    for i, c in enumerate(columns):
        t.setColumnWidth(i, c[2])
    t.horizontalHeader().setStretchLastSection(True)
    t.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    return t


def _fill_row(table, r, values, color=None):
    for c, v in enumerate(values):
        item = QTableWidgetItem(str(v))
        if color:
            item.setBackground(QBrush(QColor(color)))
        table.setItem(r, c, item)


def _clean(text):
    return " ".join(str(text or "").split())   # Tabs/Zeilenumbrüche würden die kopierte Tabelle zerreißen


def _who(row):
    """„Nachname, 18.10.2026 14:05“ aus changed_by/changed_at (bzw. created_* als Rückfall)."""
    if row is None:
        return ""
    keys = row.keys()
    by = (row["changed_by"] if "changed_by" in keys else None) or (row["created_by"] if "created_by" in keys else None)
    at = (row["changed_at"] if "changed_at" in keys else None) or (row["created_at"] if "created_at" in keys else None)
    when = ""
    if at:
        try:
            when = dt.datetime.fromisoformat(at).strftime("%d.%m.%Y %H:%M")
        except ValueError:
            when = at
    return f"{by or '?'}, {when}".strip(", ")


def _when(iso):
    if not iso:
        return ""
    try:
        return dt.datetime.fromisoformat(iso).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return iso


def cat_color(cat):
    return cat["farbe"] if cat else None


def _tip(text):
    return html.escape(text).replace("\n", "<br>")


class Worker(QObject):
    """Signale aus dem Hintergrund-Thread kommen automatisch im GUI-Thread an."""
    progress = Signal(str, int, int)
    done = Signal(object)
    failed = Signal(object)


class ExportDialog(QDialog):
    def __init__(self, parent, filtered_count, n_favs):
        super().__init__(parent)
        self.setWindowTitle("Excel-Export")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.addWidget(QLabel("Welche Produkte sollen exportiert werden?", objectName="cardTitle"))
        self.scope = QButtonGroup(self)
        for value, text in (("filter", f"Aktuelle Auswahl / Filter ({_dots(filtered_count)} Produkte)"),
                            ("favoriten", f"Meine Favoriten ({_dots(n_favs)} Produkte)"),
                            ("aktiv", "Alle aktiven Produkte"), ("alle", "Alle Produkte inkl. entfernter")):
            rb = QRadioButton(text)
            rb.setProperty("scope", value)
            rb.setChecked(value == "filter")
            self.scope.addButton(rb)
            lay.addWidget(rb)
        lay.addSpacing(10)
        lay.addWidget(QLabel("Inhalt", objectName="cardTitle"))
        self.personal = QCheckBox("Spalten „Favorit“, „Kategorie“ und „Meine Notiz“ anhängen", checked=True)
        self.hist = QCheckBox("Blatt Änderungshistorie (Feld, alter Wert, neuer Wert je Version)", checked=True)
        self.initial = QCheckBox("Erstimport (alle Produkte als „Neu“) in der Historie mit aufführen")
        self.versions = QCheckBox("Blatt Versionen (Übersicht aller Importe)", checked=True)
        for w in (self.personal, self.hist, self.initial, self.versions):
            lay.addWidget(w)
        lay.addSpacing(10)
        lay.addLayout(_row(QPushButton("Abbrechen", clicked=self.reject),
                           QPushButton("Exportieren …", objectName="primary", clicked=self.accept), stretch_at=0))

    def options(self):
        return {"scope": self.scope.checkedButton().property("scope"), "history": self.hist.isChecked(),
                "versions": self.versions.isChecked(), "initial": self.initial.isChecked(),
                "personal": self.personal.isChecked()}


class AddToListDialog(QDialog):
    """Ziel-Liste wählen (Meine Favoriten, private oder gemeinsame Listen, auch Unterlisten) und bei Gruppen den Modus."""

    def __init__(self, win, what, n, is_group):
        super().__init__(win)
        self.win, self.target, self.whole_group = win, None, True
        self.setWindowTitle("Zu Liste hinzufügen")
        self.setMinimumSize(520, 520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.addWidget(QLabel(f"„{what}“ hinzufügen zu …", objectName="cardTitle", wordWrap=True))
        self.tree = QTreeWidget(headerHidden=True)
        self.tree.currentItemChanged.connect(lambda *_: self._update_buttons())
        self.tree.itemDoubleClicked.connect(lambda *_: self.ok.isEnabled() and self._accept())
        lay.addWidget(self.tree, 1)
        self.rb_group = self.rb_single = None
        if is_group:
            lay.addWidget(QLabel("Wie soll die Produktgruppe übernommen werden?", objectName="cardTitle"))
            self.rb_group = QRadioButton("Ganze Produktgruppe – erscheint als aufklappbarer Baum; "
                                         "neue Produkte der Gruppe gehören automatisch dazu", checked=True)
            self.rb_single = QRadioButton(f"Alle {_dots(n)} aktiven Produkte einzeln – fester Stand von heute, "
                                          "einzelne Produkte lassen sich später wieder entfernen")
            for rb in (self.rb_group, self.rb_single):
                rb.setStyleSheet("QRadioButton { padding: 2px 0; }")
                lay.addWidget(rb)
        self.new_btn = QPushButton("Neue Liste hier …", clicked=self._new_here)
        self.ok = QPushButton("Hinzufügen", objectName="primary", clicked=self._accept)
        lay.addLayout(_row(self.new_btn, QPushButton("Abbrechen", clicked=self.reject), self.ok, stretch_at=1))
        self._fill(win._last_target)

    def _fill(self, select=None):
        self.tree.clear()
        bold = self.tree.font()
        bold.setBold(True)
        fav = QTreeWidgetItem(self.tree, [f"{STAR} Meine Favoriten"])
        fav.setData(0, UD, ("fav", None))
        fav.setFont(0, bold)
        shared = QTreeWidgetItem(self.tree, ["Gemeinsame Listen (für alle sichtbar)"])
        shared.setData(0, UD, ("liste", None))
        shared.setFont(0, bold)
        lists = self.win.lists = {r["id"]: r for r in queries.list_lists(self.win.conn)}

        def add(parent, kind, parent_id):
            if kind == "pliste":
                rows = sorted(((lid, v["name"]) for lid, v in self.win.store.plists.items() if v["parent"] == parent_id),
                              key=lambda r: r[1].casefold())
            else:
                rows = [(lid, r["name"]) for lid, r in lists.items() if r["parent_id"] == parent_id]
            for lid, name in rows:
                item = QTreeWidgetItem(parent, [name])
                item.setData(0, UD, (kind, lid))
                add(item, kind, lid)

        add(fav, "pliste", None)
        add(shared, "liste", None)
        self.tree.expandAll()
        current = fav
        for it in [fav, shared] + list(MainWindow._walk(fav)) + list(MainWindow._walk(shared)):
            if tuple(it.data(0, UD)) == tuple(select or ()):
                current = it
        self.tree.setCurrentItem(current)

    def _selected(self):
        item = self.tree.currentItem()
        return tuple(item.data(0, UD)) if item else None

    def _update_buttons(self):
        c = self._selected()
        self.ok.setEnabled(c is not None and c != ("liste", None))   # Ordner „Gemeinsame Listen“ selbst ist kein Ziel

    def _new_here(self):
        c = self._selected() or ("fav", None)
        created = self.win._new_container(c, select=False)
        if created:
            self._fill(created)

    def _accept(self):
        self.target = self._selected()
        self.whole_group = self.rb_group is None or self.rb_group.isChecked()
        self.accept()


class CategoryDialog(QDialog):
    """Persönliche Farbkategorien anlegen, umbenennen, umfärben, löschen."""

    def __init__(self, win):
        super().__init__(win)
        self.win, self.store = win, win.store
        self.setWindowTitle("Farbkategorien")
        self.setMinimumSize(420, 360)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.addWidget(QLabel("Eigene Farbkategorien", objectName="cardTitle"))
        lay.addWidget(QLabel("Ihre eigenen Kategorien (gespeichert in Ihrer Favoriten-Datei). Wenn Sie ein Produkt "
                             "einfärben, sehen Kollegen das unter „Änderungen anderer“.", objectName="muted", wordWrap=True))
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda *_: self._rename())
        lay.addWidget(self.list, 1)
        lay.addLayout(_row(QPushButton("Neu …", objectName="primary", clicked=self._new),
                           QPushButton("Umbenennen …", clicked=self._rename),
                           QPushButton("Farbe …", clicked=self._recolor),
                           QPushButton("Löschen", clicked=self._delete),
                           QPushButton("Schließen", clicked=self.accept), stretch_at=4))
        self._fill()

    def _fill(self):
        self.list.clear()
        for cid, c in self.store.categories.items():
            n = sum(v == cid for v in self.store.marks.values())
            item = QListWidgetItem(color_icon(c["farbe"], 16), f"{c['name']}   ({n} Produkte)")
            item.setData(UD, cid)
            self.list.addItem(item)

    def _cid(self):
        item = self.list.currentItem()
        return item.data(UD) if item else None

    def _new(self):
        name, ok = QInputDialog.getText(self, "Neue Farbkategorie", "Name:")
        if not ok or not name.strip():
            return
        color = QColorDialog.getColor(QColor(GREEN), self, "Farbe wählen")
        if color.isValid() and self.win._persist(self.store.add_category, name, color.name()) is not None:
            self._fill()

    def _rename(self):
        cid = self._cid()
        if cid is None:
            return
        name, ok = QInputDialog.getText(self, "Umbenennen", "Name:", text=self.store.categories[cid]["name"])
        if ok and name.strip() and self.win._persist(self.store.update_category, cid, name) is not None:
            self._fill()

    def _recolor(self):
        cid = self._cid()
        if cid is None:
            return
        color = QColorDialog.getColor(QColor(self.store.categories[cid]["farbe"]), self, "Farbe wählen")
        if color.isValid() and self.win._persist(self.store.update_category, cid, None, color.name()) is not None:
            self._fill()

    def _delete(self):
        cid = self._cid()
        if cid is None:
            return
        c = self.store.categories[cid]
        if QMessageBox.question(self, "Kategorie löschen", f"Kategorie „{c['name']}“ löschen?\n"
                                "Die Markierung wird bei allen Produkten entfernt.") == QMessageBox.StandardButton.Yes:
            if self.win._persist(self.store.delete_category, cid) is not None:
                self._fill()


class MainWindow(QMainWindow):
    def __init__(self, db_path, fav_dir=None, settings=None, user=None, auto_backup=True):
        super().__init__()
        self.setWindowTitle(f"HMV-Viewer – Hilfsmittelverzeichnis  (v{__version__})")
        self.resize(1600, 940)
        self.settings = settings or QSettings("HMV-Viewer", "HMV-Viewer")   # je Windows-Benutzer
        apply_view(self.settings.value("dichte", "Normal"), self.settings.value("schrift", 10))
        apply_theme(self.settings.value("design", "Classic"))
        self._icon_targets = []        # (Widget, Icon-Name, Farbname) – nach Designwechsel neu zeichnen
        self._undo = []                # (Beschreibung, Funktion) für Strg+Z
        self.recent = self._load_recent()
        self.extra_nummern = None      # eingefügte Nummernliste als Filter
        self.loaded_rows = []
        self.view_mode = self.settings.value("ansicht", "tabelle")
        self._last_open = self.settings.value("zuletzt_geoeffnet")
        self.db_path = str(db_path)
        self.conn = db.connect(self.db_path)
        self.user = None   # Nachname aus der Benutzer-Tabelle (siehe _set_user)
        self.store = None
        self.lists = {}   # id -> Zeile aus queries.list_lists
        self._last_target = ("fav", None)
        self.design_actions = {}
        self.chips = {}
        self.names = None
        self.first_id = self.latest_id = None
        self.version_by_label = {}
        self.ver_ids = []
        self.filter = ProductFilter()
        self.total = 0
        self.order, self.desc = "nummer", False
        self.hier_data, self.node_by_key = [], {}
        self.current_nummer, self.current_keys = None, {}
        self.note_nummer = None
        self.row_nummer = []
        self.hist_rows = []
        self.change_rows = []
        self._worker = None

        self.search_timer = QTimer(self, singleShot=True, interval=300, timeout=self.apply_filter)
        self.hier_timer = QTimer(self, singleShot=True, interval=250, timeout=self._on_hier_filter)
        self.note_timer = QTimer(self, singleShot=True, interval=800, timeout=self._save_note)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())
        body = QHBoxLayout()
        body.setSpacing(0)
        body.addWidget(self._build_nav())
        self.stack = QStackedWidget(objectName="page")
        self.stack.addWidget(self._build_products_page())
        self.stack.addWidget(self._build_versions_page())
        self.stack.addWidget(self._build_dashboard_page())
        self.stack.addWidget(self._build_activity_page())
        body.addWidget(self.stack, 1)
        root.addLayout(body, 1)
        self.setCentralWidget(central)
        self.toast = Toast(central)
        self.fav_label = QLabel()
        self.statusBar().addPermanentWidget(self.fav_label)
        self.read_only = db.is_read_only(self.db_path)
        if self.read_only:
            ro = QLabel("NUR LESEN – keine Schreibrechte auf die gemeinsame Datenbank")
            ro.setStyleSheet(f"color: {DANGER}; font-weight: 700;")
            self.statusBar().addPermanentWidget(ro)
        self.statusBar().addPermanentWidget(QLabel(f"Datenbank: {self.db_path}"))
        self._bind_shortcuts()
        self._restore_layout()

        self._open_store(fav_dir or self.settings.value("favoriten_ordner") or self._ask_first_folder(), reload=False)
        self._set_user(user or self.settings.value("benutzer") or self._ask_user(first=True))
        self._apply_icons()
        self.reload_all()
        if not queries.list_versions(self.conn):
            QTimer.singleShot(300, self._offer_first_import)
        else:
            self._goto_page_widget(2)   # Startseite
            if self._last_open:
                QTimer.singleShot(700, lambda: self._show_whats_new(auto=True))
        if not self._last_open:
            self.settings.setValue("zuletzt_geoeffnet", dt.datetime.now().isoformat(timespec="seconds"))
        if auto_backup:
            QTimer.singleShot(4000, self._auto_backup)

    # ------------------------------------------------------------------ Aufbau
    def _build_header(self):
        header = QFrame(objectName="header")
        lay = QHBoxLayout(header)
        lay.setContentsMargins(20, 12, 20, 12)
        lay.setSpacing(10)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(QLabel("HMV-Viewer", objectName="title"))
        titles.addWidget(QLabel(f"Hilfsmittelverzeichnis · v{__version__}", objectName="subtitle"))
        lay.addLayout(titles)
        lay.addSpacing(24)
        self.search = QLineEdit(objectName="search", clearButtonEnabled=True)
        self.search.setPlaceholderText("Produkte suchen – Bezeichnung, Hersteller, Nummer oder Notiz   Strg+F")
        self.search.setMinimumWidth(380)
        self.search_icon = self.search.addAction(QIcon(), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(lambda: self.search_timer.start())
        self.search.returnPressed.connect(self.apply_filter)
        self.search.installEventFilter(self)
        lay.addWidget(self.search, 1)
        palette = QPushButton("Strg+K", clicked=self.open_palette,
                              toolTip="Schnellzugriff: Produkte, Gruppen, Listen und Funktionen")
        lay.addWidget(palette)
        lay.addSpacing(10)
        imp = QPushButton("Importieren", objectName="primary", clicked=self.start_import,
                          toolTip="Neue HMV-XML oder ZIP einlesen (Strg+I)")
        exp = QPushButton("Excel-Export", clicked=self.start_export,
                          toolTip="Auswahl, Favoriten oder alles nach Excel (Strg+E)")
        fav = QPushButton("Favoriten", clicked=self.show_favorites, toolTip="Strg+B")
        for w in (imp, exp, fav):
            lay.addWidget(w)
        self.user_btn = QPushButton("Benutzer ▾", toolTip="Wer bin ich? Wird bei gemeinsamen Listen und Kommentaren angezeigt")
        user_menu = QMenu(self.user_btn)
        user_menu.aboutToShow.connect(lambda: self._fill_user_menu(user_menu))
        self.user_btn.setMenu(user_menu)
        lay.addWidget(self.user_btn)
        menu_btn = QPushButton("Mehr ▾")
        menu = QMenu(menu_btn)
        menu.addAction(make_icon("plus"), "Neue private Liste …", lambda: self._new_container(("pliste", None)))
        menu.addAction(make_icon("plus"), "Neue gemeinsame Liste …", lambda: self._new_container(("liste", None)))
        menu.addAction(make_icon("paste"), "Nummernliste einfügen …  (Strg+Umschalt+V)", self._paste_numbers)
        menu.addAction(make_icon("bell"), "Was ist neu? …", lambda: self._show_whats_new(auto=False))
        menu.addSeparator()
        menu.addAction("Speicherort für Favoriten & Notizen …", self._change_fav_folder)
        menu.addAction("Favoriten-Ordner im Explorer öffnen", self._open_fav_folder)
        menu.addAction(make_icon("tag"), "Farbkategorien verwalten …", self._manage_categories)
        menu.addSeparator()
        menu.addAction(make_icon("save"), "Datenbank sichern (Backup) …", self._backup_db)
        menu.addAction("Datenbank aus Sicherung wiederherstellen (NUR IM NOTFALL) …", self._restore_db)
        menu.addSeparator()
        design = menu.addMenu("Design")
        current = self.settings.value("design", "Classic")
        for name in THEME_NAMES:
            act = design.addAction(name, lambda name=name: self.set_theme(name))
            act.setCheckable(True)
            act.setChecked(name == current)
            self.design_actions[name] = act
        view = menu.addMenu("Ansicht")
        dens = view.addMenu("Zeilenhöhe")
        cur_d = self.settings.value("dichte", "Normal")
        for name in DENSITY:
            act = dens.addAction(name, lambda name=name: self.set_view(density=name))
            act.setCheckable(True)
            act.setChecked(name == cur_d)
        fonts = view.addMenu("Schriftgröße")
        cur_f = int(self.settings.value("schrift", 10))
        for size in FONT_SIZES:
            act = fonts.addAction(f"{size} pt", lambda size=size: self.set_view(font_pt=size))
            act.setCheckable(True)
            act.setChecked(size == cur_f)
        menu.addSeparator()
        menu.addAction("Tastenkürzel …", self._show_shortcuts)
        menu.addAction(make_icon("info"), "Info & Support …", self._show_info)
        menu.addAction("Neu laden  (F5)", self.reload_all)
        menu_btn.setMenu(menu)
        lay.addWidget(menu_btn)
        self._icon_targets += [(palette, "command", "HEADER_FG"), (imp, "import", "HEADER_PRIMARY_FG"),
                               (exp, "export", "HEADER_FG"), (fav, "star", "HEADER_FG"),
                               (self.user_btn, "user", "HEADER_FG"), (menu_btn, "menu", "HEADER_FG")]
        return header

    def _apply_icons(self):
        for widget, name, color in self._icon_targets:
            widget.setIcon(make_icon(name, globals()[color]))
        self.search_icon.setIcon(make_icon("search", MUTED))

    def _build_nav(self):
        nav = QFrame(objectName="nav")
        nav.setFixedWidth(116)
        lay = QVBoxLayout(nav)
        lay.setContentsMargins(10, 14, 10, 14)
        self.nav_group = QButtonGroup(self)
        # id = Index im Stapel: 0 Produkte, 1 Versionen, 2 Startseite (steht oben), 3 Änderungen anderer
        for i, text, icon, tip in ((2, "Start", "home", "Übersicht (Strg+0)"), (0, "Produkte", "box", "Strg+1"),
                                   (1, "Versionen", "history", "Importe und Änderungen (Strg+2)"),
                                   (3, "Änderungen\nanderer", "comment",
                                    "Was andere Benutzer kommentiert, eingefärbt oder an Listen geändert haben (Strg+3)")):
            b = QToolButton(text=text, checkable=True, checked=(i == 0), toolTip=tip)
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            b.setIconSize(QSize(22, 22))
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            b.setMinimumHeight(64)
            self.nav_group.addButton(b, i)
            self._icon_targets.append((b, icon, "MUTED"))
            lay.addWidget(b)
        self.nav_group.idClicked.connect(self._goto_page_widget)
        lay.addStretch(1)
        return nav

    def _goto_page_widget(self, i):
        self.nav_group.button(i).setChecked(True)
        self.stack.setCurrentIndex(i)
        if i == 2:
            self.refresh_dashboard()
        elif i == 3:
            self.refresh_activity(mark_seen=True)

    def _build_activity_page(self):
        page = QWidget(objectName="page")
        outer = QVBoxLayout(page)
        outer.setContentsMargins(14, 14, 14, 14)
        card, lay = _card("Änderungen anderer Benutzer")
        lay.addWidget(QLabel("Kommentare, Farbmarkierungen und Änderungen an gemeinsamen Listen von Kolleginnen und "
                             "Kollegen. Doppelklick öffnet das Produkt bzw. die Liste.", objectName="muted", wordWrap=True))
        self.act_period = QComboBox(minimumWidth=150)
        for text, days in (("Letzte 7 Tage", 7), ("Letzte 30 Tage", 30), ("Letzte 90 Tage", 90), ("Alles", 0)):
            self.act_period.addItem(text, days)
        self.act_period.setCurrentIndex(1)
        self.act_kind = QComboBox(minimumWidth=170)
        self.act_kind.addItem("Alle Arten", None)
        for key, label in queries.ACTIVITY_KINDS.items():
            self.act_kind.addItem(label, key)
        self.act_user = QComboBox(minimumWidth=170)
        for cb in (self.act_period, self.act_kind, self.act_user):
            cb.activated.connect(lambda *_: self.refresh_activity())
        refresh = QPushButton("Aktualisieren", clicked=lambda: self.refresh_activity())
        self._icon_targets.append((refresh, "history", "GREEN"))
        self.act_info = QLabel(objectName="muted")
        self.act_mine = QCheckBox("Eigene Änderungen auch anzeigen", toggled=lambda *_: self.refresh_activity())
        self.act_mine.setMinimumWidth(self.act_mine.sizeHint().width() + 16)   # Beschriftung nie abschneiden
        lay.addLayout(_row(QLabel("Zeitraum"), self.act_period, QLabel("Art"), self.act_kind, QLabel("Benutzer"),
                           self.act_user, self.act_mine, refresh, self.act_info, stretch_at=8))
        cols = (("at", "Zeitpunkt", 140), ("user", "Benutzer", 120), ("art", "Art", 150), ("nummer", "Hilfsmittelnummer", 125),
                ("name", "Bezeichnung", 300), ("detail", "Inhalt", 420))
        self.act_table = _table(cols)
        self.act_table.cellDoubleClicked.connect(lambda r, c: self._open_activity(r))
        self.act_empty = QLabel(objectName="empty", alignment=Qt.AlignmentFlag.AlignCenter, wordWrap=True)
        self.act_empty.linkActivated.connect(lambda link: self.act_mine.setChecked(True) if link == "mine"
                                             else self._set_user(self._ask_user()))
        self.act_stack = QStackedWidget()
        self.act_stack.addWidget(self.act_table)
        self.act_stack.addWidget(self.act_empty)
        lay.addWidget(self.act_stack, 1)
        outer.addWidget(card)
        self.act_rows = []
        return page

    def refresh_activity(self, mark_seen=False):
        if self.store is None:
            return
        days = self.act_period.currentData()
        since = (dt.datetime.now() - dt.timedelta(days=days)).isoformat(timespec="seconds") if days else ""
        current_user = self.act_user.currentData()
        self.act_user.blockSignals(True)
        self.act_user.clear()
        mine = self.act_mine.isChecked()
        self.act_user.addItem("Alle Benutzer" if mine else "Alle anderen", None)
        for name in queries.list_users(self.conn):
            if mine or name != self.user:
                self.act_user.addItem(name, name)
        self.act_user.setCurrentIndex(max(0, self.act_user.findData(current_user)))
        self.act_user.blockSignals(False)
        self.act_rows = queries.others_activity(self.conn, None if mine else self.user, since,
                                                self.act_kind.currentData(), self.act_user.currentData())
        t = self.act_table
        t.setRowCount(len(self.act_rows))
        for r, a in enumerate(self.act_rows):
            if a["art"] == "kategorie":
                detail = f"eingefärbt: {a['detail']}" if a["detail"] else "Farbmarkierung entfernt"
            else:
                detail = a["detail"] or ""
            _fill_row(t, r, (_when(a["at"]), a["user"] or "?", queries.ACTIVITY_KINDS.get(a["art"], a["art"]),
                             format_nummer(a["nummer"]) if a["nummer"] else "", a["bezeichnung"] or "", _clean(detail)))
            t.item(r, 2).setIcon(make_icon({"kommentar": "comment", "kategorie": "tag", "liste": "list"}[a["art"]],
                                           a["farbe"] or GREEN, 16))
            t.item(r, 5).setToolTip(_tip(detail))
        self.act_info.setText(f"{len(self.act_rows)} Einträge")
        self._show_activity_empty(since, mine)
        if mark_seen:
            self.settings.setValue("aktivitaet_gesehen", dt.datetime.now().isoformat(timespec="seconds"))
        self._update_activity_badge()

    def _show_activity_empty(self, since, mine):
        """Leere Ansicht erklären – meist sind alle Einträge die eigenen (die hier ausgeblendet werden)."""
        if self.act_rows:
            self.act_stack.setCurrentWidget(self.act_table)
            return
        own = 0 if mine else len(queries.others_activity(self.conn, None, since, self.act_kind.currentData(),
                                                          self.user, limit=1000))
        others = [n for n in queries.list_users(self.conn) if n != self.user]
        text = "<p><b>Keine Einträge im gewählten Zeitraum.</b></p>"
        if own:
            text = (f"<p><b>Keine Änderungen anderer Benutzer.</b></p><p>Alle {own} Einträge in diesem Zeitraum stammen "
                    f"von Ihnen (<b>{html.escape(self.user or '?')}</b>) und werden hier ausgeblendet.<br>"
                    f"<a href='mine' style='color:{GREEN}'>Eigene Änderungen anzeigen</a></p>")
        elif not mine:
            text += "<p>Hier erscheint, was andere kommentieren, farblich markieren oder an gemeinsamen Listen ändern.</p>"
        if not others:
            text += ("<p>Bisher ist nur ein Benutzer angelegt. Sobald Kolleginnen und Kollegen mit ihrem Namen arbeiten, "
                     f"erscheinen ihre Änderungen hier. <a href='user' style='color:{GREEN}'>Benutzer wechseln/anlegen …</a></p>")
        self.act_empty.setText(text)
        self.act_stack.setCurrentWidget(self.act_empty)

    def _update_activity_badge(self):
        """Zähler neuer Einträge anderer seit dem letzten Öffnen des Reiters (am Navigations-Button)."""
        try:
            n = len(queries.others_activity(self.conn, self.user, self.settings.value("aktivitaet_gesehen") or "", limit=100))
        except sqlite3.OperationalError:
            return
        btn = self.nav_group.button(3)
        btn.setText("Änderungen\nanderer" + (f" ({n if n < 100 else '99+'})" if n else ""))

    def _open_activity(self, row):
        a = self.act_rows[row]
        if a["nummer"]:
            self._open_product(a["nummer"])
        elif a["liste_id"] and self._item_for_key({"liste": a["liste_id"]}) is not None:
            self._goto_page_widget(0)
            self._on_detail_link(f"liste:{a['liste_id']}")

    def _build_products_page(self):
        page = QWidget(objectName="page")
        lay = QHBoxLayout(page)
        lay.setContentsMargins(14, 14, 14, 14)
        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.split.setHandleWidth(12)
        self.split.addWidget(self._build_tree_card())
        self.split.addWidget(self._build_list_card())
        self.split.addWidget(self._build_detail_card())
        self.split.setSizes([300, 900, 430])
        self.split.setStretchFactor(1, 1)
        lay.addWidget(self.split)
        return page

    def _build_tree_card(self):
        card, lay = _card("Produktgruppen")
        card.setMinimumWidth(250)
        self.hier_filter = QLineEdit(clearButtonEnabled=True, placeholderText="Filtern: Name oder Nummer, z. B. 10.50")
        self.hier_filter.setToolTip("Strg+G")
        self.hier_filter.textChanged.connect(lambda: self.hier_timer.start())
        lay.addWidget(self.hier_filter)
        self.hier = QTreeWidget(headerHidden=True)
        self.hier.setIndentation(16)
        self.hier.currentItemChanged.connect(lambda *a: self._on_tree_changed())
        self.hier.setAcceptDrops(True)
        self.hier.viewport().setAcceptDrops(True)
        self.hier.viewport().installEventFilter(self)   # Produkte aus der Liste auf eine Liste ziehen
        self.hier.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.hier.customContextMenuRequested.connect(self._hier_menu)
        lay.addWidget(self.hier, 1)
        lay.addWidget(QLabel("Rechtsklick: Gruppe merken, Listen anlegen · Produkte per Maus auf eine Liste ziehen",
                             objectName="muted", wordWrap=True))
        return card

    def _build_list_card(self):
        card, lay = _card()
        self.list_title = QLabel("Produkte", objectName="cardTitle")
        self.saved_btn = QPushButton("Gespeicherte Suchen ▾", toolTip="Filterkombination merken und wieder aufrufen")
        saved_menu = QMenu(self.saved_btn)
        saved_menu.aboutToShow.connect(lambda: self._fill_saved_menu(saved_menu))
        self.saved_btn.setMenu(saved_menu)
        self.btn_table = QToolButton(objectName="viewToggle", checkable=True, toolTip="Tabellenansicht")
        self.btn_cards = QToolButton(objectName="viewToggle", checkable=True, toolTip="Kartenansicht")
        view_group = QButtonGroup(self)
        view_group.addButton(self.btn_table)
        view_group.addButton(self.btn_cards)
        self.btn_table.clicked.connect(lambda: self.set_view_mode("tabelle"))
        self.btn_cards.clicked.connect(lambda: self.set_view_mode("karten"))
        self._icon_targets += [(self.btn_table, "table", "TEXT"), (self.btn_cards, "cards", "TEXT"),
                               (self.saved_btn, "search", "GREEN")]
        lay.addLayout(_row(self.list_title, self.saved_btn, self.btn_table, self.btn_cards, stretch_at=1))

        self.cb_status = QComboBox(minimumWidth=130, toolTip="Aktive, entfernte oder alle Produkte")
        self.cb_status.addItems(list(STATUS_CHOICES))
        self.cb_version = QComboBox(minimumWidth=210, toolTip="Nur Produkte, die sich in dieser Version geändert haben")
        self.cb_type = QComboBox(minimumWidth=200)
        self.cb_type.addItems(list(TYPE_CHOICES))
        for cb in (self.cb_status, self.cb_version, self.cb_type):
            cb.activated.connect(lambda *_: self.apply_filter())
        lay.addLayout(_row(QLabel("Status"), self.cb_status, QLabel("Änderung in"), self.cb_version, self.cb_type,
                           stretch_at=5))

        self.cb_hersteller = QComboBox(editable=True, minimumWidth=200, toolTip="Teil des Herstellernamens eintippen (Strg+H)")
        self.cb_hersteller.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.cb_hersteller.setMaxVisibleItems(18)
        self.cb_hersteller.lineEdit().setPlaceholderText(ALL_HERSTELLER)
        self.cb_hersteller.lineEdit().setClearButtonEnabled(True)
        completer = self.cb_hersteller.completer()
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.popup().setObjectName("completer")
        self.cb_hersteller.lineEdit().textChanged.connect(lambda: self.search_timer.start())
        self.chk_merk = QCheckBox("Suche auch in Merkmalen", toggled=lambda *_: self.apply_filter())
        self.cb_kat = QComboBox(minimumWidth=150, toolTip="Nur Produkte mit dieser Farbkategorie (Ihre eigenen Kategorien)")
        self.cb_kat.activated.connect(lambda *_: self.apply_filter())
        reset = QPushButton("Filter zurücksetzen", clicked=self.reset_filter)
        self.note_search = QLineEdit(clearButtonEnabled=True, minimumWidth=260,
                                     placeholderText="Nur in Notizen und Kommentaren suchen")
        self.note_search.setToolTip("Findet Produkte, deren eigene Notiz oder Kommentare diese Wörter enthalten. "
                                    "Die große Suche oben findet sie ebenfalls.")
        self.note_search.textChanged.connect(lambda: self.search_timer.start())
        lay.addLayout(_row(QLabel("Hersteller"), self.cb_hersteller, QLabel("Kategorie"), self.cb_kat, stretch_at=4))
        lay.addLayout(_row(QLabel("Notizen"), self.note_search, self.chk_merk, reset, stretch_at=3))

        self.table = _table(PRODUCT_COLUMNS)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setDragEnabled(True)
        self.table.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.table.setDefaultDropAction(Qt.DropAction.CopyAction)
        hdr = self.table.horizontalHeader()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(COL["bezeichnung"], QHeaderView.ResizeMode.Stretch)
        hdr.setSortIndicatorShown(True)
        hdr.setSectionsMovable(True)
        hdr.sectionClicked.connect(self._sort_by)
        hdr.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        hdr.customContextMenuRequested.connect(self._column_menu)
        self.table.itemSelectionChanged.connect(self._on_product_select)
        self.table.cellClicked.connect(lambda r, c: c == COL["fav"] and self._toggle_fav(self.row_nummer[r]))
        self.table.cellDoubleClicked.connect(lambda r, c: c != COL["fav"] and self._edit_note())
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._product_menu)
        self.table.verticalScrollBar().valueChanged.connect(self._maybe_load_more)

        self.cards = CardView()
        self.cards.nummerSelected.connect(self._on_card_select)
        self.cards.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.cards.customContextMenuRequested.connect(self._card_menu)
        self.cards.verticalScrollBar().valueChanged.connect(self._maybe_load_more)

        self.empty = QWidget()
        elay = QVBoxLayout(self.empty)
        elay.addStretch(1)
        self.empty_icon = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.empty_text = QLabel(objectName="empty", alignment=Qt.AlignmentFlag.AlignCenter, wordWrap=True)
        self.empty_text.linkActivated.connect(lambda link: self.start_import() if link == "import" else self.reset_filter())
        elay.addWidget(self.empty_icon)
        elay.addWidget(self.empty_text)
        elay.addStretch(2)
        self.list_stack = QStackedWidget()
        for w in (self.table, self.empty, self.cards):
            self.list_stack.addWidget(w)
        lay.addWidget(self.list_stack, 1)

        self.pager_label = QLabel(objectName="muted")
        chips = [QLabel("Letzte Version:", objectName="muted")]
        for ctype in (NEU, GEAENDERT, REAKTIVIERT, ENTFERNT):
            chip = self.chips[ctype] = QLabel(CHANGE_LABELS[ctype], objectName="chip")
            chip.setStyleSheet(f"background: {TAG_COLORS[ctype]};")
            chips.append(chip)
        lay.addLayout(_row(self.pager_label, *chips, stretch_at=1))
        return card

    def _build_detail_card(self):
        card, lay = _card()
        self.btn_fav = QPushButton("Merken", clicked=self._toggle_selected_fav, toolTip="Strg+D")
        self.btn_copy = QPushButton("Kopieren", clicked=lambda: self._copy("formatted"), toolTip="Hilfsmittelnummer kopieren")
        self.cb_detail_kat = QComboBox(minimumWidth=150, toolTip="Persönliche Farbkategorie für dieses Produkt")
        self.cb_detail_kat.activated.connect(
            lambda *_: self.current_nummer and self._set_mark([self.current_nummer], self.cb_detail_kat.currentData()))
        self._icon_targets += [(self.btn_copy, "copy", "GREEN")]
        lay.addLayout(_row(self.btn_fav, self.btn_copy, self.cb_detail_kat, stretch_at=2))

        self.detail_tabs = QTabWidget()
        self.detail = QScrollArea(widgetResizable=True, frameShape=QFrame.Shape.NoFrame)
        inner = QWidget()
        dlay = QVBoxLayout(inner)
        dlay.setContentsMargins(4, 6, 8, 6)
        self.detail_title = QLabel(objectName="detailTitle", wordWrap=True, textFormat=Qt.TextFormat.PlainText)
        self.detail_chips = QHBoxLayout()
        self.detail_chips.setSpacing(6)
        self.detail_hint = QLabel(objectName="muted", wordWrap=True)
        dlay.addWidget(self.detail_title)
        dlay.addLayout(self.detail_chips)
        self.sec_info = CollapsibleSection("Einordnung")
        self.sec_merk = CollapsibleSection("Merkmale")
        self.sec_lists = CollapsibleSection("Listen")
        for sec in (self.sec_info, self.sec_merk, self.sec_lists):
            sec.linkActivated.connect(lambda url: self._on_detail_link(url.split(":", 1)[1]))
            dlay.addWidget(sec)
        dlay.addWidget(self.detail_hint)
        dlay.addStretch(1)
        self.detail.setWidget(inner)
        self.detail_tabs.addTab(self.detail, "Details")

        self.comments = CommentsWidget()
        self.comments.send.connect(self._send_comment)
        self.comments.delete.connect(self._delete_comment)
        self.detail_tabs.addTab(self.comments, "Kommentare")

        hist = QSplitter(Qt.Orientation.Vertical)
        self.hist_tree = QTreeWidget(rootIsDecorated=False, alternatingRowColors=True)
        self.hist_tree.setHeaderLabels(["Version", "Importiert", "Änderung", "Felder"])
        for i, w in enumerate((140, 90, 110)):
            self.hist_tree.setColumnWidth(i, w)
        self.hist_tree.currentItemChanged.connect(self._on_hist_select)
        self.hist_text = QTextBrowser()
        hist.addWidget(self.hist_tree)
        hist.addWidget(self.hist_text)
        hist.setSizes([180, 320])
        self.detail_tabs.addTab(hist, "Historie")
        lay.addWidget(self.detail_tabs, 1)

        lay.addWidget(QLabel("Meine Notiz", objectName="cardTitle"))
        self.note_edit = QPlainTextEdit(placeholderText="z. B. Hinweise, Ansprechpartner … "
                                                        "(nur für Sie, wird automatisch gespeichert)")
        self.note_edit.setMaximumHeight(90)
        self.note_edit.setToolTip("Strg+N · wird in Ihrer persönlichen Favoriten-Datei gespeichert")
        self.note_edit.textChanged.connect(lambda: self.note_timer.start())
        lay.addWidget(self.note_edit)
        return card

    def _build_dashboard_page(self):
        page = QWidget(objectName="page")
        outer = QVBoxLayout(page)
        outer.setContentsMargins(22, 18, 22, 18)
        outer.setSpacing(14)
        head = QHBoxLayout()
        self.greeting = QLabel(objectName="greeting")
        head.addWidget(self.greeting, 1)
        for text, icon, fn in (("Suchen  (Strg+K)", "search", self.open_palette),
                               ("Nummernliste einfügen", "paste", self._paste_numbers),
                               ("Meine Favoriten", "star", self.show_favorites),
                               ("Was ist neu?", "bell", lambda: self._show_whats_new(auto=False))):
            b = QPushButton(text, clicked=fn)
            self._icon_targets.append((b, icon, "GREEN"))
            head.addWidget(b)
        outer.addLayout(head)
        tiles = QHBoxLayout()
        tiles.setSpacing(14)
        self.tile_products = stat_tile("Produkte im Verzeichnis", "box")
        self.tile_import = stat_tile("Letzter Import", "import")
        self.tile_favs = stat_tile("Meine Favoriten", "star")
        self.tile_lists = stat_tile("Gemeinsame Listen", "list")
        for t in (self.tile_products, self.tile_import, self.tile_favs, self.tile_lists):
            tiles.addWidget(t)
        outer.addLayout(tiles)
        body = QHBoxLayout()
        body.setSpacing(14)
        chart_card, cl = _card("Änderungen je Version")
        self.chart = BarChart()
        cl.addWidget(self.chart, 1)
        body.addWidget(chart_card, 3)
        side = QVBoxLayout()
        side.setSpacing(14)
        rc, rl = _card("Zuletzt angesehen")
        self.dash_recent = ClickList()
        rl.addWidget(self.dash_recent)
        lc, ll = _card("Zuletzt geänderte gemeinsame Listen")
        self.dash_lists = ClickList()
        ll.addWidget(self.dash_lists)
        side.addWidget(rc)
        side.addWidget(lc)
        body.addLayout(side, 2)
        outer.addLayout(body, 1)
        return page

    def _build_versions_page(self):
        page = QWidget(objectName="page")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(14, 14, 14, 14)
        split = QSplitter(Qt.Orientation.Vertical)
        split.setHandleWidth(12)

        card, clay = _card("Importierte Versionen")
        clay.addWidget(QLabel("Jeder Import der XML ist eine Version. Auswahl zeigt unten, was sich geändert hat.",
                              objectName="muted"))
        cols = (("id", "Version", 70), ("imported", "Importiert am", 150), ("stand", "Stand-Datum", 100),
                ("logisch", "logische Vers.", 100), ("total", "Produkte", 90), ("neu", "Neu", 70),
                ("geaendert", "Geändert", 80), ("entfernt", "Entfernt", 80), ("wieder", "Wieder aufgen.", 110),
                ("stamm", "Änd. Stammdaten", 120), ("quelle", "Quelle", 300))
        self.ver_table = _table(cols)
        self.ver_table.itemSelectionChanged.connect(self._load_version_changes)
        clay.addWidget(self.ver_table, 1)
        split.addWidget(card)

        card, clay = _card()
        self.ver_title = QLabel("Änderungen der Version", objectName="cardTitle")
        self.cb_vtype = QComboBox(minimumWidth=200)
        self.cb_vtype.addItems(list(TYPE_CHOICES))
        self.cb_vtype.activated.connect(lambda *_: self._load_version_changes())
        self.ver_note = QLabel(objectName="muted")
        clay.addLayout(_row(self.ver_title, self.cb_vtype,
                            QPushButton("In Produktliste anzeigen", objectName="primary",
                                        clicked=self._show_version_in_products),
                            self.ver_note, QLabel("Doppelklick auf ein Produkt öffnet es", objectName="muted"),
                            stretch_at=4))
        cols = (("typ", "Änderung", 130), ("ebene", "Ebene", 120), ("nummer", "Nummer", 130),
                ("name", "Bezeichnung", 480), ("felder", "Geänderte Felder", 280))
        self.chg_table = _table(cols)
        self.chg_table.cellDoubleClicked.connect(lambda r, c: self._on_change_double_click(r))
        clay.addWidget(self.chg_table, 1)
        split.addWidget(card)
        split.setSizes([260, 600])
        lay.addWidget(split)
        return page

    def _bind_shortcuts(self):
        def focus(widget):
            self._goto_page_widget(0)
            widget.setFocus()
            if isinstance(widget, QLineEdit):
                widget.selectAll()

        for seq, fn in (("Ctrl+F", lambda: focus(self.search)), ("Ctrl+G", lambda: focus(self.hier_filter)),
                        ("Ctrl+H", lambda: focus(self.cb_hersteller.lineEdit())),
                        ("Ctrl+D", self._toggle_selected_fav), ("Ctrl+B", self.show_favorites),
                        ("Ctrl+N", self._edit_note),
                        ("Ctrl+I", self.start_import), ("Ctrl+E", self.start_export),
                        ("Ctrl+K", self.open_palette), ("Ctrl+Z", self._undo_last),
                        ("Ctrl+Shift+V", self._paste_numbers), ("Ctrl+0", lambda: self._goto_page_widget(2)),
                        ("Ctrl+1", lambda: self._goto_page_widget(0)), ("Ctrl+2", lambda: self._goto_page_widget(1)),
                        ("Ctrl+3", lambda: self._goto_page_widget(3)),
                        ("F5", self.reload_all)):
            QShortcut(QKeySequence(seq), self, activated=fn)
        QShortcut(QKeySequence.StandardKey.Copy, self.table, activated=lambda: self._copy("table"),
                  context=Qt.ShortcutContext.WidgetShortcut)

    def eventFilter(self, obj, event):
        if obj is self.search and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Down and self.table.rowCount():
                self.table.setFocus()
                self.table.selectRow(0)
                return True
            if event.key() == Qt.Key.Key_Escape:
                self.search.clear()
                return True
        hier = getattr(self, "hier", None)   # Filter läuft schon während des Aufbaus
        if hier is not None and obj is hier.viewport() and event.type() in (
                QEvent.Type.DragEnter, QEvent.Type.DragMove, QEvent.Type.Drop):
            return self._tree_drop_event(event)
        return super().eventFilter(obj, event)

    def _tree_drop_event(self, event):
        """Produkte aus der Tabelle auf Meine Favoriten oder eine Liste ziehen."""
        if event.source() is not self.table:
            event.ignore()
            return True
        item = self.hier.itemAt(event.position().toPoint())
        c = self._container_of_key(item.data(0, UD) or {}) if item else None
        if c is None:
            event.ignore()
            return True
        if event.type() == QEvent.Type.Drop:
            self._container_add(c, self._selected_nummern())
        else:
            self.statusBar().showMessage(f"Loslassen fügt die markierten Produkte zu „{self._container_name(c)}“ hinzu", 1500)
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
        return True

    def _show_shortcuts(self):
        rows = "".join(f"<tr><td style='padding:3px 16px 3px 0'><b>{k}</b></td><td>{v}</td></tr>" for k, v in SHORTCUTS)
        QMessageBox.information(self, "Tastenkürzel", f"<table>{rows}</table>"
                                "<p>Klick in die ★-Spalte: Favorit umschalten · Doppelklick auf eine Zeile: Notiz.<br>"
                                "Gruppe, Art oder Hersteller in den Details anklicken: danach filtern.</p>")

    # ------------------------------------------------------------------ Fenster-Zustand
    def _restore_layout(self):
        geo = self.settings.value("fenster")
        if geo is not None:
            self.restoreGeometry(geo)
        sizes = self.settings.value("spalten")
        if sizes:
            self.split.setSizes([int(s) for s in sizes])
        state = self.settings.value("tabelle_v3")
        if state is not None:
            self.table.horizontalHeader().restoreState(state)
        self.btn_cards.setChecked(self.view_mode == "karten")
        self.btn_table.setChecked(self.view_mode != "karten")

    def closeEvent(self, event):
        self._save_note()
        self.settings.setValue("fenster", self.saveGeometry())
        self.settings.setValue("spalten", self.split.sizes())
        self.settings.setValue("tabelle_v3", self.table.horizontalHeader().saveState())
        self.settings.setValue("zuletzt_geoeffnet", dt.datetime.now().isoformat(timespec="seconds"))
        super().closeEvent(event)

    # ------------------------------------------------------------------ Favoriten-Datei
    def _ask_first_folder(self):
        default = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)) / "HMV-Viewer"
        box = QMessageBox(self)
        box.setWindowTitle("Speicherort für Ihre Favoriten")
        box.setText("<b>Wo sollen Ihre persönlichen Favoriten und Notizen gespeichert werden?</b>")
        box.setInformativeText(f"Jeder Benutzer hat eine eigene Datei ({FILE_NAME}).\n\nVorschlag:\n{default}\n\n"
                               "Tipp: Ein Ordner auf dem Netzlaufwerk bleibt auch beim PC-Wechsel erhalten. "
                               "Ändern geht jederzeit über „Mehr ▾“.")
        use_default = box.addButton("Vorschlag verwenden", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Anderen Ordner wählen …", QMessageBox.ButtonRole.ActionRole)
        box.exec()
        if box.clickedButton() is not use_default:
            folder = QFileDialog.getExistingDirectory(self, "Ordner für Favoriten & Notizen wählen", str(default.parent))
            if folder:
                return folder
        return str(default)

    def _open_store(self, folder, reload=True, carry=None):
        """Öffnet die Favoriten-Datei im Ordner; bei Fehler Rückfrage nach anderem Ordner."""
        try:
            store = FavoriteStore(folder)
        except OSError as exc:
            QMessageBox.warning(self, "Favoriten nicht lesbar",
                                f"Die Favoriten-Datei in\n{folder}\nkann nicht gelesen werden:\n{exc}\n\n"
                                "Bitte einen anderen Ordner wählen.")
            new = QFileDialog.getExistingDirectory(self, "Ordner für Favoriten & Notizen wählen")
            if new:
                return self._open_store(new, reload, carry)
            if self.store is not None:
                return False
            folder = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
            store = FavoriteStore(folder)
        if store.recovered:
            QMessageBox.warning(self, "Favoriten-Datei beschädigt",
                                f"Die Datei war beschädigt und wurde gesichert als:\n{store.recovered}\n\n"
                                "Es wird mit leeren Favoriten weitergearbeitet.")
        if store.is_new:
            # Übernahme aus dem bisherigen Ordner bzw. aus der gemeinsamen DB von v1.x
            for k in (list(carry.favs) if carry else legacy_db_keys(self.conn)):
                store.favs.setdefault(k, dt.datetime.now().isoformat(timespec="seconds"))
            if carry:
                store.notes.update(carry.notes)
            if self._persist(store.save) is None and self.store is not None:
                return False
        self.store = store
        self.settings.setValue("favoriten_ordner", str(Path(folder)))
        self.store.attach(self.conn)
        self.fav_label.setText(f"{STAR} Favoriten: {store.path}")
        self.fav_label.setToolTip("Persönliche Favoriten & Notizen – Ort ändern über „Mehr ▾“")
        if reload:
            self.reload_all()
        return True

    def _change_fav_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Ordner für Favoriten & Notizen wählen", str(self.store.path.parent))
        if not folder or Path(folder) == self.store.path.parent:
            return
        carry = None
        if not (Path(folder) / FILE_NAME).exists() and (self.store.favs or self.store.notes):
            ans = QMessageBox.question(self, "Favoriten übernehmen?",
                                       f"Im gewählten Ordner gibt es noch keine Favoriten-Datei.\n\n"
                                       f"Ihre aktuellen {len(self.store.favs)} Favoriten und {len(self.store.notes)} "
                                       "Notizen dorthin übernehmen?")
            carry = self.store if ans == QMessageBox.StandardButton.Yes else None
        self._save_note()
        if self._open_store(folder, carry=carry):
            self.statusBar().showMessage(f"Favoriten werden jetzt gespeichert in {self.store.path}", 6000)

    def _open_fav_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.store.path.parent)))

    def _persist(self, fn, *args):
        """Ruft eine Speicher-Funktion auf; Fehler (z. B. Netzlaufwerk weg) werden gemeldet. None = fehlgeschlagen."""
        try:
            result = fn(*args)
        except OSError as exc:
            QMessageBox.critical(self, "Speichern fehlgeschlagen",
                                 f"Favoriten/Notizen konnten nicht gespeichert werden:\n{exc}\n\n"
                                 "Ist der Ordner erreichbar? Speicherort ändern über „Mehr ▾“.")
            return None
        return True if result is None else result

    # ------------------------------------------------------------------ Laden
    def reload_all(self):
        self.store.attach(self.conn)
        self.names = queries.Names(self.conn)
        self.first_id = queries.first_import_id(self.conn)
        self.latest_id = queries.latest_import_id(self.conn)
        versions = queries.list_versions(self.conn)
        current = self.cb_version.currentText()
        self.version_by_label = {queries.version_label(v): v["id"] for v in versions}
        self.cb_version.clear()
        self.cb_version.addItems([ALL_VERSIONS] + list(self.version_by_label))
        self.cb_version.setCurrentText(current if current in self.version_by_label else ALL_VERSIONS)
        hersteller = self.cb_hersteller.currentText()
        self._quiet(self.cb_hersteller.lineEdit(), self._fill_hersteller, hersteller)
        self._fill_categories()
        self.comment_info = queries.comment_summary(self.conn)
        self.hier_data = queries.hierarchy_tree(self.conn)
        self.node_by_key = {}

        def index(nodes):
            for n in nodes:
                self.node_by_key[_key_tuple(n["key"])] = n
                index(n["children"])

        index(self.hier_data)
        self._load_hierarchy()
        self.apply_filter()
        self._load_versions()
        if self.stack.currentIndex() == 2:
            self.refresh_dashboard()
        self._update_activity_badge()

    def _fill_hersteller(self, text):
        self.cb_hersteller.clear()
        self.cb_hersteller.addItems(queries.list_hersteller(self.conn))
        self.cb_hersteller.setCurrentIndex(-1)
        self.cb_hersteller.setEditText(text)

    def _current_key(self):
        item = self.hier.currentItem()
        return item.data(0, UD) if item else {}

    def _load_hierarchy(self):
        prev = self._current_key()
        term = self.hier_filter.text().strip().casefold()
        nodes = prune(self.hier_data, term) if term else self.hier_data
        self.hier.blockSignals(True)
        try:
            self.hier.clear()
            self.fav_item = QTreeWidgetItem([STAR])
            self.fav_item.setData(0, UD, {"favoriten": True})
            self.fav_item.setForeground(0, QBrush(QColor(GOLD)))
            self.fav_item.setToolTip(0, "Nur für Sie: gemerkte Produkte, ganze Gruppen und private Listen · Rechtsklick: neue Liste")
            font = self.fav_item.font(0)
            font.setBold(True)
            self.fav_item.setFont(0, font)
            total = queries.count_products(self.conn, ProductFilter(status="aktiv"))
            self.all_item = QTreeWidgetItem([f"Alle Produkte  ({_dots(total)})"])
            self.all_item.setData(0, UD, {})
            self.all_item.setFont(0, font)
            self.lists_item = QTreeWidgetItem(["Gemeinsame Listen"])
            self.lists_item.setData(0, UD, {"listen_root": True})
            self.lists_item.setFlags(Qt.ItemFlag.ItemIsEnabled)   # nur Ordner, kein Filter
            self.lists_item.setForeground(0, QBrush(QColor(GREEN)))
            self.lists_item.setFont(0, font)
            self.lists_item.setToolTip(0, "Für alle Benutzer sichtbar · Rechtsklick: neue Liste")
            self.recent_item = QTreeWidgetItem([f"Zuletzt angesehen  ({len(self.recent)})"])
            self.recent_item.setData(0, UD, {"zuletzt": True})
            self.recent_item.setIcon(0, make_icon("history", MUTED, 16))
            self.recent_item.setToolTip(0, "Ihre zuletzt geöffneten Produkte (max. 20)")
            self.fav_item.setIcon(0, make_icon("star", GOLD, 16))
            self.lists_item.setIcon(0, make_icon("list", GREEN, 16))
            self.all_item.setIcon(0, make_icon("box", TEXT, 16))
            self.hier.addTopLevelItems([self.recent_item, self.fav_item, self.lists_item, self.all_item])

            self._add_nodes(self.all_item, nodes)
            self.all_item.setExpanded(True)
            self._fill_collections()
            target = self._item_for_key(prev) if prev else None
            self.hier.setCurrentItem(target or self.all_item)
            self.hier.scrollToItem(target or self.all_item)
        finally:
            self.hier.blockSignals(False)
        return prev != self._current_key()

    def _on_hier_filter(self):
        if self._load_hierarchy():
            self.apply_filter()

    def _add_nodes(self, parent, nodes):
        """Hierarchie-Knoten (mit Unterbaum) unter parent einhängen; gibt die obersten neuen Einträge zurück."""
        created = []
        for n in nodes:
            item = QTreeWidgetItem(parent, [f"{n['label']}  ({n['count']})"])
            item.setData(0, UD, n["key"])
            item.setToolTip(0, n["label"])
            self._add_nodes(item, n["children"])
            item.setExpanded(n.get("open", False))
            created.append(item)
        return created

    @staticmethod
    def _walk(item):
        for i in range(item.childCount()):
            child = item.child(i)
            yield child
            yield from MainWindow._walk(child)

    @staticmethod
    def _item_path(item):
        path = []
        while item is not None:
            path.append(_key_tuple(item.data(0, UD) or {}))
            item = item.parent()
        return tuple(reversed(path))

    def _fill_collections(self):
        """„Meine Favoriten“ (mit privaten Listen) und „Gemeinsame Listen“ aufbauen – verschachtelt, Gruppen als Baum."""
        self.lists = {r["id"]: r for r in queries.list_lists(self.conn)}
        store = self.store
        self.fav_item.takeChildren()
        self.fav_item.setText(0, f"{STAR} Meine Favoriten  ({self._count_label(store.favs)})")
        self._add_containers(self.fav_item, "pliste", None)
        self._add_group_entries(self.fav_item, ("fav", None), store.favs)
        self.lists_item.takeChildren()
        self.lists_item.setText(0, f"Gemeinsame Listen  ({len(self.lists)})")
        self._add_containers(self.lists_item, "liste", None)
        for item in (self.fav_item, self.lists_item):
            item.setExpanded(True)

    @staticmethod
    def _count_label(keys):
        n_p = sum(len(k) == 10 for k in keys)
        n_g = sum(len(k) < 10 for k in keys)
        return f"{n_p} Produkte" + (f", {n_g} Gruppe{'n' if n_g != 1 else ''}" if n_g else "")

    def _add_containers(self, parent_item, kind, parent_id):
        if kind == "pliste":
            rows = sorted(((lid, v["name"], v["items"]) for lid, v in self.store.plists.items() if v["parent"] == parent_id),
                          key=lambda r: r[1].casefold())
        else:
            rows = [(lid, r["name"], None) for lid, r in self.lists.items() if r["parent_id"] == parent_id]
        for lid, name, items in rows:
            if items is None:   # gemeinsame Liste: Einträge aus der DB
                groups = queries.list_groups(self.conn, lid)
                label = f"{self.lists[lid]['n']} Produkte" + (f", {len(groups)} Gruppe{'n' if len(groups) != 1 else ''}"
                                                             if groups else "")
                r = self.lists[lid]
                tip = (f"Gemeinsame Liste · angelegt von {r['created_by'] or '?'} am {fmt_date(r['created_at'])}"
                       f" · zuletzt geändert: {_who(r)}")
            else:
                groups = [k for k in items if len(k) < 10]
                label = self._count_label(items)
                tip = "Private Liste · nur für Sie sichtbar"
            item = QTreeWidgetItem(parent_item, [f"{name}  ({label})"])
            item.setData(0, UD, {kind: lid})
            if kind == "liste" and lid in self.store.abos:
                item.setIcon(0, make_icon("bell", GOLD, 14))
                tip += " · abonniert"
            item.setToolTip(0, tip + " · Rechtsklick: Unterliste, umbenennen, löschen")
            self._add_containers(item, kind, lid)
            self._add_group_entries(item, (kind, lid), groups)
            item.setExpanded(True)

    def _add_group_entries(self, parent_item, container, keys):
        """Als ganze Gruppe eingetragene Präfixe als aufklappbaren Hierarchie-Baum anzeigen."""
        for k in sorted(k for k in keys if len(k) < 10):
            node = self.node_by_key.get(_key_tuple(queries.key_from_prefix(k)))
            if node:
                item = self._add_nodes(parent_item, [dict(node, open=False)])[0]
                # volle Nummer voranstellen: „24 Atmungsorgane“ allein wäre ohne Produktgruppe mehrdeutig
                full = ".".join(part for part in (k[0:2], k[2:4], k[4:6], k[6:7]) if part)
                item.setText(0, f"{full} {node['label'].split(' ', 1)[-1]}  ({node['count']})")
            else:   # Gruppe gibt es im aktuellen Verzeichnis nicht (mehr)
                item = QTreeWidgetItem(parent_item, [f"{k} (nicht mehr im Verzeichnis)"])
                item.setData(0, UD, queries.key_from_prefix(k))
            item.setData(0, ENTRY_ROLE, (container, k))
            item.setForeground(0, QBrush(QColor(GREEN)))
            item.setToolTip(0, "Ganze Produktgruppe – neue Produkte der Gruppe gehören automatisch dazu")

    def _refresh_collections(self):
        """Favoriten/Listen neu aufbauen (auch Änderungen anderer Benutzer); Auswahl und Aufklappzustand bleiben."""
        current = self.hier.currentItem()
        cur_path = self._item_path(current) if current is not None else None
        roots = (self.fav_item, self.lists_item)
        in_collections = current is not None and self._item_path(current)[0] in {self._item_path(r)[0] for r in roots}
        state = {self._item_path(it): it.isExpanded() for r in roots for it in self._walk(r)}
        self._quiet(self.hier, self._fill_collections)
        found = None
        for r in roots:
            for it in self._walk(r):
                path = self._item_path(it)
                if path in state:
                    it.setExpanded(state[path])
                if path == cur_path:
                    found = it
        if in_collections:
            if found is None:   # Liste wurde (evtl. von jemand anderem) gelöscht
                self._select_tree(self.all_item)
            else:
                self._quiet(self.hier, self.hier.setCurrentItem, found)

    def changeEvent(self, event):
        if event.type() == QEvent.Type.ActivationChange and self.isActiveWindow() and self.store is not None:
            self._sync_with_others()
        super().changeEvent(event)

    def _sync_with_others(self):
        """Beim Zurückkehren ins Fenster Änderungen anderer Benutzer übernehmen (mehrere Personen, eine Datenbank)."""
        try:
            if queries.latest_import_id(self.conn) != self.latest_id:   # jemand hat eine neue Version importiert
                self.reload_all()
                self.statusBar().showMessage("Neue Version von einem anderen Benutzer importiert – Ansicht aktualisiert", 6000)
            else:
                self._refresh_collections()   # gemeinsame Listen anderer Benutzer
            self._update_activity_badge()
        except sqlite3.OperationalError:
            pass   # Datenbank gerade gesperrt (z. B. Import eines Kollegen) – beim nächsten Mal

    def _item_for_key(self, key):
        if key.get("zuletzt"):
            return self.recent_item
        if key.get("favoriten"):
            return self.fav_item
        if not key:
            return self.all_item
        root = self.fav_item if key.get("pliste") else self.lists_item if key.get("liste") else self.all_item
        return next((it for it in self._walk(root) if it.data(0, UD) == key), None)

    def _hersteller_text(self):
        text = self.cb_hersteller.currentText().strip()
        return "" if text == ALL_HERSTELLER else text

    def _read_filter(self):
        key = self._current_key() or {}
        self.filter = ProductFilter(
            text=self.search.text().strip(), in_merkmale=self.chk_merk.isChecked(),
            status=STATUS_CHOICES.get(self.cb_status.currentText(), "aktiv"),
            gruppe=key.get("gruppe"), ort=key.get("ort"), untergruppe=key.get("untergruppe"), art=key.get("art"),
            import_id=self.version_by_label.get(self.cb_version.currentText()),
            change_type=TYPE_CHOICES.get(self.cb_type.currentText()), favoriten=bool(key.get("favoriten")),
            liste_id=key.get("liste"), pliste_id=key.get("pliste"),
            nummern=tuple(self.recent) if key.get("zuletzt") else self.extra_nummern,
            hersteller=self._hersteller_text(), kategorie=self.cb_kat.currentData(),
            notiz_text=self.note_search.text().strip())

    def apply_filter(self):
        self.search_timer.stop()
        self._read_filter()
        self.refresh_list()

    @staticmethod
    def _quiet(widget, fn, *args):
        """fn ausführen, ohne dass die Signale von widget eine Neu-Filterung auslösen."""
        widget.blockSignals(True)
        try:
            fn(*args)
        finally:
            widget.blockSignals(False)

    def _on_tree_changed(self):
        self.extra_nummern = None   # eingefügte Nummernliste gilt nur bis zum nächsten Bereichswechsel
        self.apply_filter()

    def reset_filter(self):
        self.extra_nummern = None
        self._quiet(self.search, self.search.clear)
        self._quiet(self.note_search, self.note_search.clear)
        self._quiet(self.chk_merk, self.chk_merk.setChecked, False)
        self._quiet(self.cb_hersteller.lineEdit(), self.cb_hersteller.lineEdit().clear)
        self.cb_status.setCurrentIndex(0)
        self.cb_version.setCurrentIndex(0)
        self.cb_type.setCurrentIndex(0)
        self.cb_kat.setCurrentIndex(0)
        if self.hier_filter.text():
            self._quiet(self.hier_filter, self.hier_filter.clear)
            self._load_hierarchy()
        self._select_tree(self.all_item)

    def _select_tree(self, item):
        self._quiet(self.hier, self.hier.setCurrentItem, item)
        self.hier.scrollToItem(item)
        self.apply_filter()

    def _sort_by(self, col):
        key = PRODUCT_COLUMNS[col][3]
        if key is None:
            self._update_sort_indicator()
            return
        self.desc = (not self.desc) if self.order == key else (key == "fav")   # Favoriten zuerst
        self.order = key
        self.refresh_list()

    def _update_sort_indicator(self):
        col = next(i for i, c in enumerate(PRODUCT_COLUMNS) if c[3] == self.order)
        self.table.horizontalHeader().setSortIndicator(
            col, Qt.SortOrder.DescendingOrder if self.desc else Qt.SortOrder.AscendingOrder)

    def _maybe_load_more(self, value):
        bar = self.sender()
        if value >= bar.maximum() - 2 and len(self.loaded_rows) < self.total:
            self._load_more()

    def _status_text(self, p):
        if not p["active"]:
            return f"Entfernt in V{p['removed_import']}"
        if p["last_import_change"] == self.first_id and p["last_change_type"] == NEU:
            return "Erstimport"
        return f"{CHANGE_LABELS.get(p['last_change_type'], '')} in V{p['last_import_change']}"

    def _row_tag(self, p):
        if not p["active"]:
            return ENTFERNT
        if self.filter.import_id is not None:
            return None if self.filter.import_id == self.first_id else p["shown_type"]
        if p["last_import_change"] == self.latest_id and self.latest_id != self.first_id:
            return p["last_change_type"]
        return None

    def refresh_list(self):
        self.total = queries.count_products(self.conn, self.filter)
        self.loaded_rows = []
        self.row_nummer = []
        self.comment_info = queries.comment_summary(self.conn)
        self.table.blockSignals(True)
        self.table.clearSelection()
        self.table.setRowCount(0)
        self.table.blockSignals(False)
        self.cards.blockSignals(True)
        self.cards.clear()
        self.cards.blockSignals(False)
        self._load_more()
        self._update_sort_indicator()
        self._show_empty_state()
        fade_in(self.list_stack.currentWidget())
        summary = [f"{_dots(self.total)} Produkte"]
        item = self.hier.currentItem()
        if item and item is not self.all_item:
            summary.append(f"Bereich: {item.text(0)}")
        if self.extra_nummern is not None:
            summary.append(f"eingefügte Nummernliste ({len(self.extra_nummern)})")
        if self.filter.kategorie in self.store.categories:
            summary.append(f"Kategorie: {self.store.categories[self.filter.kategorie]['name']}")
        if self.filter.hersteller:
            summary.append(f"Hersteller: „{self.filter.hersteller}“")
        if self.filter.text:
            summary.append(f"Suche: „{self.filter.text}“")
        if self.filter.notiz_text:
            summary.append(f"Notiz enthält: „{self.filter.notiz_text}“")
        if self.filter.liste_id in self.lists:
            summary.append("zuletzt geändert: " + _who(self.lists[self.filter.liste_id]))
        self.statusBar().showMessage("  ·  ".join(summary))
        self.list_title.setText(item.text(0).split("  (")[0] if item else "Produkte")
        self._show_detail(None)

    def _load_more(self):
        """Nächsten Block laden (beim Scrollen ans Ende) – ersetzt die frühere Seitenaufteilung."""
        if len(self.loaded_rows) >= self.total and self.loaded_rows:
            return
        rows = queries.fetch_products(self.conn, self.filter, self.order, self.desc,
                                      limit=PAGE_SIZE, offset=len(self.loaded_rows))
        start = len(self.loaded_rows)
        self.loaded_rows += rows
        self.row_nummer += [r["nummer"] for r in rows]
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.loaded_rows))
        for i, row in enumerate(rows):
            self._fill_table_row(start + i, row)
        self.table.blockSignals(False)
        if self.view_mode == "karten":
            self._add_cards(rows)
        rest = self.total - len(self.loaded_rows)
        self.pager_label.setText(f"{_dots(self.total)} Treffer" + (
            f" · {_dots(len(self.loaded_rows))} geladen – weiter scrollen lädt mehr" if rest > 0 else ""))

    def _fill_table_row(self, r, p):
        nr = p["nummer"]
        notes = self.store.notes
        info = self.comment_info.get(nr)
        _fill_row(self.table, r, (
            self._star_for(nr), "", format_nummer(nr), p["bezeichnung"] or "",
            p["hersteller"] or "", _clean(notes.get(nr)), f"({info[0]}) {_clean(info[1]['text'])}" if info else "",
            self.names.path(p)["art"], fmt_date(p["aufnahmedatum"]),
            fmt_date(p["aenderungsdatum"]), self._status_text(p)), TAG_COLORS.get(self._row_tag(p)))
        self._paint_mark(r, nr)
        star = self.table.item(r, COL["fav"])
        star.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        star.setForeground(QBrush(QColor(GOLD)))
        star.setToolTip("Klicken: Favorit an/aus" + (" (☆ = über eine ganze Gruppe Favorit)" if star.text() == "☆" else ""))
        if p["merkmale"]:
            self.table.item(r, COL["bezeichnung"]).setToolTip(_tip(p["merkmale"][:700]))
        if info:
            self.table.item(r, COL["gnotiz"]).setToolTip(
                f"{info[0]} Kommentar(e), zuletzt {html.escape(info[1]['user'] or '?')}: " + _tip(info[1]["text"]))
        note = self.table.item(r, COL["notiz"])
        note.setForeground(QBrush(QColor(MUTED)))
        if nr in notes:
            note.setToolTip(_tip(notes[nr]))

    def _add_cards(self, rows):
        self.cards.blockSignals(True)
        for p in rows:
            nr = p["nummer"]
            tag = self._row_tag(p)
            chips = [(CHANGE_LABELS[tag], TAG_COLORS[tag])] if tag else []
            cat = self.store.categories.get(self.store.marks.get(nr))
            if cat:
                chips.append((cat["name"], MINT))
            info = self.comment_info.get(nr)
            comment = f"{info[1]['user'] or '?'}: {info[1]['text']}" if info else self.store.notes.get(nr, "")
            self.cards.add_card(nr, p["bezeichnung"] or "(ohne Bezeichnung)",
                                f"{format_nummer(nr)} · {p['hersteller'] or ''}", chips, _clean(comment)[:140],
                                self._star_for(nr), cat["farbe"] if cat else None)
        self.cards.blockSignals(False)

    def set_view_mode(self, mode):
        self.view_mode = mode
        self.settings.setValue("ansicht", mode)
        self.btn_cards.setChecked(mode == "karten")
        self.btn_table.setChecked(mode != "karten")
        if mode == "karten" and self.cards.count() != len(self.loaded_rows):
            self.cards.clear()
            self._add_cards(self.loaded_rows)
        self._show_empty_state()
        if self.current_nummer:
            self.cards.select_nummer(self.current_nummer)

    def _on_card_select(self, nummer):
        if nummer in self.row_nummer:
            self.table.selectRow(self.row_nummer.index(nummer))   # Tabelle bleibt die Quelle für Auswahl und Menüs

    def _card_menu(self, pos):
        item = self.cards.itemAt(pos)
        if item is None:
            return
        nummer = item.data(Qt.ItemDataRole.UserRole)
        self.table.selectRow(self.row_nummer.index(nummer))
        self._product_menu(None)

    def _column_menu(self, pos):
        hdr = self.table.horizontalHeader()
        menu = QMenu(self)
        for i, c in enumerate(PRODUCT_COLUMNS):
            if c[0] in ("nummer", "bezeichnung"):
                continue   # Pflichtspalten
            act = menu.addAction(c[1] or "Farbkategorie", lambda i=i: hdr.setSectionHidden(i, not hdr.isSectionHidden(i)))
            act.setCheckable(True)
            act.setChecked(not hdr.isSectionHidden(i))
        menu.addSeparator()
        menu.addAction("Standard wiederherstellen", self._reset_columns)
        menu.exec(hdr.mapToGlobal(pos))

    def _reset_columns(self):
        hdr = self.table.horizontalHeader()
        for i, c in enumerate(PRODUCT_COLUMNS):
            hdr.setSectionHidden(i, False)
            hdr.moveSection(hdr.visualIndex(i), i)
            if c[0] != "bezeichnung":
                self.table.setColumnWidth(i, c[2])

    def _show_empty_state(self):
        if self.total:
            self.list_stack.setCurrentWidget(self.cards if self.view_mode == "karten" else self.table)
            return
        icon = "search"
        if self.latest_id is None:
            icon = "import"
            text = (f"<p><b>Noch keine Daten vorhanden.</b></p><p><a href='import' style='color:{GREEN}'>"
                    "Jetzt HMV-XML oder ZIP importieren</a></p>")
        elif self.filter.favoriten and not self.filter.text and not self.filter.hersteller:
            icon = "star_outline"
            text = (f"<p><b>Noch keine Favoriten.</b></p><p>Klicken Sie in der Liste in die {STAR}-Spalte, "
                    "drücken Sie Strg+D oder ziehen Sie Produkte auf „Meine Favoriten“.</p>")
        elif self.filter.kategorie is not None and not self.filter.text:
            icon = "tag"
            text = ("<p><b>Noch keine Produkte mit dieser Kategorie.</b></p><p>Produkte markieren und per Rechtsklick "
                    "„Farbkategorie“ wählen oder rechts im Detailbereich eine Kategorie setzen.</p>")
        elif (self.filter.liste_id is not None or self.filter.pliste_id is not None) and not self.filter.text \
                and not self.filter.hersteller:
            icon = "list"
            text = ("<p><b>Diese Liste ist noch leer.</b></p><p>Produkte hierher ziehen oder markieren und per "
                    "Rechtsklick „Zu Liste hinzufügen …“ wählen.</p>")
        elif self.filter.nummern is not None and not self.recent and self.extra_nummern is None:
            icon = "history"
            text = "<p><b>Noch nichts angesehen.</b></p><p>Geöffnete Produkte erscheinen hier.</p>"
        else:
            text = (f"<p><b>Keine Treffer für diese Filter.</b></p><p><a href='reset' style='color:{GREEN}'>"
                    "Alle Filter zurücksetzen</a></p>")
        self.empty_icon.setPixmap(make_icon(icon, SCROLL_HOVER, 72).pixmap(72, 72))
        self.empty_text.setText(text)
        self.list_stack.setCurrentWidget(self.empty)

    # ------------------------------------------------------------------ Favoriten
    def _hier_menu(self, pos):
        item = self.hier.itemAt(pos)
        key = item.data(0, UD) if item else None
        if not key:   # „Alle Produkte“: zu groß für eine Liste
            return
        menu = QMenu(self)
        c = self._container_of_key(key)
        if key.get("listen_root"):
            menu.addAction("Neue gemeinsame Liste …", lambda: self._new_container(("liste", None)))
        elif c:
            kind, lid = c
            if kind == "fav":
                menu.addAction("Neue private Liste …", lambda: self._new_container(("pliste", None)))
            else:
                menu.addAction(make_icon("plus"), "Unterliste anlegen …", lambda: self._new_container(c))
                menu.addAction("Umbenennen …", lambda: self._rename_container(c))
                menu.addAction("Löschen …", lambda: self._delete_container(c))
                if kind == "liste":
                    menu.addSeparator()
                    menu.addAction(make_icon("history"), "Verlauf anzeigen …", lambda: self._show_list_log(lid))
                    menu.addAction(make_icon("bell"), "Abo beenden" if lid in self.store.abos
                                   else "Abonnieren (Hinweis bei Änderungen anderer)", lambda: self._toggle_abo(lid))
            entries = self._container_entries(c)
            if entries:
                menu.addSeparator()
                menu.addAction(f"Inhalt in andere Liste kopieren …  ({self._count_label(entries)})",
                               lambda: self._open_add_dialog(entries, f"Inhalt von „{self._container_name(c)}“"))
        else:   # Produktgruppe / Ort / Untergruppe / Art (auch innerhalb einer Liste)
            k = queries.favorite_key(key)
            entry = item.data(0, ENTRY_ROLE)
            if entry:
                ec, ek = entry
                menu.addAction(f"Aus „{self._container_name(tuple(ec))}“ entfernen",
                               lambda: self._container_remove(tuple(ec), [ek]))
                menu.addSeparator()
            menu.addAction(f"{STAR}  Ganze Gruppe aus Meine Favoriten entfernen" if k in self.store.favs
                           else "☆  Ganze Gruppe zu Meine Favoriten", lambda: self._toggle_fav(k))
            f = ProductFilter(status="aktiv", **{c2: key[c2] for c2 in ("gruppe", "ort", "untergruppe", "art") if c2 in key})
            n = queries.count_products(self.conn, f)
            menu.addAction("Zu Liste hinzufügen …  (ganze Gruppe oder einzelne Produkte)",
                           lambda: self._open_add_dialog(None, item.text(0).split("  (")[0], group=(k, f, n)))
        menu.exec(self.hier.viewport().mapToGlobal(pos))

    def _nummern_for(self, f, n):
        """Produktnummern zu einem Filter; bei sehr vielen Produkten vorher nachfragen."""
        if n > 500 and QMessageBox.question(
                self, "Viele Produkte", f"Wirklich {_dots(n)} Produkte zur Liste hinzufügen?") != QMessageBox.StandardButton.Yes:
            return []
        return [r["nummer"] for r in queries.iter_products(self.conn, f)]

    # ------------------------------------------------------------------ Gemeinsame Listen
    # ---- Listen allgemein: container = ("fav", None) | ("pliste", id) | ("liste", id)
    @staticmethod
    def _container_of_key(key):
        if key.get("favoriten"):
            return ("fav", None)
        if key.get("pliste"):
            return ("pliste", key["pliste"])
        if key.get("liste"):
            return ("liste", key["liste"])
        return None

    @staticmethod
    def _container_key(c):
        kind, lid = c
        return {"favoriten": True} if kind == "fav" else {kind: lid}

    def _container_name(self, c):
        kind, lid = c
        if kind == "fav":
            return "Meine Favoriten"
        if kind == "pliste":
            return self.store.plists.get(lid, {}).get("name", "?")
        return self.lists.get(lid, {"name": "?"})["name"]

    def _container_entries(self, c):
        kind, lid = c
        if kind == "fav":
            return list(self.store.favs)
        if kind == "pliste":
            return list(self.store.plists[lid]["items"])
        return [r[0] for r in self.conn.execute("SELECT nummer FROM liste_eintrag WHERE liste_id=?", (lid,))]

    def _current_container(self):
        return self._container_of_key(self._current_key() or {})

    def _ask_list_name(self, title, shared, text=""):
        hint = "für alle Benutzer sichtbar" if shared else "nur für Sie sichtbar"
        name, ok = QInputDialog.getText(self, title, f"Name der Liste ({hint}):", text=text)
        return name.strip() if ok and name.strip() else None

    def _list_db(self, fn, *args):
        """Schreibzugriff auf die gemeinsame DB mit verständlicher Fehlermeldung. None = fehlgeschlagen."""
        try:
            result = fn(self.conn, *args)
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Name bereits vergeben", "Es gibt schon eine Liste mit diesem Namen.")
            return None
        except sqlite3.OperationalError as exc:   # z. B. Datenbank gesperrt oder schreibgeschützt
            reason = ("Ein anderer Benutzer ändert gerade die Datenbank (z. B. ein Import). Bitte gleich erneut versuchen."
                      if "locked" in str(exc) else "Sie haben keine Schreibrechte auf die gemeinsame Datenbank."
                      if "readonly" in str(exc) or "read-only" in str(exc) else str(exc))
            QMessageBox.critical(self, "Speichern fehlgeschlagen", f"Die Änderung wurde nicht gespeichert.\n\n{reason}")
            return None
        return True if result is None else result

    def _new_container(self, parent_c, select=True, name=None):
        """Neue private oder gemeinsame (Unter-)Liste. parent_c: ("pliste"|"liste", Eltern-id oder None) oder ("fav", None)."""
        kind, parent = parent_c
        kind = "pliste" if kind == "fav" else kind
        where = f" in „{self._container_name((kind, parent))}“" if parent is not None else ""
        name = name or self._ask_list_name(f"Neue {'gemeinsame' if kind == 'liste' else 'private'} Liste{where}",
                                           kind == "liste")
        if not name:
            return None
        if kind == "pliste":
            try:
                lid = self._persist(self.store.create_plist, name, parent)
            except ValueError as exc:
                QMessageBox.warning(self, "Name bereits vergeben", str(exc))
                return None
        else:
            lid = self._list_db(queries.create_list, name, self.user, parent)
        if lid is None:
            return None
        self.store.attach(self.conn)
        self._refresh_collections()
        self.statusBar().showMessage(f"Liste „{name}“ angelegt" + (" – für alle sichtbar" if kind == "liste" else ""), 5000)
        if select:
            self._goto_page_widget(0)
            self._select_tree(self._item_for_key({kind: lid}))
        return (kind, lid)

    def _rename_container(self, c, name=None):
        kind, lid = c
        name = name or self._ask_list_name("Liste umbenennen", kind == "liste", self._container_name(c))
        if not name:
            return
        if kind == "pliste":
            try:
                ok = self._persist(self.store.rename_plist, lid, name)
            except ValueError as exc:
                QMessageBox.warning(self, "Name bereits vergeben", str(exc))
                return
        else:
            ok = self._list_db(queries.rename_list, lid, name, self.user)
        if ok:
            self._refresh_collections()

    def _delete_container(self, c):
        kind, lid = c
        name = self._container_name(c)
        who = (f"für ALLE Benutzer (angelegt von {self.lists[lid]['created_by'] or '?'})" if kind == "liste"
               else "(nur Ihre private Liste)")
        if QMessageBox.question(self, "Liste löschen", f"Liste „{name}“ samt Unterlisten löschen {who}?") \
                != QMessageBox.StandardButton.Yes:
            return
        ok = self._persist(self.store.delete_plist, lid) if kind == "pliste" else self._list_db(queries.delete_list, lid)
        if ok:
            self.store.attach(self.conn)
            self._refresh_collections()
            self.statusBar().showMessage(f"Liste „{name}“ gelöscht", 5000)

    def _open_add_dialog(self, keys, what, group=None):
        """Dialog „Zu Liste hinzufügen“. keys: feste Einträge; group: (Präfix, Filter, Anzahl) für eine Produktgruppe."""
        dlg = AddToListDialog(self, what, len(keys or []) if group is None else group[2], group is not None)
        if dlg.exec() != QDialog.DialogCode.Accepted or dlg.target is None:
            return
        self._last_target = dlg.target
        if group is not None:
            k, f, n = group
            keys = [k] if dlg.whole_group else self._nummern_for(f, n)
        self._container_add(dlg.target, keys)

    def _container_add(self, c, keys, record=True):
        if c is None or not keys:
            return
        kind, lid = c
        before = set(self._container_entries(c))
        if kind == "fav":
            n = self._persist(self.store.add, keys)
        elif kind == "pliste":
            n = self._persist(self.store.add_to_plist, lid, keys)
        else:
            n = self._list_db(queries.add_to_list, lid, keys, self.user)
        if n is None:
            return
        added = [k for k in dict.fromkeys(keys) if k not in before]
        self._after_list_change()
        skipped = len(keys) - n
        what = "Gruppe" if len(keys) == 1 and len(keys[0]) < 10 else f"{n} Eintrag/Einträge"
        msg = f"{what} zu „{self._container_name(c)}“ hinzugefügt" + (f" ({skipped} waren schon drin)" if skipped else "")
        if record and added:
            self._push_undo(msg, lambda: self._container_remove(c, added, record=False))
        else:
            self._toast(msg)

    def _container_remove(self, c, keys, record=True):
        kind, lid = c
        direct = set(self._container_entries(c))
        keys = [k for k in keys if k in direct]   # über eine Gruppe enthaltene Produkte lassen sich nicht einzeln entfernen
        if kind == "fav":
            for k in keys:
                self.store.favs.pop(k, None)
            n = None if self._persist(self.store.save) is None else len(keys)
        elif kind == "pliste":
            n = self._persist(self.store.remove_from_plist, lid, keys)
        else:
            n = self._list_db(queries.remove_from_list, lid, keys, self.user)
        if n is None:
            return
        self._after_list_change()
        msg = f"{n} Eintrag/Einträge aus „{self._container_name(c)}“ entfernt"
        if record and keys:
            self._push_undo(msg, lambda: self._container_add(c, keys, record=False))
        else:
            self._toast(msg)

    def _remove_selected_from_current(self, sel):
        c = self._current_container()
        direct = set(self._container_entries(c))
        via_group = [k for k in sel if k not in direct]
        self._container_remove(c, sel)
        if via_group:
            QMessageBox.information(self, "Über Gruppe enthalten",
                                    f"{len(via_group)} Produkt(e) gehören über eine ganze Produktgruppe zur Liste und "
                                    "wurden nicht entfernt. Entfernen Sie dafür die Gruppe (Rechtsklick links im Baum).")

    def _after_list_change(self):
        """Nach jeder Änderung an Favoriten/Listen: SQL-Tabellen, Baum, Sterne und ggf. die Liste aktualisieren."""
        self.store.attach(self.conn)
        self._refresh_collections()
        if self._current_container() is not None:
            self.refresh_list()
        else:
            for r, nr in enumerate(self.row_nummer):
                self.table.item(r, COL["fav"]).setText(self._star_for(nr))
            if self.current_nummer:
                self._show_detail(self.current_nummer)

    def _star_for(self, nr):
        if nr in self.store.favs:
            return STAR
        return "☆" if any(len(k) < 10 and nr.startswith(k) for k in self.store.favs) else ""

    # ------------------------------------------------------------------ Farbkategorien & Design
    def _fill_categories(self):
        for cb, first in ((self.cb_kat, "Alle Kategorien"), (self.cb_detail_kat, "– keine Kategorie –")):
            current = cb.currentData()
            cb.blockSignals(True)
            cb.clear()
            cb.addItem(first, None)
            for cid, c in self.store.categories.items():
                cb.addItem(color_icon(c["farbe"]), c["name"], cid)
            cb.setCurrentIndex(max(0, cb.findData(current)))
            cb.blockSignals(False)

    def _paint_mark(self, r, nr):
        item = self.table.item(r, COL["kat"])
        cat = self.store.categories.get(self.store.marks.get(nr))
        item.setIcon(color_icon(cat["farbe"]) if cat else QIcon())
        item.setToolTip(cat["name"] if cat else "")

    def _set_mark(self, nummern, cid, record=True):
        old = {k: self.store.marks.get(k) for k in nummern}
        if self._persist(self.store.set_mark, nummern, cid) is None:
            return
        if not self.read_only:   # für „Änderungen anderer“ bei den Kollegen; Fehler hier nie störend
            cat = self.store.categories.get(cid) if cid else None
            try:
                queries.log_activity(self.conn, self.user, "kategorie", nummern, cat["name"] if cat else "",
                                     cat["farbe"] if cat else None)
            except sqlite3.Error:
                pass
        self.store.attach(self.conn)
        for k in nummern:
            if k in self.row_nummer:
                self._paint_mark(self.row_nummer.index(k), k)
        name = self.store.categories[cid]["name"] if cid else "keine Kategorie"
        msg = f"{len(nummern)} Produkt(e): {name}"
        if record:
            def undo():
                groups = {}
                for k, v in old.items():
                    groups.setdefault(v if v in self.store.categories else None, []).append(k)
                for v, ks in groups.items():
                    self._set_mark(ks, v, record=False)
            self._push_undo(msg, undo)
        else:
            self._toast(msg)
        if self.filter.kategorie is not None:
            self.refresh_list()
        elif self.current_nummer in nummern:
            self._quiet(self.cb_detail_kat, self.cb_detail_kat.setCurrentIndex,
                        max(0, self.cb_detail_kat.findData(cid)))

    def _manage_categories(self):
        CategoryDialog(self).exec()
        self.store.attach(self.conn)
        self._fill_categories()
        self.refresh_list()

    def set_theme(self, name):
        self.settings.setValue("design", name)
        for n, act in self.design_actions.items():
            act.setChecked(n == name)
        self._restyle()

    def set_view(self, density=None, font_pt=None):
        if density:
            self.settings.setValue("dichte", density)
        if font_pt:
            self.settings.setValue("schrift", int(font_pt))
        apply_view(self.settings.value("dichte", "Normal"), self.settings.value("schrift", 10))
        for t in (self.table, self.ver_table, self.chg_table):
            t.verticalHeader().setDefaultSectionSize(ROW_H)
        self._restyle()
        self._toast("Ansicht geändert (Zeilenhöhe/Schriftgröße)")

    def _restyle(self):
        apply_theme(self.settings.value("design", "Classic"))
        self._apply_icons()
        for ctype, chip in self.chips.items():
            chip.setStyleSheet(f"background: {TAG_COLORS[ctype]}; color: {TEXT};")
        current = self.current_nummer
        self.reload_all()   # Inhalte mit den neuen Farben neu aufbauen (Baum, Liste, Details, Versionen)
        if current in self.row_nummer:
            self.table.selectRow(self.row_nummer.index(current))

    # ------------------------------------------------------------------ Benutzer
    def _ask_user(self, first=False):
        names = queries.list_users(self.conn)
        text = ("Bitte Ihren Nachnamen wählen oder neu eintippen (kein Passwort nötig).\n"
                "Er wird bei gemeinsamen Listen und Notizen als „zuletzt geändert von“ angezeigt.")
        name, ok = QInputDialog.getItem(self, "Benutzer anmelden" if first else "Benutzer wechseln / anlegen",
                                        text, names, max(0, names.index(self.user)) if self.user in names else 0, True)
        if ok and name.strip():
            return name
        return getpass.getuser() if first else None   # ohne Angabe: Windows-Anmeldename

    def _set_user(self, name):
        if not name:
            return
        try:
            stored = None if self.read_only else self._list_db(queries.create_user, name)
        except ValueError as exc:
            QMessageBox.warning(self, "Ungültiger Name", str(exc))
            return
        if stored is None:
            stored = name   # DB schreibgeschützt: Name trotzdem für diese Sitzung verwenden
        self.user = stored
        self.settings.setValue("benutzer", stored)
        self.user_btn.setText(f"{stored} ▾")
        self.statusBar().showMessage(f"Angemeldet als {stored}", 4000)

    def _fill_user_menu(self, menu):
        menu.clear()
        for name in queries.list_users(self.conn):
            act = menu.addAction(name, lambda name=name: self._set_user(name))
            act.setCheckable(True)
            act.setChecked(name == self.user)
        menu.addSeparator()
        menu.addAction("Neuen Benutzer anlegen / wechseln …", lambda: self._set_user(self._ask_user()))

    # ------------------------------------------------------------------ Sicherung der gemeinsamen Datenbank
    def _backup_db(self):
        self._save_note()
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M")
        path, _ = QFileDialog.getSaveFileName(self, "Datenbank sichern",
                                              str(Path(self.db_path).parent / f"HMV_Sicherung_{stamp}.db"),
                                              "SQLite-Datenbank (*.db)")
        if not path:
            return
        if Path(path).resolve() == Path(self.db_path).resolve():
            QMessageBox.warning(self, "Sicherung", "Bitte eine andere Datei als die laufende Datenbank wählen.")
            return
        try:
            Path(path).unlink(missing_ok=True)   # Überschreiben wurde im Dialog bestätigt
            queries.backup_db(self.conn, path)
        except (sqlite3.Error, OSError) as exc:
            QMessageBox.critical(self, "Sicherung fehlgeschlagen", f"{type(exc).__name__}: {exc}")
            return
        QMessageBox.information(self, "Sicherung erstellt",
                                f"Die gemeinsame Datenbank wurde gesichert:\n{path}\n\n"
                                "Enthalten: Verzeichnis, Versionen, gemeinsame Listen, gemeinsame Notizen, Benutzer.\n"
                                "Nicht enthalten: Ihre persönlichen Favoriten, privaten Listen, Notizen und Kategorien "
                                f"(Datei {self.store.path}).")

    def _restore_db(self):
        box = QMessageBox(QMessageBox.Icon.Critical, "ACHTUNG – Datenbank wiederherstellen",
                          "<p style='font-size:13pt'><b>ACHTUNG: DER IMPORT EINER SICHERUNG ÜBERSCHREIBT ALLE "
                          "INFORMATIONEN DER GEMEINSAMEN DATENBANK.</b></p>"
                          "<p>Verzeichnis, Versionen und Historie, gemeinsame Listen, gemeinsame Notizen und Benutzer "
                          "werden durch den Stand der Sicherung ersetzt – <b>für ALLE Benutzer</b>.</p>"
                          "<p><b>Dies soll NUR IM NOTFALL geschehen</b> (z. B. wenn die Datenbank beschädigt ist). "
                          "Andere Benutzer sollten das Programm vorher schließen.</p>"
                          "<p>Der aktuelle Stand wird vorher automatisch gesichert.</p>", parent=self)
        go = box.addButton("Weiter – Sicherung auswählen …", QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton("Abbrechen", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel)
        box.exec()
        if box.clickedButton() is not go:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Sicherung auswählen (NUR IM NOTFALL)", str(Path(self.db_path).parent),
                                              "SQLite-Datenbank (*.db);;Alle Dateien (*.*)")
        if not path:
            return
        if Path(path).resolve() == Path(self.db_path).resolve():
            QMessageBox.warning(self, "Wiederherstellen", "Das ist die laufende Datenbank selbst.")
            return
        try:
            info = queries.check_backup(path)
        except ValueError as exc:
            QMessageBox.critical(self, "Ungültige Sicherung", str(exc))
            return
        word, ok = QInputDialog.getText(
            self, "Letzte Bestätigung",
            f"Sicherung: {path}\n({info['versionen']} Versionen, {_dots(info['produkte'])} Produkte, "
            f"{info['listen']} gemeinsame Listen)\n\n"
            "ALLE INFORMATIONEN der gemeinsamen Datenbank werden überschrieben.\n"
            "Zur Bestätigung bitte ÜBERSCHREIBEN eintippen:")
        if not ok or word.strip() != "ÜBERSCHREIBEN":
            QMessageBox.information(self, "Abgebrochen", "Es wurde nichts verändert.")
            return
        self._save_note()
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        safety = Path(self.db_path).parent / "sicherungen" / f"vor_wiederherstellung_{stamp}.db"
        try:
            safety.parent.mkdir(parents=True, exist_ok=True)
            queries.backup_db(self.conn, safety)   # ohne diese Sicherung wird nichts überschrieben
            queries.restore_db(self.conn, path)
            db.ensure_schema(self.conn)            # ältere Sicherungen auf den aktuellen Stand bringen
        except (sqlite3.Error, OSError, ValueError) as exc:
            QMessageBox.critical(self, "Wiederherstellung fehlgeschlagen",
                                 f"{type(exc).__name__}: {exc}\n\nSicherung des vorherigen Stands: {safety}")
            return
        self._set_user(self.user)
        self.reload_all()
        QMessageBox.information(self, "Wiederhergestellt",
                                f"Die Datenbank wurde aus der Sicherung wiederhergestellt.\n\n"
                                f"Der vorherige Stand wurde gesichert unter:\n{safety}")

    # ------------------------------------------------------------------ Rückgängig & Hinweise
    def _toast(self, text, action_text=None, action=None):
        self.toast.show_message(text, action_text, action)

    def _push_undo(self, label, fn):
        self._undo.append((label, fn))
        del self._undo[:-30]
        self._toast(label, "Rückgängig", self._undo_last)

    def _undo_last(self):
        focus = QApplication.focusWidget()
        if isinstance(focus, (QLineEdit, QPlainTextEdit)):   # in Textfeldern bleibt Strg+Z die normale Text-Rückgängig-Funktion
            focus.undo()
            return
        if not self._undo:
            self._toast("Nichts zum Rückgängigmachen")
            return
        label, fn = self._undo.pop()
        fn()
        self._toast(f"Rückgängig: {label}")

    # ------------------------------------------------------------------ Schnellzugriff (Strg+K)
    def open_palette(self):
        CommandPalette(self, self._palette_items).exec()

    def _palette_items(self, text):
        term = text.casefold()
        actions = [("search", "Produkte durchsuchen", "Strg+F", lambda: (self._goto_page_widget(0), self.search.setFocus())),
                   ("home", "Startseite", "Strg+0", lambda: self._goto_page_widget(2)),
                   ("star", "Meine Favoriten", "Strg+B", self.show_favorites),
                   ("history", "Zuletzt angesehen", "", lambda: (self._goto_page_widget(0), self._select_tree(self.recent_item))),
                   ("paste", "Nummernliste einfügen", "Strg+Umschalt+V", self._paste_numbers),
                   ("import", "Importieren", "Strg+I", self.start_import),
                   ("export", "Excel-Export", "Strg+E", self.start_export),
                   ("plus", "Neue private Liste", "", lambda: self._new_container(("pliste", None))),
                   ("plus", "Neue gemeinsame Liste", "", lambda: self._new_container(("liste", None))),
                   ("bell", "Was ist neu?", "", lambda: self._show_whats_new(auto=False)),
                   ("tag", "Farbkategorien verwalten", "", self._manage_categories),
                   ("save", "Datenbank sichern", "", self._backup_db),
                   ("info", "Info & Support", "", self._show_info),
                   ("history", "Versionen & Änderungen", "Strg+2", lambda: self._goto_page_widget(1))]
        actions += [("menu", f"Design: {n}", "", lambda n=n: self.set_theme(n)) for n in THEME_NAMES]
        out = [(make_icon(i, GREEN), t, sub, fn) for i, t, sub, fn in actions if not term or term in t.casefold()]
        if not term:
            out += [(make_icon("history", MUTED), format_nummer(nr), "zuletzt angesehen",
                     lambda nr=nr: self._open_product(nr)) for nr in self.recent[:8]]
            return out
        for r in queries.fetch_products(self.conn, ProductFilter(text=text, status="alle"), limit=15):
            out.append((make_icon("box", TEXT), f"{format_nummer(r['nummer'])}  {r['bezeichnung'] or ''}",
                        r["hersteller"] or "", lambda nr=r["nummer"]: self._open_product(nr)))
        groups = [n for n in self.node_by_key.values() if term in n["label"].casefold()][:10]
        for n in groups:
            out.append((make_icon("list", MUTED), n["label"], "Produktgruppe",
                        lambda key=n["key"]: (self._goto_page_widget(0), self._select_tree(self._item_for_key(key)))))
        for lid, v in self.store.plists.items():
            if term in v["name"].casefold():
                out.append((make_icon("star_outline", GOLD), v["name"], "meine Liste",
                            lambda lid=lid: self._on_detail_link(f"pliste:{lid}")))
        for lid, r in self.lists.items():
            if term in r["name"].casefold():
                out.append((make_icon("list", GREEN), r["name"], "gemeinsame Liste",
                            lambda lid=lid: self._on_detail_link(f"liste:{lid}")))
        return out

    def _open_product(self, nummer):
        """Produkt direkt öffnen: Filter auf diese Nummer, Zeile auswählen."""
        self._goto_page_widget(0)
        self.extra_nummern = (nummer,)
        self._quiet(self.search, self.search.clear)
        self.cb_status.setCurrentText("Alle")
        self._quiet(self.hier, self.hier.setCurrentItem, self.all_item)
        self.apply_filter()
        if self.row_nummer:
            self.table.selectRow(0)

    # ------------------------------------------------------------------ Nummernliste, Vergleich
    def _paste_numbers(self):
        def lookup(nums):
            found = {r["nummer"]: r["active"] for r in self.conn.execute(
                "SELECT nummer, active FROM produkt WHERE nummer IN (SELECT value FROM json_each(?))", (json.dumps(nums),))}
            return ([n for n in nums if found.get(n) == 1], [n for n in nums if found.get(n) == 0],
                    [n for n in nums if n not in found])
        dlg = PasteNumbersDialog(self, lookup)
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.result:
            return
        mode, found = dlg.result
        if mode == "add":
            self._open_add_dialog(found, f"{len(found)} eingefügte Nummern")
            return
        self._goto_page_widget(0)
        self.cb_status.setCurrentText("Alle")
        self._quiet(self.search, self.search.clear)
        self._quiet(self.hier, self.hier.setCurrentItem, self.all_item)
        self.extra_nummern = tuple(found)
        self.apply_filter()
        self._toast(f"{len(found)} Produkte aus der eingefügten Liste – „Filter zurücksetzen“ hebt das auf")

    def _compare_rows(self, nummern):
        prods = []
        for nr in nummern:
            row = dict(queries.get_product(self.conn, nr))
            row.update(nummer_fmt=format_nummer(nr), aufnahme=fmt_date(row["aufnahmedatum"]),
                       status=self._status_text(row))
            prods.append(row)
        return prods

    def _compare(self, nummern):
        CompareDialog(self, self._compare_rows(nummern), self.names,
                      on_add=lambda have: self._compare_rows(self._pick_compare(have))).exec()

    def _compare_with(self, nummer):
        """Rechtsklick „Vergleichen mit …“: zweites (bis viertes) Produkt in einem Popup auswählen."""
        picked = self._pick_compare([nummer])
        if picked:
            self._compare([nummer] + picked)

    def _pick_compare(self, have):
        base = queries.get_product(self.conn, have[0])
        label = f"{format_nummer(have[0])} {base['bezeichnung'] or ''}"

        def entries(rows):
            return [(r["nummer"], f"{format_nummer(r['nummer'])}  {r['bezeichnung'] or ''}  ·  {r['hersteller'] or ''}")
                    for r in rows if r["nummer"] not in have]

        def search(text):
            return entries(queries.fetch_products(self.conn, ProductFilter(text=text, status="alle"), limit=80))

        def same_art():
            f = ProductFilter(status="aktiv", gruppe=base["gruppe"], ort=base["ort"], untergruppe=base["untergruppe"],
                              art=base["art"])
            rows = queries.fetch_products(self.conn, f, limit=300)
            return entries([r for r in rows if (r["bezeichnung"] or "").strip() != "Nicht besetzt"])   # HMV-Platzhalter

        dlg = ProductPicker(self, label, search, same_art, max_sel=max(1, 4 - len(have)))
        return dlg.result if dlg.exec() == QDialog.DialogCode.Accepted else []

    # ------------------------------------------------------------------ gespeicherte Suchen
    def _search_state(self):
        return {"text": self.search.text(), "notiz": self.note_search.text(), "merk": self.chk_merk.isChecked(),
                "status": self.cb_status.currentText(), "version": self.cb_version.currentText(),
                "typ": self.cb_type.currentText(), "hersteller": self._hersteller_text(),
                "kategorie": self.cb_kat.currentData(), "bereich": self._current_key() or {}}

    def _apply_search_state(self, st):
        self._goto_page_widget(0)
        self.extra_nummern = None
        self._quiet(self.search, self.search.setText, st.get("text", ""))
        self._quiet(self.note_search, self.note_search.setText, st.get("notiz", ""))
        self._quiet(self.chk_merk, self.chk_merk.setChecked, bool(st.get("merk")))
        self.cb_status.setCurrentText(st.get("status", "Nur aktive"))
        self.cb_version.setCurrentText(st.get("version", ALL_VERSIONS))
        self.cb_type.setCurrentText(st.get("typ", "Alle Änderungstypen"))
        self._quiet(self.cb_hersteller.lineEdit(), self.cb_hersteller.setEditText, st.get("hersteller", ""))
        self.cb_kat.setCurrentIndex(max(0, self.cb_kat.findData(st.get("kategorie"))))
        item = self._item_for_key(st.get("bereich") or {}) or self.all_item
        self._quiet(self.hier, self.hier.setCurrentItem, item)
        self.hier.scrollToItem(item)
        self.apply_filter()

    def _fill_saved_menu(self, menu):
        menu.clear()
        for name in sorted(self.store.searches, key=str.casefold):
            menu.addAction(make_icon("search", GREEN), name, lambda name=name: self._apply_search_state(self.store.searches[name]))
        if self.store.searches:
            menu.addSeparator()
        menu.addAction(make_icon("plus"), "Aktuelle Suche speichern …", self._save_search)
        if self.store.searches:
            sub = menu.addMenu("Löschen")
            for name in sorted(self.store.searches, key=str.casefold):
                sub.addAction(name, lambda name=name: self._persist(self.store.delete_search, name))

    def _save_search(self):
        name, ok = QInputDialog.getText(self, "Suche speichern", "Name der Suche (nur für Sie):")
        if ok and name.strip():
            try:
                if self._persist(self.store.save_search, name, self._search_state()) is not None:
                    self._toast(f"Suche „{name.strip()}“ gespeichert")
            except ValueError as exc:
                QMessageBox.warning(self, "Suche speichern", str(exc))

    # ------------------------------------------------------------------ gemeinsame Listen: Verlauf, Abo
    def _show_list_log(self, lid):
        rows = queries.list_log(self.conn, lid)
        body = "".join(f"<tr><td style='color:{MUTED}'>{_when(r['at'])}</td><td><b>{html.escape(r['user'] or '?')}</b></td>"
                       f"<td>{html.escape(r['aktion'])}</td><td>{html.escape(r['detail'] or '')}</td></tr>" for r in rows)
        TextDialog(self, f"Verlauf: {self.lists[lid]['name']}",
                   f"<table cellpadding='5' width='100%'>{body or '<tr><td>Noch keine Einträge.</td></tr>'}</table>").exec()

    def _toggle_abo(self, lid):
        on = self._persist(self.store.toggle_abo, lid)
        if on is None:
            return
        self._refresh_collections()
        self._toast(f"„{self.lists[lid]['name']}“ " + ("abonniert – Sie werden beim Start über Änderungen informiert"
                                                    if lid in self.store.abos else "nicht mehr abonniert"))

    # ------------------------------------------------------------------ Was ist neu?
    def _show_whats_new(self, auto):
        since = self._last_open or "0000"
        parts = []
        imports = queries.imports_since(self.conn, since)
        if imports:
            items = []
            for imp in imports:
                n_fav = queries.count_products(self.conn, ProductFilter(status="alle", favoriten=True, import_id=imp["id"]))
                items.append(f"V{imp['id']} vom {_when(imp['imported_at'])}: {imp['n_new']} neu, {imp['n_changed']} geändert, "
                             f"{imp['n_removed']} entfernt" + (f" – <a href='favoriten'>{n_fav} Ihrer Favoriten betroffen</a>"
                                                               if n_fav else ""))
            parts.append(("Neue Importe", items))
        changed = [r for lid, r in self.lists.items() if lid in self.store.abos and (r["changed_at"] or "") > since
                   and (r["changed_by"] or "") != (self.user or "")]
        if changed:
            parts.append(("Abonnierte Listen geändert", [
                f"<a href='liste:{r['id']}'>{html.escape(r['name'])}</a> – {html.escape(_who(r))}" for r in changed]))
        marks = queries.others_activity(self.conn, self.user, since, "kategorie", limit=25)
        if marks:
            parts.append(("Neue Farbmarkierungen anderer", [
                f"<a href='produkt:{a['nummer']}'>{format_nummer(a['nummer'])}</a> – <b>{html.escape(a['user'] or '?')}</b> "
                f"({_when(a['at'])}): {html.escape(a['detail'] or 'Markierung entfernt')}" for a in marks]))
        comments = queries.comments_since(self.conn, since, self.user)[:25]
        if comments:
            parts.append(("Neue Kommentare", [
                f"<a href='produkt:{c['nummer']}'>{format_nummer(c['nummer'])}</a> – <b>{html.escape(c['user'] or '?')}</b> "
                f"({_when(c['at'])}): {html.escape(c['text'][:160])}" for c in comments]))
        if not parts:
            if not auto:
                QMessageBox.information(self, "Was ist neu?", f"Seit {_when(since) or 'dem letzten Start'} gibt es nichts Neues.")
            return
        text = f"<h2>Was ist neu seit {_when(since)}?</h2>" + "".join(
            f"<h3 style='color:{GREEN}'>{title}</h3><ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"
            for title, items in parts)
        TextDialog(self, "Was ist neu?", text, on_link=self._whats_new_link).exec()

    def _whats_new_link(self, target):
        if target == "favoriten":
            self.show_favorites()
        elif target.startswith("produkt:"):
            self._open_product(target.split(":", 1)[1])
        else:
            self._goto_page_widget(0)
            self._on_detail_link(target)

    # ------------------------------------------------------------------ Startseite
    def refresh_dashboard(self):
        if self.store is None or self.names is None:
            return
        hour = dt.datetime.now().hour
        greet = "Guten Morgen" if hour < 11 else "Guten Tag" if hour < 18 else "Guten Abend"
        self.greeting.setText(f"{greet}, {self.user}")
        total = queries.count_products(self.conn, ProductFilter(status="aktiv"))
        self.tile_products.value.setText(_dots(total))
        self.tile_products.sub.setText(f"{len(self.hier_data)} Produktgruppen")
        versions = queries.list_versions(self.conn)
        if versions:
            v = versions[0]
            self.tile_import.value.setText(f"V{v['id']}")
            self.tile_import.sub.setText(f"{_when(v['imported_at'])} · {v['n_new']} neu, {v['n_changed']} geändert, "
                                         f"{v['n_removed']} entfernt")
        else:
            self.tile_import.value.setText("–")
            self.tile_import.sub.setText("Noch kein Import")
        n_fav = queries.count_products(self.conn, ProductFilter(status="aktiv", favoriten=True))
        self.tile_favs.value.setText(_dots(n_fav))
        self.tile_favs.sub.setText(f"{len(self.store.plists)} private Listen · {self._count_label(self.store.favs)} gemerkt")
        self.tile_lists.value.setText(str(len(self.lists)))
        self.tile_lists.sub.setText(f"{len(self.store.abos)} abonniert")
        chart = []
        for v in reversed(versions[:12]):
            if v["id"] == self.first_id:
                continue
            chart.append((f"V{v['id']}", {NEU: v["n_new"], GEAENDERT: v["n_changed"], ENTFERNT: v["n_removed"],
                                          REAKTIVIERT: v["n_reactivated"]}))
        self.chart.set_data(chart)
        recent = []
        for nr in self.recent[:8]:
            p = queries.get_product(self.conn, nr)
            if p:
                recent.append((make_icon("box", MUTED), f"{format_nummer(nr)}  {p['bezeichnung'] or ''}",
                               lambda nr=nr: self._open_product(nr)))
        self.dash_recent.set_items(recent, "Noch keine Produkte angesehen.")
        self.dash_lists.set_items(
            [(make_icon("bell" if r["id"] in self.store.abos else "list", GREEN), f"{r['name']}  ·  {_who(r)}",
              lambda lid=r["id"]: (self._goto_page_widget(0), self._on_detail_link(f"liste:{lid}")))
             for r in queries.recent_lists(self.conn)], "Noch keine gemeinsamen Listen.")

    # ------------------------------------------------------------------ automatische Sicherung, Info
    def _auto_backup(self, sync=False):
        """Täglich eine Sicherung der gemeinsamen DB in data/sicherungen (die letzten 14 bleiben)."""
        if self.read_only:
            return None
        folder = Path(self.db_path).parent / "sicherungen"
        target = folder / f"auto_{dt.date.today():%Y%m%d}.db"
        if target.exists():
            return None

        def job():
            folder.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(f".tmp{os.getpid()}")
            src = sqlite3.connect(self.db_path, timeout=60)
            try:
                queries.backup_db(src, tmp)
            finally:
                src.close()
            if target.exists():          # ein Kollege war schneller
                tmp.unlink(missing_ok=True)
            else:
                os.replace(tmp, target)
            for old in sorted(folder.glob("auto_*.db"))[:-14]:
                old.unlink(missing_ok=True)
            return target

        if sync:
            return job()
        w = self._backup_worker = Worker()
        w.done.connect(lambda t: t and self.statusBar().showMessage(f"Automatische Tagessicherung erstellt: {t}", 6000))
        w.failed.connect(lambda exc: self.statusBar().showMessage(f"Automatische Sicherung nicht möglich: {exc}", 8000))

        def run():
            try:
                w.done.emit(job())
            except Exception as exc:  # noqa: BLE001 - nur Hinweis, nie ein Absturz
                w.failed.emit(exc)

        threading.Thread(target=run, daemon=True).start()
        return None

    def _show_info(self):
        import platform
        import PySide6
        from PySide6.QtCore import qVersion
        mode = self.conn.execute("PRAGMA journal_mode").fetchone()[0]
        rows = [("Version", f"HMV-Viewer {__version__}"), ("Benutzer", f"{self.user} (Windows: {getpass.getuser()})"),
                ("Datenbank", self.db_path), ("Schreibrecht", "nein – nur lesen" if self.read_only else "ja"),
                ("Journal-Modus", mode), ("Favoriten-Datei", str(self.store.path)),
                ("Sicherungen", str(Path(self.db_path).parent / "sicherungen")),
                ("Python", f"{platform.python_version()} ({platform.system()} {platform.release()})"),
                ("Qt / PySide6", f"{qVersion()} / {PySide6.__version__}"), ("SQLite", sqlite3.sqlite_version)]
        log = Path(self.db_path).parent / f"fehler_{getpass.getuser()}.log"

        def copy_report(dlg):
            text = "\n".join(f"{k}: {v}" for k, v in rows)
            if log.exists():
                text += "\n\nLetzter Fehler:\n" + "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-40:])
            QApplication.clipboard().setText(text)
            self._toast("Fehlerbericht kopiert – z. B. in eine E-Mail an den Support einfügen")

        TextDialog(self, "Info & Support", "<h2>HMV-Viewer</h2>" + grid_html([(k, html.escape(str(v))) for k, v in rows]),
                   buttons=[("Fehlerbericht kopieren", copy_report, True)], size=(760, 480)).exec()

    def show_favorites(self):
        self._goto_page_widget(0)
        self._select_tree(self.fav_item)

    def _selected_nummern(self):
        rows = sorted(i.row() for i in self.table.selectionModel().selectedRows())
        return [self.row_nummer[r] for r in rows]

    def _toggle_selected_fav(self):
        sel = self._selected_nummern()
        if len(sel) == 1:
            self._toggle_fav(sel[0])
        elif sel:
            self._add_favs(sel)

    def _after_fav_change(self, message):
        self._after_list_change()
        self._toast(message)

    def _toggle_fav(self, k, record=True):
        if self._persist(self.store.toggle, k) is None:
            return
        added = k in self.store.favs
        if len(k) == 10:
            name = format_nummer(k)
        else:
            node = self.node_by_key.get(_key_tuple(queries.key_from_prefix(k)))
            name = (node["label"] if node else k) + " (ganze Gruppe)"
        msg = f"{name} {'als Favorit gemerkt' if added else 'aus den Favoriten entfernt'}"
        self._after_list_change()
        if record:
            self._push_undo(msg, lambda: self._toggle_fav(k, record=False))
        else:
            self._toast(msg)

    def _add_favs(self, nummern):
        self._container_add(("fav", None), nummern)

    def _remove_favs(self, nummern):
        self._container_remove(("fav", None), nummern)

    def _on_detail_link(self, target):
        if target.startswith("produkt:"):
            self._open_product(target.split(":", 1)[1])
            return
        if target.startswith(("liste:", "pliste:")):
            kind, lid = target.split(":", 1)
            item = self._item_for_key({kind: int(lid) if kind == "liste" else lid})
            if item is not None:
                self._quiet(self.search, self.search.clear)
                self._select_tree(item)
            return
        if target == "hersteller":
            p = queries.get_product(self.conn, self.current_nummer) if self.current_nummer else None
            if p and p["hersteller"]:
                self._quiet(self.search, self.search.clear)
                self._quiet(self.cb_hersteller.lineEdit(), self.cb_hersteller.setEditText, p["hersteller"])
                self._select_tree(self.all_item)
            return
        self._reveal_level(target)

    def _reveal_level(self, level):
        key = self.current_keys.get(level)
        if key is None:
            return
        item = self._item_for_key(key)
        if item is None and self.hier_filter.text():
            self._quiet(self.hier_filter, self.hier_filter.clear)
            self._load_hierarchy()
            item = self._item_for_key(key)
        if item is None:
            return
        self._quiet(self.search, self.search.clear)
        self._select_tree(item)

    # ------------------------------------------------------------------ Details & Notizen
    def _on_product_select(self):
        sel = self._selected_nummern()
        row = self.table.currentRow()
        current = self.row_nummer[row] if 0 <= row < len(self.row_nummer) else None
        nummer = current if current in sel else (sel[0] if sel else None)
        if len(sel) > 1:
            self.statusBar().showMessage(f"{len(sel)} Zeilen markiert – Strg+C kopiert sie als Tabelle, "
                                         "Rechtsklick für Listen und Vergleich", 5000)
        if nummer != self.current_nummer:
            self._show_detail(nummer)
            if nummer and self.view_mode == "karten":
                self._quiet(self.cards, self.cards.select_nummer, nummer)

    def _edit_note(self):
        if self.current_nummer:
            self._goto_page_widget(0)
            self.note_edit.setFocus()

    def _save_note(self):
        self.note_timer.stop()
        k = self.note_nummer
        if k is None or self.store is None:
            return
        text = self.note_edit.toPlainText().strip()
        if text == self.store.notes.get(k, ""):
            return
        if self._persist(self.store.set_note, k, text) is None:
            return
        if k in self.row_nummer:
            item = self.table.item(self.row_nummer.index(k), COL["notiz"])
            item.setText(_clean(text))
            item.setToolTip(_tip(text))
        self.statusBar().showMessage(f"Notiz zu {format_nummer(k)} gespeichert", 3000)

    def _show_detail(self, nummer):
        self._save_note()
        self.current_nummer, self.current_keys = nummer, {}
        self.note_nummer = nummer
        self._quiet(self.note_edit, self.note_edit.setPlainText, self.store.notes.get(nummer, "") if nummer else "")
        self.note_edit.setEnabled(bool(nummer))
        self.hist_tree.clear()
        self.hist_rows = []
        self.hist_text.clear()
        self.btn_fav.setEnabled(bool(nummer))
        self.btn_copy.setEnabled(bool(nummer))
        is_fav = nummer in self.store.favs
        self.btn_fav.setText("Favorit entfernen" if is_fav else "Merken")
        self.btn_fav.setIcon(make_icon("star" if is_fav else "star_outline", GOLD))
        self.cb_detail_kat.setEnabled(bool(nummer))
        self.cb_detail_kat.setCurrentIndex(max(0, self.cb_detail_kat.findData(self.store.marks.get(nummer))))
        while self.detail_chips.count():
            w = self.detail_chips.takeAt(0).widget()
            if w:
                w.hide()              # sofort weg, nicht erst beim nächsten Durchlauf der Ereignisschleife
                w.setParent(None)
                w.deleteLater()
        p = queries.get_product(self.conn, nummer) if nummer else None
        self.comments.setEnabled(p is not None)
        if p is None:
            self.detail_title.setText("")
            for sec in (self.sec_info, self.sec_merk, self.sec_lists):
                sec.set_html("")
            self.detail_hint.setText("Produkt in der Liste auswählen, um Details, Kommentare, Historie und "
                                     "Ihre Notiz zu sehen.")
            self.comments.set_comments([], self.user, _when)
            self.detail_tabs.setTabText(1, "Kommentare")
            return
        self._remember_recent(nummer)
        path = self.names.path(p)
        g, o, u, a = p["gruppe"], p["ort"], p["untergruppe"], p["art"]
        self.current_keys = {"gruppe": {"gruppe": g}, "ort": {"gruppe": g, "ort": o},
                             "untergruppe": {"gruppe": g, "ort": o, "untergruppe": u},
                             "art": {"gruppe": g, "ort": o, "untergruppe": u, "art": a}}
        esc = html.escape

        def link(target, text):
            return f"<a href='goto:{target}' style='color:{GREEN}'>{esc(text)}</a>"

        self.detail_title.setText(p["bezeichnung"] or "(ohne Bezeichnung)")
        tag = self._row_tag(p)
        chips = [("aktiv" if p["active"] else "entfernt", MINT if p["active"] else TAG_COLORS[ENTFERNT])]
        if tag:
            chips.append((CHANGE_LABELS[tag], TAG_COLORS[tag]))
        cat = self.store.categories.get(self.store.marks.get(nummer))
        if cat:
            chips.append((cat["name"], cat["farbe"]))
        if is_fav or self._star_for(nummer):
            chips.append(("Favorit" if is_fav else "Favorit (Gruppe)", MINT))
        for text, color in chips:
            ch = QLabel(text, objectName="chip", textFormat=Qt.TextFormat.PlainText)
            ch.setStyleSheet(f"background: {color}; color: {TEXT if color != cat_color(cat) else '#FFFFFF'};")
            self.detail_chips.addWidget(ch)
        self.detail_chips.addStretch(1)
        self.sec_info.set_html(grid_html([
            ("Hilfsmittelnummer", f"<b>{format_nummer(p['nummer'])}</b> <span style='color:{MUTED}'>({p['nummer']})</span>"),
            ("Hersteller", link("hersteller", p["hersteller"]) if p["hersteller"] else ""),
            ("Produktgruppe", link("gruppe", path["gruppe"])), ("Anwendungsort", link("ort", path["ort"])),
            ("Untergruppe", link("untergruppe", path["untergruppe"])), ("Produktart", link("art", path["art"])),
            ("Aufnahme", fmt_date(p["aufnahmedatum"])), ("Änderung (HMV)", fmt_date(p["aenderungsdatum"]) or "–"),
            ("Status", esc(self._status_text(p)))]))
        self.sec_merk.set_html(esc(p["merkmale"] or "–").replace("\n", "<br>"))
        in_lists = queries.lists_for_product(self.conn, nummer)
        mine = [(lid, v["name"]) for lid, v in self.store.plists.items()
                if nummer in v["items"] or any(len(k) < 10 and nummer.startswith(k) for k in v["items"])]
        rows = []
        if in_lists:
            rows.append(("Gemeinsam", ", ".join(link(f"liste:{r['id']}", r["name"]) for r in in_lists)))
        if mine:
            rows.append(("Meine", ", ".join(link(f"pliste:{lid}", name) for lid, name in mine)))
        self.sec_lists.set_html(grid_html(rows) if rows else "")
        self.detail_hint.setText("Grüne Links anklicken = Liste danach filtern")
        comments = queries.comments_for(self.conn, nummer)
        self.comments.set_comments(comments, self.user, _when)
        self.detail_tabs.setTabText(1, f"Kommentare ({len(comments)})" if comments else "Kommentare")

        vlabels = queries.version_labels(self.conn)
        for h in queries.product_history(self.conn, nummer):
            self.hist_rows.append(h)
            item = QTreeWidgetItem(self.hist_tree, [
                vlabels.get(h["import_id"], f"V{h['import_id']}"), (h["imported_at"] or "")[:10],
                CHANGE_LABELS.get(h["change_type"], h["change_type"]),
                ", ".join(FIELD_LABELS.get(f, f) for f in h["changes"])])
            item.setData(0, UD, len(self.hist_rows) - 1)
            for c in range(4):
                item.setBackground(c, QBrush(QColor(TAG_COLORS.get(h["change_type"], SURFACE))))
        if self.hist_tree.topLevelItemCount():
            self.hist_tree.setCurrentItem(self.hist_tree.topLevelItem(0))
        else:
            self.hist_text.setHtml(f"<p style='color:{MUTED}'>Keine Historie vorhanden.</p>")

    # ---- Kommentare (für alle sichtbar)
    def _send_comment(self, text):
        if not self.current_nummer:
            return
        try:
            ok = self._list_db(queries.add_comment, self.current_nummer, text, self.user)
        except ValueError:
            return
        if ok is None:
            return
        self.comments.input.clear()
        self._refresh_comments()
        self._toast("Kommentar gespeichert – für alle sichtbar")

    def _delete_comment(self, comment_id):
        if QMessageBox.question(self, "Kommentar löschen", "Eigenen Kommentar löschen?") != QMessageBox.StandardButton.Yes:
            return
        if self._list_db(queries.delete_comment, comment_id, self.user):
            self._refresh_comments()

    def _refresh_comments(self):
        nr = self.current_nummer
        comments = queries.comments_for(self.conn, nr)
        self.comments.set_comments(comments, self.user, _when)
        self.detail_tabs.setTabText(1, f"Kommentare ({len(comments)})" if comments else "Kommentare")
        self.comment_info = queries.comment_summary(self.conn)
        if nr in self.row_nummer:
            info = self.comment_info.get(nr)
            item = self.table.item(self.row_nummer.index(nr), COL["gnotiz"])
            item.setText(f"({info[0]}) {_clean(info[1]['text'])}" if info else "")

    # ---- zuletzt angesehen (je Windows-Benutzer)
    def _load_recent(self):
        value = self.settings.value("zuletzt_angesehen") or []
        return [value] if isinstance(value, str) else list(value)

    def _remember_recent(self, nummer):
        if self.recent[:1] == [nummer]:
            return
        self.recent = [nummer] + [n for n in self.recent if n != nummer][:19]
        self.settings.setValue("zuletzt_angesehen", self.recent)
        self.recent_item.setText(0, f"Zuletzt angesehen  ({len(self.recent)})")

    def _on_hist_select(self, item, _prev=None):
        if item is None:
            return
        h = self.hist_rows[item.data(0, UD)]
        vlabels = queries.version_labels(self.conn)
        ctype = h["change_type"]
        out = [f"<h3 style='margin:4px 0'>{CHANGE_LABELS.get(ctype, ctype)} in "
               f"{vlabels.get(h['import_id'], 'V' + str(h['import_id']))}</h3>",
               f"<p style='color:{MUTED}; margin:0 0 8px 0'>Importiert am {(h['imported_at'] or '').replace('T', ' ')}"
               f" · Quelle: {html.escape(h['source_name'] or '')}</p>"]
        if not h["changes"]:
            out.append("<p>" + {
                NEU: "Das Produkt ist in dieser Version neu im Verzeichnis.",
                ENTFERNT: "Das Produkt war in dieser XML nicht mehr enthalten und wurde als „entfernt“ markiert.",
                REAKTIVIERT: "Das Produkt war zuvor entfernt und ist in dieser XML wieder enthalten (Felder unverändert).",
            }.get(ctype, "Keine Feldänderungen gespeichert.") + "</p>")
        styles = {"add": f"background:{DIFF_ADD}", "del": f"background:{DIFF_DEL}", "hunk": f"color:{MUTED}", "muted": f"color:{MUTED}"}
        for fld, (old, new) in h["changes"].items():
            out.append(f"<p style='margin:12px 0 4px 0; color:{GREEN}'><b>{FIELD_LABELS.get(fld, fld)}</b></p>")
            for text, tag in diff_parts(old, new):
                out.append(f"<div style='{styles.get(tag, '')}; padding:2px 6px; white-space:pre-wrap'>{html.escape(text)}</div>")
        self.hist_text.setHtml("".join(out))

    def _product_menu(self, pos):
        if pos is not None:   # None = aus der Kartenansicht, Auswahl ist schon gesetzt
            row = self.table.rowAt(pos.y())
            if row < 0:
                return
            if row not in {i.row() for i in self.table.selectionModel().selectedRows()}:
                self.table.selectRow(row)
        sel = self._selected_nummern()
        if not sel:
            return
        menu = QMenu(self)
        if len(sel) == 1:
            menu.addAction(f"{STAR}  Favorit an/aus  (Strg+D)", self._toggle_selected_fav)
            menu.addAction("Notiz bearbeiten  (Strg+N)", self._edit_note)
        else:
            menu.addAction(f"{STAR}  {len(sel)} Produkte zu Favoriten hinzufügen", lambda: self._add_favs(sel))
            menu.addAction(f"☆  {len(sel)} Produkte aus Favoriten entfernen", lambda: self._remove_favs(sel))
        menu.addSeparator()
        n = f"{len(sel)} Produkte" if len(sel) > 1 else "Produkt"
        menu.addAction(make_icon("list"), f"{n} zu Liste hinzufügen …", lambda: self._open_add_dialog(sel, n))
        if len(sel) == 1:
            menu.addAction(make_icon("compare"), "Vergleichen mit …", lambda: self._compare_with(sel[0]))
        elif 2 <= len(sel) <= 4:
            menu.addAction(make_icon("compare"), f"{len(sel)} Produkte vergleichen …", lambda: self._compare(sel))
        c = self._current_container()
        if c is not None:
            menu.addAction(f"{n} aus „{self._container_name(c)}“ entfernen", lambda: self._remove_selected_from_current(sel))
        kat = menu.addMenu(f"Farbkategorie für {n}")
        for cid, c in self.store.categories.items():
            kat.addAction(color_icon(c["farbe"]), c["name"], lambda cid=cid: self._set_mark(sel, cid))
        kat.addSeparator()
        kat.addAction("Keine Kategorie", lambda: self._set_mark(sel, None))
        kat.addAction("Kategorien verwalten …", self._manage_categories)
        menu.addSeparator()
        menu.addAction(f"Als Tabelle kopieren ({len(sel)} Zeile{'n' if len(sel) > 1 else ''})  (Strg+C)",
                       lambda: self._copy("table"))
        menu.addAction("Nur Hilfsmittelnummern kopieren (01.24.01.0002)", lambda: self._copy("formatted"))
        menu.addAction("Nur Hilfsmittelnummern kopieren (0124010002)", lambda: self._copy("plain"))
        menu.addAction("Alle Zeilen dieser Seite markieren  (Strg+A)", self.table.selectAll)
        if len(sel) == 1:
            menu.addSeparator()
            menu.addAction("Produktart in der Hierarchie zeigen", lambda: self._reveal_level("art"))
            menu.addAction("Alle Produkte dieses Herstellers", lambda: self._on_detail_link("hersteller"))
        from PySide6.QtGui import QCursor
        menu.exec(self.table.viewport().mapToGlobal(pos) if pos is not None else QCursor.pos())

    def _copy(self, mode):
        sel = self._selected_nummern()
        if not sel:
            return
        if mode == "table":
            cols = [i for i, c in enumerate(PRODUCT_COLUMNS) if c[0] != "fav"]
            lines = ["\t".join(PRODUCT_COLUMNS[c][1] or "Kategorie" for c in cols)]
            for k in sel:
                r = self.row_nummer.index(k)
                lines.append("\t".join(_clean(self.table.item(r, c).toolTip() if c == COL["kat"] else
                                               self.table.item(r, c).text()) for c in cols))
            text = "\n".join(lines)
            msg = f"{len(sel)} Zeile(n) als Tabelle kopiert – in Excel oder E-Mail einfügen"
        else:
            text = "\n".join(format_nummer(k) if mode == "formatted" else k for k in sel)
            msg = f"Kopiert: {text}" if len(sel) == 1 else f"{len(sel)} Nummern kopiert"
        QApplication.clipboard().setText(text)
        self._toast(msg)

    # ------------------------------------------------------------------ Versionen
    def _load_versions(self):
        versions = queries.list_versions(self.conn)
        self.ver_table.blockSignals(True)
        self.ver_table.setRowCount(len(versions))
        self.ver_ids = [v["id"] for v in versions]
        for r, v in enumerate(versions):
            _fill_row(self.ver_table, r, (
                f"V{v['id']}", (v["imported_at"] or "").replace("T", " "), fmt_date(v["source_date"]),
                v["logische_version"] or "", _dots(v["n_total"]), v["n_new"], v["n_changed"], v["n_removed"],
                v["n_reactivated"], v["n_stamm_changes"], v["source_name"] or ""))
        self.ver_table.blockSignals(False)
        if versions:
            self.ver_table.selectRow(0)
        else:
            self.chg_table.setRowCount(0)
            self.ver_note.setText("Noch keine Version importiert.")

    def _selected_version(self):
        rows = self.ver_table.selectionModel().selectedRows()
        return self.ver_ids[rows[0].row()] if rows else None

    def _load_version_changes(self):
        vid = self._selected_version()
        self.chg_table.setRowCount(0)
        self.change_rows = []
        if vid is None:
            return
        ctype = TYPE_CHOICES.get(self.cb_vtype.currentText())
        limit = 5000
        total = queries.count_changes(self.conn, vid, ctype)
        self.change_rows = queries.version_changes(self.conn, vid, ctype, limit)
        self.chg_table.setRowCount(len(self.change_rows))
        for i, r in enumerate(self.change_rows):
            _fill_row(self.chg_table, i, (CHANGE_LABELS.get(r["change_type"], r["change_type"]), r["entity_label"],
                                          r["display_k"], r["name"], r["fields"]), TAG_COLORS.get(r["change_type"]))
        self.ver_title.setText(f"Änderungen in V{vid}")
        note = f"{_dots(total)} Einträge"
        if vid == self.first_id:
            note += "  (Erstimport: alle Produkte gelten als „Neu“)"
        if total > limit:
            note += f"  –  angezeigt werden die ersten {_dots(limit)}"
        self.ver_note.setText(note)

    def _version_label(self, vid):
        return next((l for l, i in self.version_by_label.items() if i == vid), ALL_VERSIONS)

    def _show_version_in_products(self):
        vid = self._selected_version()
        if vid is None:
            return
        self.cb_version.setCurrentText(self._version_label(vid))
        self.cb_type.setCurrentText(self.cb_vtype.currentText())
        self.cb_status.setCurrentText("Alle")
        self._quiet(self.search, self.search.clear)
        self._goto_page_widget(0)
        self.apply_filter()

    def _on_change_double_click(self, row):
        r = self.change_rows[row] if row < len(self.change_rows) else None
        if not r or r["entity"] != "PRODUKT":
            return
        self.cb_version.setCurrentText(self._version_label(self._selected_version()))
        self.cb_type.setCurrentIndex(0)
        self.cb_status.setCurrentText("Alle")
        self._quiet(self.search, self.search.setText, r["display_k"])
        self._goto_page_widget(0)
        self.apply_filter()
        if r["k"] in self.row_nummer:
            self.table.selectRow(self.row_nummer.index(r["k"]))

    # ------------------------------------------------------------------ Import / Export
    def _offer_first_import(self):
        if QMessageBox.question(self, "Erster Start", "Es ist noch keine HMV-XML importiert.\n\n"
                                "Jetzt eine XML- oder ZIP-Datei auswählen?") == QMessageBox.StandardButton.Yes:
            self.start_import()

    def _run_background(self, title, job, on_done, on_error):
        dlg = QProgressDialog("Starte …", None, 0, 0, self)
        dlg.setWindowTitle(title)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumWidth(460)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.show()
        w = self._worker = Worker()

        def progress(stage, current, total):
            dlg.setMaximum(total or 0)
            dlg.setValue(current if total else 0)
            dlg.setLabelText(f"{stage}  {_dots(current)}/{_dots(total)}" if total else stage)

        w.progress.connect(progress)
        w.done.connect(lambda res: (dlg.close(), on_done(res)))
        w.failed.connect(lambda exc: (dlg.close(), on_error(exc)))

        def run():
            try:
                conn = db.connect(self.db_path)
                try:
                    res = job(conn, lambda s, c, t: w.progress.emit(s, c, t))
                finally:
                    conn.close()
                w.done.emit(res)
            except BaseException as exc:  # noqa: BLE001 - an die GUI weiterreichen
                w.failed.emit(exc)

        threading.Thread(target=run, daemon=True).start()

    def start_import(self):
        path, _ = QFileDialog.getOpenFileName(self, "HMV-XML oder ZIP auswählen", "",
                                              "HMV XML / ZIP (*.xml *.zip);;Alle Dateien (*.*)")
        if path:
            self._run_import(path, force=False)

    def _run_import(self, path, force):
        self._run_background("Import läuft",
                             lambda conn, progress: importer.import_file(conn, path, force=force, progress=progress),
                             self._import_done, lambda exc: self._import_failed(exc, path))

    def _import_done(self, res):
        self.reload_all()
        if res.first_import:
            text = (f"Erstimport abgeschlossen (Version {res.import_id}).\n\n{_dots(res.n_total)} Produkte eingelesen.\n"
                    "Dies ist die Ausgangsbasis – ab dem nächsten Import werden Änderungen markiert.")
            QMessageBox.information(self, "Import abgeschlossen", text)
            return
        text = (f"Version {res.import_id} importiert – {_dots(res.n_total)} Produkte in der Datei.\n\n"
                f"Neu:  {res.n_new}\nGeändert:  {res.n_changed}\nEntfernt:  {res.n_removed}\n"
                f"Wieder aufgenommen:  {res.n_reactivated}\nUnverändert:  {_dots(res.n_unchanged)}\n"
                f"Änderungen an Gruppen/Orten/Untergruppen/Arten:  {res.n_stamm_changes}")
        if res.warnings:
            text += f"\n\n{len(res.warnings)} Warnung(en), z. B.: {res.warnings[0]}"
        self.cb_version.setCurrentText(self._version_label(res.import_id))
        self.cb_status.setCurrentText("Alle")
        n_fav = queries.count_products(self.conn, ProductFilter(status="alle", favoriten=True, import_id=res.import_id))
        if n_fav:
            # betroffene eigene Produkte sofort zeigen
            text += f"\n\n{STAR} {n_fav} Ihrer Favoriten sind betroffen – sie werden jetzt angezeigt."
            self._select_tree(self.fav_item)
        else:
            self.apply_filter()
        QMessageBox.information(self, "Import abgeschlossen", text)

    def _import_failed(self, exc, path):
        yes = QMessageBox.StandardButton.Yes
        if isinstance(exc, importer.DuplicateImport):
            if QMessageBox.question(self, "Bereits importiert",
                                    f"{exc}\n\nTrotzdem erneut importieren?\n(Es entsteht eine neue Version.)") == yes:
                self._run_import(path, force=True)
        elif isinstance(exc, importer.SuspiciousImport):
            if QMessageBox.question(self, "Plausibilitätswarnung", f"{exc}\n\nTrotzdem importieren?\n"
                                    "(Fehlende Produkte würden als „entfernt“ markiert.)") == yes:
                self._run_import(path, force=True)
        elif isinstance(exc, ET.ParseError):
            QMessageBox.critical(self, "Import fehlgeschlagen", f"Die Datei ist keine gültige XML:\n{exc}")
        elif isinstance(exc, sqlite3.OperationalError) and "locked" in str(exc):
            QMessageBox.warning(self, "Datenbank gerade belegt",
                                "Ein anderer Benutzer ändert gerade die gemeinsame Datenbank (z. B. ein Import).\n"
                                "Bitte in ein paar Minuten erneut versuchen.")
        elif isinstance(exc, (SourceError, importer.EmptyImport)):
            QMessageBox.critical(self, "Import fehlgeschlagen", str(exc))
        else:
            QMessageBox.critical(self, "Import fehlgeschlagen", f"{type(exc).__name__}: {exc}")

    def start_export(self):
        if not queries.list_versions(self.conn):
            QMessageBox.information(self, "Export", "Es sind noch keine Daten vorhanden – bitte zuerst eine XML importieren.")
            return
        self._save_note()
        n_favs = queries.count_products(self.conn, ProductFilter(status="alle", favoriten=True))
        dlg = ExportDialog(self, self.total, n_favs)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        opts = dlg.options()
        stamp = dt.date.today().strftime("%Y%m%d")
        name = "HMV_Favoriten" if opts["scope"] == "favoriten" else "HMV_Export"
        if opts["scope"] == "filter" and self._current_container() not in (None, ("fav", None)):
            name = "HMV_Liste_" + "".join(c if c.isalnum() else "_" for c in self._container_name(self._current_container()))
        path, _ = QFileDialog.getSaveFileName(self, "Excel-Datei speichern", f"{name}_{stamp}.xlsx",
                                              "Excel-Arbeitsmappe (*.xlsx)")
        if not path:
            return
        f = {"filter": replace(self.filter), "favoriten": ProductFilter(status="alle", favoriten=True)}.get(
            opts["scope"]) or ProductFilter(status=opts["scope"])
        store = self.store

        def job(conn, progress):
            store.attach(conn)   # Favoriten-Filter braucht die TEMP-Tabelle auch in dieser Verbindung
            return exporter.export_excel(conn, path, f, include_history=opts["history"],
                                         include_versions=opts["versions"],
                                         include_initial_in_history=opts["initial"], progress=progress,
                                         favorites=store if opts["personal"] else None)

        def done(res):
            msg = f"{_dots(res['products'])} Produkte exportiert"
            if opts["history"]:
                msg += f"\n{_dots(res['history_rows'])} Zeilen in der Änderungshistorie"
            box = QMessageBox(QMessageBox.Icon.Information, "Export abgeschlossen", f"{msg}\n\n{path}", parent=self)
            open_btn = box.addButton("Datei öffnen", QMessageBox.ButtonRole.AcceptRole)
            box.addButton("Schließen", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.clickedButton() is open_btn:
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))

        def failed(exc):
            if isinstance(exc, PermissionError):
                QMessageBox.critical(self, "Export fehlgeschlagen",
                                     f"Die Datei konnte nicht geschrieben werden (ist sie in Excel geöffnet?):\n{path}")
            else:
                QMessageBox.critical(self, "Export fehlgeschlagen", f"{type(exc).__name__}: {exc}")

        self._run_background("Excel-Export läuft", job, done, failed)


def setup_app(theme=None):
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("HMV-Viewer")
    app.setStyle("Fusion")
    apply_theme(theme or "Classic")   # das Hauptfenster stellt danach die gespeicherte Farbwelt ein
    return app


def run_gui(db_path, fav_dir=None):
    app = setup_app()
    win = MainWindow(db_path, fav_dir=fav_dir)
    win.show()
    return app.exec()
