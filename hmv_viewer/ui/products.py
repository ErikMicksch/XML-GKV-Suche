"""Produktliste: Suche, Filter, Spalten, Auswahl, Kontextmenü, Kopieren, gespeicherte Suchen, Nummernliste."""
from __future__ import annotations

import html
import json
import sqlite3

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot
from PySide6.QtGui import QFontMetrics, QGuiApplication

from hmv_viewer import merkmale, queries
from hmv_viewer.gui import (PAGE_SIZE, PRODUCT_COLUMNS, STATUS_CHOICES, TYPE_CHOICES, _clean, _dots, _who, fmt_date)
from hmv_viewer.model import CHANGE_LABELS, ENTFERNT, NEU, UMGRUPPIERT, format_nummer
from hmv_viewer.queries import ProductFilter
from hmv_viewer.ui_extras import parse_numbers

from .core import SEP, entry, flag
from .models import DictModel

ROLES = ("idx", "nummer", "c", "tips", "bg", "katColor", "selected", "title", "subtitle", "chips", "comment", "star")
TITLES = {"fav": "★", "kat": "Farbe"}
LOCKED = ("nummer", "bezeichnung")   # Pflichtspalten
FILTER_KEYS = ("text", "inBez", "inMerk", "inNotes", "status", "version", "ctype", "hersteller", "kategorie",
               "ohnePlatzhalter")
STATUS_BY_VALUE = {v: k for k, v in STATUS_CHOICES.items()}
TYPE_BY_VALUE = {v: k for k, v in TYPE_CHOICES.items()}


class Products(QObject):
    changed = Signal()
    currentRowChanged = Signal(int)
    listReset = Signal()

    def __init__(self, core):
        super().__init__()
        self.core = core
        s = core.settings
        self.model = DictModel(ROLES, self)
        self.st = {"text": "", "inBez": flag(s, "suche_bez", True), "inMerk": flag(s, "merkmale_suche", True),
                   "inNotes": flag(s, "suche_notizen", True), "status": "aktiv", "version": 0, "ctype": "",
                   "hersteller": "", "kategorie": "", "ohnePlatzhalter": flag(s, "ohne_platzhalter", False),
                   "moreFilters": flag(s, "mehr_filter", False), "viewMode": s.value("ansicht", "tabelle"),
                   "order": "nummer", "desc": False}
        self.filter = ProductFilter()
        self.query_words = []
        self.extra_nummern = None
        self.total = 0
        self.loaded = []
        self.sel, self.cur, self.anchor = set(), -1, -1
        self.hersteller_all = []
        self.version_labels = {}
        self._empty = {}
        self._title = "Produkte"
        self._pager = ""
        self.cols = self._load_columns()
        self.save_timer = QTimer(self, singleShot=True, interval=600, timeout=self._save_columns)

    # ------------------------------------------------------------------ Eigenschaften für QML
    modelObj = Property(QObject, lambda self: self.model, constant=True)
    state = Property("QVariantMap", lambda self: dict(self.st), notify=changed)
    title = Property(str, lambda self: self._title, notify=changed)
    pager = Property(str, lambda self: self._pager, notify=changed)
    totalCount = Property(int, lambda self: self.total, notify=changed)
    empty = Property("QVariantMap", lambda self: dict(self._empty), notify=changed)
    selectedCount = Property(int, lambda self: len(self.sel), notify=changed)
    statusOptions = Property("QVariantList", lambda self: [{"value": v, "text": k} for k, v in STATUS_CHOICES.items()],
                             constant=True)
    typeOptions = Property("QVariantList", lambda self: [{"value": v or "", "text": k} for k, v in TYPE_CHOICES.items()],
                           constant=True)
    versionOptions = Property("QVariantList", lambda self: [{"value": 0, "text": "Alle Versionen"}] + [
        {"value": i, "text": t} for i, t in self.version_labels.items()], notify=changed)
    categoryOptions = Property("QVariantList", lambda self: [{"value": "", "text": "Alle Kategorien", "color": ""}] + [
        {"value": cid, "text": c["name"], "color": c["farbe"]} for cid, c in self.core.store.categories.items()]
        if self.core.store else [], notify=changed)
    columns = Property("QVariantList", lambda self: self._columns_spec(), notify=changed)
    visibleColumns = Property("QVariantList", lambda self: [c for c in self._columns_spec() if c["visible"]],
                              notify=changed)
    savedSearches = Property("QVariantList", lambda self: sorted(self.core.store.searches, key=str.casefold)
                             if self.core.store else [], notify=changed)

    @Property(int, notify=changed)
    def activeMoreFilters(self):
        st = self.st
        return sum((st["status"] != "aktiv", bool(st["version"]), bool(st["ctype"]), bool(st["hersteller"]),
                    bool(st["kategorie"]), bool(st["ohnePlatzhalter"])))

    # ------------------------------------------------------------------ Filterzustand
    @Slot(str, "QVariant")
    def set(self, key, value):
        if key in ("version",):
            value = int(value or 0)
        if self.st.get(key) == value:
            return
        self.st[key] = value
        saved = {"inBez": "suche_bez", "inMerk": "merkmale_suche", "inNotes": "suche_notizen",
                 "ohnePlatzhalter": "ohne_platzhalter", "moreFilters": "mehr_filter", "viewMode": "ansicht"}
        if key in saved:
            self.core.settings.setValue(saved[key], value)
        if key in FILTER_KEYS:
            self.refresh()
        else:
            self.changed.emit()

    def reload_options(self):
        self.version_labels = {v["id"]: queries.version_label(v) for v in queries.list_versions(self.core.conn)}
        if self.st["version"] not in self.version_labels:
            self.st["version"] = 0
        if self.st["kategorie"] not in self.core.store.categories:
            self.st["kategorie"] = ""
        self.hersteller_all = queries.list_hersteller(self.core.conn)
        self.changed.emit()

    @Slot(str, result="QVariantList")
    def herstellerMatches(self, text):
        t = text.strip().casefold()
        return [h for h in self.hersteller_all if t in h.casefold()][:60] if t else self.hersteller_all[:60]

    def read_filter(self):
        st, key = self.st, self.core.tree.current_key()
        self.filter = ProductFilter(
            text=st["text"].strip(), in_merkmale=st["inMerk"], in_bez=st["inBez"], in_notizen=st["inNotes"],
            status=st["status"], gruppe=key.get("gruppe"), ort=key.get("ort"), untergruppe=key.get("untergruppe"),
            art=key.get("art"), import_id=st["version"] or None, change_type=st["ctype"] or None,
            favoriten=bool(key.get("favoriten")), liste_id=key.get("liste"), pliste_id=key.get("pliste"),
            nummern=tuple(self.core.recent) if key.get("zuletzt") else self.extra_nummern,
            hersteller=st["hersteller"].strip(), kategorie=st["kategorie"] or None,
            ohne_platzhalter=st["ohnePlatzhalter"])
        self.query_words = merkmale.parse_query(self.filter.text).words if self.filter.in_merkmale else []

    # ------------------------------------------------------------------ Liste laden
    def status_text(self, p):
        if not p["active"]:
            verb = "Umgruppiert" if p["last_change_type"] == UMGRUPPIERT else "Entfernt"
            return f"{verb} in V{p['removed_import']}"
        if p["last_import_change"] == self.core.first_id and p["last_change_type"] == NEU:
            return "Erstimport"
        return f"{CHANGE_LABELS.get(p['last_change_type'], '')} in V{p['last_import_change']}"

    def row_tag(self, p):
        core = self.core
        if not p["active"]:
            return UMGRUPPIERT if p["last_change_type"] == UMGRUPPIERT else ENTFERNT
        if self.filter.import_id is not None:
            return None if self.filter.import_id == core.first_id else p["shown_type"]
        if p["last_import_change"] == core.latest_id and core.latest_id != core.first_id:
            return p["last_change_type"]
        return None

    def _row(self, p, i):
        core, nr = self.core, p["nummer"]
        store, theme = core.store, core.theme
        info = core.comment_info.get(nr)
        cat = store.categories.get(store.marks.get(nr))
        tag = self.row_tag(p)
        note = store.notes.get(nr, "")
        star = core.lists_ctl.star_for(nr)
        c = {"fav": star, "kat": cat["name"] if cat else "", "nummer": format_nummer(nr), "bezeichnung": p["bezeichnung"] or "",
             "hersteller": p["hersteller"] or "", "fund": merkmale.fundstelle(p["merkmale"], self.query_words),
             "notiz": _clean(note), "gnotiz": f"({info[0]}) {_clean(info[1]['text'])}" if info else "",
             "art": core.names.path(p)["art"], "aufnahme": fmt_date(p["aufnahmedatum"]),
             "aenderung": fmt_date(p["aenderungsdatum"]), "version": self.status_text(p)}
        tips = {"fav": "Klicken: Favorit an/aus" + (" (☆ = über eine ganze Gruppe Favorit)" if star == "☆" else ""),
                "bezeichnung": (p["merkmale"] or "")[:700], "notiz": note, "kat": c["kat"],
                "gnotiz": f"{info[0]} Kommentar(e), zuletzt {info[1]['user'] or '?'}: {info[1]['text']}" if info else ""}
        chips = [{"text": CHANGE_LABELS[tag], "color": theme.tag(tag)}] if tag else []
        if cat:
            chips.append({"text": cat["name"], "color": theme.get("mint")})
        comment = f"{info[1]['user'] or '?'}: {info[1]['text']}" if info else note
        return {"idx": i, "nummer": nr, "c": c, "tips": tips, "bg": theme.tag(tag) if tag else "",
                "katColor": cat["farbe"] if cat else "", "selected": i in self.sel, "star": star,
                "title": p["bezeichnung"] or "(ohne Bezeichnung)", "subtitle": f"{format_nummer(nr)} · {p['hersteller'] or ''}",
                "chips": chips, "comment": _clean(comment)[:140]}

    def refresh(self, keep=None):
        """Filter lesen, Liste neu laden. keep: Produktnummer, die danach wieder ausgewählt sein soll."""
        core = self.core
        if core.store is None:
            return
        self.read_filter()
        self.total = queries.count_products(core.conn, self.filter)
        self.loaded = []
        core.comment_info = queries.comment_summary(core.conn)
        self.sel, self.cur, self.anchor = set(), -1, -1
        self.model.set_rows([])
        self._load_more()
        self._update_empty()
        self._summary()
        self.listReset.emit()
        self.changed.emit()
        if keep and keep in [r["nummer"] for r in self.loaded]:
            self.click([r["nummer"] for r in self.loaded].index(keep), False, False)
        else:
            core.detail.show(None)

    def _load_more(self):
        if self.loaded and len(self.loaded) >= self.total:
            return
        rows = queries.fetch_products(self.core.conn, self.filter, self.st["order"], self.st["desc"],
                                      limit=PAGE_SIZE, offset=len(self.loaded))
        start = len(self.loaded)
        self.loaded += rows
        self.model.append_rows([self._row(p, start + i) for i, p in enumerate(rows)])
        rest = self.total - len(self.loaded)
        self._pager = f"{_dots(self.total)} Treffer" + (
            f" · {_dots(len(self.loaded))} geladen – weiter scrollen lädt mehr" if rest > 0 else "")

    @Slot()
    def loadMore(self):
        if len(self.loaded) < self.total:
            self._load_more()
            self.changed.emit()

    def _summary(self):
        core, f = self.core, self.filter
        parts = [f"{_dots(self.total)} Produkte"]
        if core.tree.current != "all":
            parts.append(f"Bereich: {core.tree.label_of(core.tree.current)}")
        if self.extra_nummern is not None:
            parts.append(f"eingefügte Nummernliste ({len(self.extra_nummern)})")
        if f.kategorie in core.store.categories:
            parts.append(f"Kategorie: {core.store.categories[f.kategorie]['name']}")
        if f.hersteller:
            parts.append(f"Hersteller: „{f.hersteller}“")
        if f.text:
            parts.append(f"Suche: „{f.text}“")
        if f.liste_id in core.lists:
            parts.append("zuletzt geändert: " + _who(core.lists[f.liste_id]))
        core.show_status("  ·  ".join(parts))
        self._title = core.tree.label_of(core.tree.current)

    def _update_empty(self):
        core, f = self.core, self.filter
        if self.total:
            self._empty = {}
            return
        if core.latest_id is None:
            e = ("import", "Noch keine Daten vorhanden", "Lesen Sie zuerst eine HMV-XML- oder ZIP-Datei ein.",
                 "import", "Jetzt importieren …")
        elif f.favoriten and not f.text and not f.hersteller:
            e = ("star", "Noch keine Favoriten", "Klicken Sie in der Liste auf den Stern ☆ oder ziehen Sie Produkte "
                 "mit der Maus auf „Meine Favoriten“.", "", "")
        elif f.kategorie is not None and not f.text:
            e = ("tag", "Noch keine Produkte mit dieser Kategorie", "Produkt mit der rechten Maustaste anklicken und "
                 "„Farbkategorie“ wählen – oder rechts in den Details eine Kategorie setzen.", "reset", "Filter zurücksetzen")
        elif (f.liste_id is not None or f.pliste_id is not None) and not f.text and not f.hersteller:
            e = ("list", "Diese Liste ist noch leer", "Produkte mit der Maus hierher ziehen oder mit der rechten "
                 "Maustaste „Zu Liste hinzufügen …“ wählen.", "", "")
        elif f.nummern is not None and not core.recent and self.extra_nummern is None:
            e = ("history", "Noch nichts angesehen", "Geöffnete Produkte erscheinen hier.", "", "")
        else:
            e = ("search", "Keine Treffer", "Für diese Suche und diese Filter gibt es keine Produkte. "
                 "Prüfen Sie die Schreibweise oder setzen Sie die Filter zurück.", "reset", "Alle Filter zurücksetzen")
        self._empty = dict(zip(("icon", "title", "text", "action", "actionText"), e))

    @Slot(str)
    def emptyAction(self, action):
        if action == "import":
            self.core.maint.start_import()
        elif action == "reset":
            self.resetFilter()

    def on_area_changed(self):
        self.extra_nummern = None   # eingefügte Nummernliste gilt nur bis zum nächsten Bereichswechsel
        self.refresh()

    @Slot()
    def resetFilter(self):
        self.extra_nummern = None
        self.st.update(text="", hersteller="", status="aktiv", version=0, ctype="", kategorie="")
        if self.core.tree.term:
            self.core.tree.setFilter("")
        self.core.tree.select("all", refresh=False)
        self.refresh()

    @Slot(str)
    def sortBy(self, key):
        sort = next((c[3] for c in PRODUCT_COLUMNS if c[0] == key), None)
        if sort is None:
            return
        self.st["desc"] = (not self.st["desc"]) if self.st["order"] == sort else (sort == "fav")   # Favoriten zuerst
        self.st["order"] = sort
        self.refresh(keep=self.current_nummer())

    def update_stars(self):
        for i, r in enumerate(self.model.rows):
            star = self.core.lists_ctl.star_for(r["nummer"])
            if star != r["star"]:
                self.model.update_row(i, star=star, c=dict(r["c"], fav=star))

    def update_rows(self, nummern):
        """Zeilen nach Notiz/Kategorie/Kommentar neu aufbauen (ohne die Liste neu zu laden)."""
        self.core.comment_info = queries.comment_summary(self.core.conn)
        for i, p in enumerate(self.loaded):
            if p["nummer"] in nummern:
                self.model.update_row(i, **self._row(p, i))

    # ------------------------------------------------------------------ Auswahl
    def current_nummer(self):
        return self.loaded[self.cur]["nummer"] if 0 <= self.cur < len(self.loaded) else None

    def selected_nummern(self):
        return [self.loaded[i]["nummer"] for i in sorted(self.sel) if i < len(self.loaded)]

    def _apply_selection(self, old):
        for i in old ^ self.sel:
            self.model.update_row(i, selected=i in self.sel)
        self.currentRowChanged.emit(self.cur)
        sel = self.selected_nummern()
        current = self.current_nummer()
        nummer = current if current in sel else (sel[0] if sel else None)
        if len(sel) > 1:
            self.core.show_status(f"{len(sel)} Zeilen markiert – Strg+C kopiert sie als Tabelle, "
                                  "rechte Maustaste für Listen und Vergleich", 5000)
        if nummer != self.core.detail.nummer:
            self.core.detail.show(nummer)
        self.changed.emit()

    @Slot(int, bool, bool)
    def click(self, row, ctrl, shift):
        if not 0 <= row < len(self.loaded):
            return
        old = set(self.sel)
        if shift and self.anchor >= 0:
            span = set(range(min(self.anchor, row), max(self.anchor, row) + 1))
            self.sel = (self.sel | span) if ctrl else span
        elif ctrl:
            self.sel ^= {row}
            self.anchor = row
        else:
            self.sel = {row}
            self.anchor = row
        self.cur = row
        self._apply_selection(old)

    @Slot(int, bool)
    def move(self, delta, shift):
        if not self.loaded:
            return
        row = min(max(0, (self.cur if self.cur >= 0 else -1) + delta), len(self.loaded) - 1)
        if row >= len(self.loaded) - 5:
            self.loadMore()
        self.click(row, False, shift)

    @Slot()
    def selectAll(self):
        old = set(self.sel)
        self.sel = set(range(len(self.loaded)))
        self._apply_selection(old)

    @Slot(int)
    def starClicked(self, row):
        if 0 <= row < len(self.loaded):
            self.core.lists_ctl.toggle_fav(self.loaded[row]["nummer"])

    @Slot(int)
    def doubleClicked(self, row):
        self.click(row, False, False)
        self.core.requestFocus("note")

    @Slot(int, result=str)
    def dragStart(self, row):
        if row not in self.sel:
            self.click(row, False, False)
        n = len(self.sel)
        return f"{n} Produkt{'e' if n != 1 else ''} – auf eine Liste links ziehen"

    # ------------------------------------------------------------------ Kontextmenü
    @Slot(int)
    def openMenu(self, row):
        if row >= 0 and row not in self.sel:
            self.click(row, False, False)
        sel = self.selected_nummern()
        if not sel:
            return
        core, lists = self.core, self.core.lists_ctl
        n = f"{len(sel)} Produkte" if len(sel) > 1 else "Produkt"
        items = []
        if len(sel) == 1:
            items += [entry("Favorit an/aus  (Strg+D)", self.toggleSelectedFav, "star"),
                      entry("Notiz bearbeiten  (Strg+N)", lambda: core.requestFocus("note"), "edit")]
        else:
            items += [entry(f"{len(sel)} Produkte zu Favoriten hinzufügen", lambda: lists.add(("fav", None), sel), "star"),
                      entry(f"{len(sel)} Produkte aus Favoriten entfernen", lambda: lists.remove(("fav", None), sel), "close")]
        items += [SEP, entry(f"{n} zu Liste hinzufügen …", lambda: lists.open_add(sel, n), "list")]
        if len(sel) == 1:
            items.append(entry("Vergleichen mit …", lambda: core.compare.compare_with(sel[0]), "compare"))
        elif 2 <= len(sel) <= 4:
            items.append(entry(f"{len(sel)} Produkte vergleichen …", lambda: core.compare.open(sel), "compare"))
        c = lists.current_container()
        if c is not None:
            items.append(entry(f"{n} aus „{lists.name(c)}“ entfernen", lambda: lists.remove_selected_from_current(sel),
                               "close"))
        cats = [entry(cat["name"], lambda cid=cid: self.set_mark(sel, cid), "tag") for cid, cat in
                core.store.categories.items()]
        cats += [SEP, entry("Keine Kategorie", lambda: self.set_mark(sel, None), "close"),
                 entry("Kategorien verwalten …", core.maint.openCategories, "settings")]
        items += [entry(f"Farbkategorie für {n}", icon="tag", children=cats), SEP,
                  entry(f"Als Tabelle kopieren ({len(sel)} Zeile{'n' if len(sel) > 1 else ''})  (Strg+C)",
                        lambda: self.copy("table"), "copy"),
                  entry("Nur Hilfsmittelnummern kopieren (01.24.01.0002)", lambda: self.copy("formatted"), "copy"),
                  entry("Nur Hilfsmittelnummern kopieren (0124010002)", lambda: self.copy("plain"), "copy"),
                  entry("Alle geladenen Zeilen markieren  (Strg+A)", self.selectAll, "check")]
        if len(sel) == 1:
            items += [SEP, entry("Produktart in der Hierarchie zeigen", lambda: core.detail.link("goto:art"), "box"),
                      entry("Alle Produkte dieses Herstellers", lambda: core.detail.link("goto:hersteller"), "filter")]
        core.popup_menu(items)

    @Slot()
    def toggleSelectedFav(self):
        sel = self.selected_nummern()
        if len(sel) == 1:
            self.core.lists_ctl.toggle_fav(sel[0])
        elif sel:
            self.core.lists_ctl.add(("fav", None), sel)

    @Slot(str)
    def copy(self, mode):
        sel = self.selected_nummern()
        if not sel:
            return
        if mode == "table":
            cols = [c for c in PRODUCT_COLUMNS if c[0] != "fav"]
            by_nr = {r["nummer"]: r for r in self.model.rows}
            lines = ["\t".join(c[1] or "Kategorie" for c in cols)]
            lines += ["\t".join(_clean(by_nr[k]["c"][c[0]]) for c in cols) for k in sel]
            text, msg = "\n".join(lines), f"{len(sel)} Zeile(n) als Tabelle kopiert – in Excel oder E-Mail einfügen"
        else:
            text = "\n".join(format_nummer(k) if mode == "formatted" else k for k in sel)
            msg = f"Kopiert: {text}" if len(sel) == 1 else f"{len(sel)} Nummern kopiert"
        QGuiApplication.clipboard().setText(text)
        self.core.toast(msg)

    # ------------------------------------------------------------------ Farbkategorien
    def set_mark(self, nummern, cid, record=True):
        core = self.core
        old = {k: core.store.marks.get(k) for k in nummern}
        if core.persist(core.store.set_mark, nummern, cid) is None:
            return
        if not core.read_only:   # für „Änderungen anderer“ bei den Kollegen; Fehler hier nie störend
            cat = core.store.categories.get(cid) if cid else None
            try:
                queries.log_activity(core.conn, core.user, "kategorie", nummern, cat["name"] if cat else "",
                                     cat["farbe"] if cat else None)
            except sqlite3.Error:
                pass
        core.store.attach(core.conn)
        msg = f"{len(nummern)} Produkt(e): {core.store.categories[cid]['name'] if cid else 'keine Kategorie'}"
        if record:
            def undo():
                groups = {}
                for k, v in old.items():
                    groups.setdefault(v if v in core.store.categories else None, []).append(k)
                for v, ks in groups.items():
                    self.set_mark(ks, v, record=False)
            core.push_undo(msg, undo)
        else:
            core.toast(msg)
        if self.filter.kategorie is not None:
            self.refresh()
        else:
            self.update_rows(set(nummern))
            if core.detail.nummer in nummern:
                core.detail.reload()

    # ------------------------------------------------------------------ Spalten
    def _load_columns(self):
        defaults = [{"key": c[0], "width": c[2], "visible": True} for c in PRODUCT_COLUMNS]
        try:
            saved = json.loads(self.core.settings.value("qml_spalten") or "[]")
        except (TypeError, ValueError):
            saved = []
        known = {c["key"]: c for c in defaults}
        cols = [dict(known[c["key"]], width=max(30, int(c.get("width", 100))), visible=bool(c.get("visible", True)))
                for c in saved if isinstance(c, dict) and c.get("key") in known]
        cols += [c for c in defaults if c["key"] not in {x["key"] for x in cols}]
        for c in cols:
            c["visible"] = c["visible"] or c["key"] in LOCKED
        return cols

    def _save_columns(self):
        self.core.settings.setValue("qml_spalten", json.dumps(self.cols))

    def _columns_spec(self):
        sort_of = {c[0]: c[3] for c in PRODUCT_COLUMNS}
        title_of = {c[0]: c[1] for c in PRODUCT_COLUMNS}
        out = []
        for c in self.cols:
            sort = sort_of[c["key"]]
            out.append({"key": c["key"], "title": TITLES.get(c["key"], title_of[c["key"]]), "width": c["width"],
                        "visible": c["visible"], "locked": c["key"] in LOCKED, "sortable": sort is not None,
                        "sorted": ("desc" if self.st["desc"] else "asc") if sort and sort == self.st["order"] else "",
                        "label": {"kat": "Farbkategorie (Farbfeld)", "fav": "Favorit (★)"}.get(c["key"], title_of[c["key"]])})
        return out

    def _col(self, key):
        return next(c for c in self.cols if c["key"] == key)

    @Slot(str, int)
    def setColumnWidth(self, key, width):
        self._col(key)["width"] = max(30, int(width))
        self.save_timer.start()
        self.changed.emit()

    @Slot(str, bool)
    def toggleColumn(self, key, on):
        if key not in LOCKED:
            self._col(key)["visible"] = on
            self.save_timer.start()
            self.changed.emit()

    @Slot(str, int)
    def moveColumn(self, key, delta):
        i = next(k for k, c in enumerate(self.cols) if c["key"] == key)
        j = min(max(0, i + delta), len(self.cols) - 1)
        self.cols.insert(j, self.cols.pop(i))
        self.save_timer.start()
        self.changed.emit()

    @Slot()
    def resetColumns(self):
        self.cols = [{"key": c[0], "width": c[2], "visible": True} for c in PRODUCT_COLUMNS]
        self.save_timer.start()
        self.changed.emit()

    @Slot(str)
    def autoWidth(self, key):
        """Doppelklick auf den Spaltenrand: Breite passend zum Inhalt der geladenen Zeilen."""
        fm = QFontMetrics(QGuiApplication.font())
        scale = self.core.theme.fontPt / max(1, QGuiApplication.font().pointSizeF())
        title = next(c["title"] for c in self._columns_spec() if c["key"] == key)
        texts = [r["c"][key] for r in self.model.rows[:500]] + [title]
        width = max((fm.horizontalAdvance(str(t)) for t in texts), default=60) * scale + 34
        self.setColumnWidth(key, min(900, int(width)))

    # ------------------------------------------------------------------ gespeicherte Suchen (Format wie Hauptoberfläche)
    def _search_state(self):
        st = self.st
        return {"text": st["text"], "merk": st["inMerk"], "bez": st["inBez"], "notizen": st["inNotes"],
                "status": STATUS_BY_VALUE.get(st["status"], "Nur aktive"),
                "version": self.version_labels.get(st["version"], "Alle Versionen"),
                "typ": TYPE_BY_VALUE.get(st["ctype"] or None, "Alle Änderungstypen"), "hersteller": st["hersteller"],
                "kategorie": st["kategorie"] or None, "bereich": self.core.tree.current_key()}

    @Slot(str)
    def applySaved(self, name):
        st = self.core.store.searches.get(name)
        if st is None:
            return
        self.core.goto(0)
        self.extra_nummern = None
        versions = {t: i for i, t in self.version_labels.items()}
        self.st.update(text=st.get("text", ""), inMerk=bool(st.get("merk")), inBez=st.get("bez", True),
                       inNotes=st.get("notizen", True), status=STATUS_CHOICES.get(st.get("status"), "aktiv"),
                       version=versions.get(st.get("version"), 0), ctype=TYPE_CHOICES.get(st.get("typ")) or "",
                       hersteller=st.get("hersteller", ""), kategorie=st.get("kategorie") or "")
        if not self.core.tree.select_key(st.get("bereich") or {}, refresh=False):
            self.core.tree.select("all", refresh=False)
        self.refresh()

    @Slot()
    def saveSearch(self):
        def save(name):
            try:
                if self.core.persist(self.core.store.save_search, name, self._search_state()) is not None:
                    self.core.toast(f"Suche „{name}“ gespeichert")
                    self.changed.emit()
            except ValueError as exc:
                self.core.info("Suche speichern", str(exc))

        self.core.prompt("Suche speichern", "Name der Suche (nur für Sie):", save,
                         placeholder="z. B. Rollatoren mit Sitz")

    @Slot(str)
    def deleteSaved(self, name):
        def delete():
            self.core.persist(self.core.store.delete_search, name)
            self.changed.emit()

        self.core.confirm("Gespeicherte Suche löschen", f"Suche „{html.escape(name)}“ löschen?", delete, yes="Löschen")

    # ------------------------------------------------------------------ Springen
    def open_product(self, nummer):
        """Produkt direkt öffnen: Filter auf diese Nummer, Zeile auswählen."""
        self.core.goto(0)
        self.extra_nummern = (nummer,)
        self.st.update(text="", status="alle")
        self.core.tree.select("all", refresh=False)
        self.refresh(keep=nummer)

    def search_line(self, key, value):
        """Merkmal-Zeile aus den Details als genaue Phrase ins Suchfeld (Suche in Merkmalen)."""
        self.core.goto(0)
        self.extra_nummern = None
        self.st.update(inMerk=True, text='"' + f"{key}: {value}".replace('"', " ") + '"')
        self.core.tree.select("all", refresh=False)
        self.refresh()
        self.core.toast(f"Alle Produkte mit „{key}: {value}“")

    @Slot()
    def showFavorites(self):
        self.core.goto(0)
        self.core.tree.select("fav")

    @Slot()
    def showRecent(self):
        self.core.goto(0)
        self.core.tree.select("recent")

    def filter_hersteller(self, name):
        self.st.update(text="", hersteller=name)
        self.core.tree.select("all", refresh=False)
        self.refresh()

    # ------------------------------------------------------------------ Nummernliste einfügen
    @Slot(result=str)
    def clipboardNumbers(self):
        text = QGuiApplication.clipboard().text()
        return text if parse_numbers(text) else ""

    @Slot(str, result="QVariantMap")
    def checkNumbers(self, text):
        nums = parse_numbers(text)
        found = {r["nummer"]: r["active"] for r in self.core.conn.execute(
            "SELECT nummer, active FROM produkt WHERE nummer IN (SELECT value FROM json_each(?))", (json.dumps(nums),))}
        active = [n for n in nums if found.get(n) == 1]
        removed = [n for n in nums if found.get(n) == 0]
        unknown = [n for n in nums if n not in found]
        danger, muted = self.core.theme.get("danger"), self.core.theme.get("muted")
        info = f"<b>{len(nums)}</b> Nummern erkannt: <b>{len(active)}</b> aktiv"
        if removed:
            info += f", <span style='color:{danger}'><b>{len(removed)}</b> entfernt</span>"
        if unknown:
            shown = ", ".join(format_nummer(u) for u in unknown[:12])
            info += (f", <span style='color:{danger}'><b>{len(unknown)}</b> unbekannt</span><br>"
                     f"<span style='color:{muted}'>Unbekannt: {shown}{' …' if len(unknown) > 12 else ''}</span>")
        return {"html": info, "found": active + removed}

    @Slot("QVariantList")
    def pasteShow(self, found):
        found = [str(n) for n in found]
        self.core.goto(0)
        self.st.update(status="alle", text="")
        self.core.tree.select("all", refresh=False)
        self.extra_nummern = tuple(found)
        self.refresh()
        self.core.toast(f"{len(found)} Produkte aus der eingefügten Liste – „Filter zurücksetzen“ hebt das auf")

    @Slot("QVariantList")
    def pasteAdd(self, found):
        found = [str(n) for n in found]
        self.core.lists_ctl.open_add(found, f"{len(found)} eingefügte Nummern")
