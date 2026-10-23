"""Farbwelten, Schriftgröße und Zeilenhöhe für die QML-Oberfläche (je Benutzer gespeichert).

Alle Farbpaare für Text sind auf Lesbarkeit geprüft (WCAG-Kontrast, siehe tests/test_qml.py):
normaler Text mindestens 4,5 : 1, Fokusrahmen und Symbole mindestens 3 : 1.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Property, Signal, Slot

DEFAULT_THEME = "AOK Modern"
_TAGS_LIGHT = dict(tagNeu="#D9F2D0", tagGeaendert="#FFF2B3", tagEntfernt="#F6C9C0", tagReaktiviert="#CFE3F7",
                   tagUmgruppiert="#E4DCF3")
_TAGS_DARK = dict(tagNeu="#1F4730", tagGeaendert="#4D4216", tagEntfernt="#552A27", tagReaktiviert="#1F3B57",
                  tagUmgruppiert="#3E2F5C")
_HEADER_ON_GREEN = dict(headerBtn="#1FFFFFFF", headerBtnHover="#3DFFFFFF", headerBtnBorder="#59FFFFFF")
_LIGHT = dict(dark=False, gold="#F2B500", goldText="#1B2A23", onAccent="#FFFFFF", danger="#B3261E", onDanger="#FFFFFF",
              diffAdd="#E6FFED", diffDel="#FFEEF0", shadow="#29003C23", **_TAGS_LIGHT, **_HEADER_ON_GREEN)
_DARK = dict(dark=True, gold="#F2B500", goldText="#14100A", danger="#FF8A80", onDanger="#2B0A07", diffAdd="#1F3A2A",
             diffDel="#432427", **_HEADER_ON_GREEN,
             shadow="#66000000", **_TAGS_DARK)

THEMES = {
    "AOK Modern": dict(_LIGHT, bg="#F3F7F5", surface="#FFFFFF", alt="#F8FBF9", line="#DDE7E1", text="#1B2A23",
                       muted="#55665D", green="#005E3F", greenDark="#00472F", mint="#E1F3E9", mintHover="#CDEBDB",
                       select="#C4E6D3", hover="#EEF6F1", focus="#00804F", scroll="#B9CBC1",
                       headerA="#00472F", headerB="#005E3F", headerC="#00804F", headerFg="#FFFFFF", headerSub="#C9E8D7",
                       disabledBg="#EEF2F0", disabledFg="#8A9A91"),
    "AOK Modern Dunkel": dict(_DARK, bg="#111815", surface="#19221E", alt="#1D2723", line="#2B3833", text="#E6ECE9",
                              muted="#A3B1AA", green="#5CC596", greenDark="#46AE80", mint="#20352B", mintHover="#294436",
                              select="#2A4A3B", hover="#22302A", focus="#7FD9AE", scroll="#3E4D46", onAccent="#0B1A13",
                              headerA="#0A2219", headerB="#0E3324", headerC="#145238", headerFg="#E6ECE9",
                              headerSub="#9FD2B8", disabledBg="#202A26", disabledFg="#66756E"),
    "Classic": dict(_LIGHT, bg="#F2F5F3", surface="#FFFFFF", alt="#F7FAF8", line="#DCE5E0", text="#1B2A23",
                    muted="#55665D", green="#005E3F", greenDark="#00472F", mint="#E3F2EA", mintHover="#D0EADC",
                    select="#C7E5D5", hover="#EEF6F1", focus="#00804F", scroll="#C5D3CB",
                    headerA="#005E3F", headerB="#005E3F", headerC="#005E3F", headerFg="#FFFFFF", headerSub="#C9E8D7",
                    disabledBg="#EEF2F0", disabledFg="#8A9A91"),
    "Hell": dict(_LIGHT, bg="#F7F8FA", surface="#FFFFFF", alt="#FAFBFC", line="#E3E6EA", text="#1F2328",
                 muted="#59616A", green="#0B7A55", greenDark="#08603F", mint="#EEF1F4", mintHover="#E1E6EB",
                 select="#DCEFE6", hover="#F2F5F7", focus="#0B7A55", scroll="#CDD3DA",
                 headerA="#FFFFFF", headerB="#FFFFFF", headerC="#FFFFFF", headerFg="#1F2328", headerSub="#59616A",
                 headerBtn="#F3F4F6", headerBtnHover="#E7EAEE", headerBtnBorder="#D5DAE0",
                 disabledBg="#F3F4F6", disabledFg="#8C939B"),
    "Dunkel": dict(_DARK, bg="#15191C", surface="#1E2428", alt="#222A2E", line="#2E363B", text="#E6EAE8",
                   muted="#A1ACA6", green="#4FC08D", greenDark="#3BA677", mint="#24332C", mintHover="#2E4238",
                   select="#2F5544", hover="#283137", focus="#7FD9AE", scroll="#3A454B", onAccent="#0B1A13",
                   headerA="#0F2A20", headerB="#0F2A20", headerC="#0F2A20", headerFg="#E6EAE8", headerSub="#9FC9B4",
                   disabledBg="#232A2E", disabledFg="#66726C"),
}
FONT_SIZES = (10, 11, 12, 13, 14, 16)
DENSITY = {"Kompakt": 30, "Normal": 36, "Groß": 44, "Sehr groß": 52}   # Zeilenhöhe der Tabellen


def _lum(hex_color):
    h = hex_color.lstrip("#")[-6:]
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    """WCAG-Kontrastverhältnis zweier Farben (1 … 21)."""
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


class Theme(QObject):
    changed = Signal()

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        name = settings.value("design", DEFAULT_THEME)
        self._name = name if name in THEMES else DEFAULT_THEME
        size = str(settings.value("schrift", 12))
        self._font = int(size) if size.isdigit() and int(size) in FONT_SIZES else 12
        dens = settings.value("dichte", "Groß")
        self._density = dens if dens in DENSITY else "Groß"

    @property
    def colors(self):
        return THEMES[self._name]

    def get(self, key):
        return THEMES[self._name][key]

    c = Property("QVariantMap", lambda self: dict(self.colors), notify=changed)
    name = Property(str, lambda self: self._name, notify=changed)
    dark = Property(bool, lambda self: self.colors["dark"], notify=changed)
    fontPt = Property(int, lambda self: self._font, notify=changed)
    rowH = Property(int, lambda self: DENSITY[self._density], notify=changed)
    density = Property(str, lambda self: self._density, notify=changed)
    names = Property("QVariantList", lambda self: list(THEMES), constant=True)
    fontSizes = Property("QVariantList", lambda self: list(FONT_SIZES), constant=True)
    densities = Property("QVariantList", lambda self: list(DENSITY), constant=True)

    @Slot(str)
    def setTheme(self, name):
        if name in THEMES:
            self._name = name
            self.settings.setValue("design", name)
            self.changed.emit()

    @Slot(int)
    def setFont(self, size):
        if size in FONT_SIZES:
            self._font = size
            self.settings.setValue("schrift", size)
            self.changed.emit()

    @Slot(str)
    def setDensity(self, name):
        if name in DENSITY:
            self._density = name
            self.settings.setValue("dichte", name)
            self.changed.emit()

    def tag(self, ctype):
        """Hintergrundfarbe eines Änderungstyps (NEU, GEAENDERT …) oder ''."""
        key = {"NEU": "tagNeu", "GEAENDERT": "tagGeaendert", "ENTFERNT": "tagEntfernt", "REAKTIVIERT": "tagReaktiviert",
               "UMGRUPPIERT": "tagUmgruppiert"}.get(ctype or "")
        return self.colors[key] if key else ""
