"""Vergleich, Produktauswahl zum Vergleichen und Schnellzugriff (Strg+K)."""
from __future__ import annotations

from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtGui import QGuiApplication

from hmv_viewer import queries
from hmv_viewer.gui import fmt_date
from hmv_viewer.merkmale import parse_merkmale
from hmv_viewer.model import format_nummer
from hmv_viewer.queries import ProductFilter

from .models import DictModel

GENERAL = (("Hilfsmittelnummer", "nummer_fmt"), ("Bezeichnung", "bezeichnung"), ("Hersteller", "hersteller"),
           ("Produktart", None), ("Aufnahme", "aufnahme"), ("Status", "status"))


class Compare(QObject):
    changed = Signal()
    opened = Signal()

    def __init__(self, core):
        super().__init__()
        self.core = core
        self.products = []
        self.only_diff = False
        self._legend = ""

    headers = Property("QVariantList", lambda self: [p["nummer_fmt"] for p in self.products], notify=changed)
    onlyDiff = Property(bool, lambda self: self.only_diff, notify=changed)
    legend = Property(str, lambda self: self._legend, notify=changed)
    canAdd = Property(bool, lambda self: len(self.products) < 6, notify=changed)

    def _product(self, nr):
        row = dict(queries.get_product(self.core.conn, nr))
        row.update(nummer_fmt=format_nummer(nr), aufnahme=fmt_date(row["aufnahmedatum"]),
                   status=self.core.products.status_text(row))
        return row

    def _rows(self):
        """[(Abschnitt, Eigenschaft, Werte)] – Abschnitt nur in Abschnittszeilen gesetzt."""
        out = [("Allgemein", "", [])]
        for label, key in GENERAL:
            out.append(("", label, [self.core.names.path(p)["art"] if key is None else str(p.get(key) or "")
                                    for p in self.products]))
        merk = [parse_merkmale(p.get("merkmale")) for p in self.products]
        keys = []
        for m in merk:
            keys += [k for k in m if k not in keys]
        if keys:
            out.append(("Merkmale", "", []))
            out += [("", k, [m.get(k, "–") for m in merk]) for k in keys]
        return out

    @Property("QVariantList", notify=changed)
    def rows(self):
        rows = self._rows()
        if self.only_diff:
            rows = [r for r in rows if r[0] or len(set(r[2])) > 1]
        return [{"section": s, "label": l, "values": v, "differs": not s and len(set(v)) > 1} for s, l, v in rows]

    def open(self, nummern):
        self.products = [self._product(n) for n in nummern[:6]]
        self._update_legend()
        self.opened.emit()

    def compare_with(self, nummer):
        self.core.picker.pick([nummer], lambda picked: self.open([nummer] + picked))

    def _update_legend(self):
        n = sum(r["differs"] for r in self.rows)
        self._legend = f"{n} Eigenschaft(en) unterscheiden sich – farbig hinterlegt."
        self.changed.emit()

    @Slot(bool)
    def setOnlyDiff(self, on):
        self.only_diff = on
        self.changed.emit()

    @Slot()
    def add(self):
        have = [p["nummer"] for p in self.products]
        self.core.picker.pick(have, lambda picked: (self.products.extend(self._product(n) for n in picked),
                                                    self._update_legend()))

    @Slot()
    def copy(self):
        lines = ["\t".join(["Eigenschaft"] + [p["nummer_fmt"] for p in self.products])]
        for section, label, values in self._rows():
            lines.append(section if section else "\t".join([label] + [" ".join(v.split()) for v in values]))
        QGuiApplication.clipboard().setText("\n".join(lines))
        self._legend = "Vergleich als Tabelle kopiert – in Excel oder eine E-Mail einfügen."
        self.changed.emit()


class Picker(QObject):
    """Produkt(e) zum Vergleichen suchen und auswählen."""
    changed = Signal()
    opened = Signal()

    def __init__(self, core):
        super().__init__()
        self.core = core
        self.model = DictModel(("nummer", "text", "selected"), self)
        self.have, self.callback, self.base = [], None, None
        self._label, self._info = "", ""
        self.max_sel = 3

    modelObj = Property(QObject, lambda self: self.model, constant=True)
    label = Property(str, lambda self: self._label, notify=changed)
    info = Property(str, lambda self: self._info, notify=changed)
    maxSel = Property(int, lambda self: self.max_sel, notify=changed)
    selectedCount = Property(int, lambda self: sum(r["selected"] for r in self.model.rows), notify=changed)

    def pick(self, have, callback):
        self.have, self.callback = list(have), callback
        self.base = queries.get_product(self.core.conn, have[0])
        self._label = f"{format_nummer(have[0])} {self.base['bezeichnung'] or ''}"
        self.max_sel = max(1, 4 - len(have))
        self.search("")
        self.opened.emit()

    def _entries(self, rows):
        return [{"nummer": r["nummer"], "selected": False,
                 "text": f"{format_nummer(r['nummer'])}  {r['bezeichnung'] or ''}  ·  {r['hersteller'] or ''}"}
                for r in rows if r["nummer"] not in self.have]

    @Slot(str)
    def search(self, text):
        conn = self.core.conn
        if text.strip():
            rows = self._entries(queries.fetch_products(conn, ProductFilter(text=text, status="alle"), limit=80))
            self._info = f"{len(rows)} Treffer"
        else:
            b = self.base
            f = ProductFilter(status="aktiv", gruppe=b["gruppe"], ort=b["ort"], untergruppe=b["untergruppe"], art=b["art"])
            rows = self._entries([r for r in queries.fetch_products(conn, f, limit=300)
                                  if (r["bezeichnung"] or "").strip() != "Nicht besetzt"])   # HMV-Platzhalter
            self._info = f"Produkte derselben Produktart ({len(rows)})"
        self.model.set_rows(rows)
        self.changed.emit()

    @Slot(int)
    def toggle(self, i):
        r = self.model.rows[i]
        if r["selected"] or self.selectedCount < self.max_sel:
            self.model.update_row(i, selected=not r["selected"])
            self.changed.emit()

    @Slot()
    def accept(self):
        picked = [r["nummer"] for r in self.model.rows if r["selected"]][:self.max_sel]
        if picked and self.callback:
            self.callback(picked)


class Palette(QObject):
    """Schnellzugriff: Funktionen, Produkte, Gruppen und Listen per Suche."""

    def __init__(self, core):
        super().__init__()
        self.core = core

    @Slot(str, result="QVariantList")
    def items(self, text):
        core = self.core
        prods, maint, lists = core.products, core.maint, core.lists_ctl
        term = text.strip().casefold()
        actions = [("search", "Produkte durchsuchen", "Strg+F", lambda: core.requestFocus("search")),
                   ("home", "Startseite", "Strg+0", lambda: core.goto(2)),
                   ("starFilled", "Meine Favoriten", "Strg+B", prods.showFavorites),
                   ("history", "Zuletzt angesehen", "", prods.showRecent),
                   ("paste", "Nummernliste einfügen", "Strg+Umschalt+V", maint.openPaste),
                   ("import", "Importieren", "Strg+I", maint.start_import),
                   ("export", "Excel-Export", "Strg+E", maint.startExport),
                   ("plus", "Neue private Liste", "", lambda: lists.new_container(("pliste", None))),
                   ("plus", "Neue gemeinsame Liste", "", lambda: lists.new_container(("liste", None))),
                   ("bell", "Was ist neu?", "", lambda: maint.whats_new(auto=False)),
                   ("tag", "Farbkategorien verwalten", "", maint.openCategories),
                   ("settings", "Einstellungen", "", maint.openSettings),
                   ("save", "Datenbank sichern", "", maint.backup),
                   ("info", "Info & Support", "", maint.info),
                   ("history", "Versionen & Änderungen", "Strg+2", lambda: core.goto(1)),
                   ("comment", "Änderungen anderer", "Strg+3", lambda: core.goto(3))]
        actions += [("palette", f"Design: {n}", "", lambda n=n: core.theme.setTheme(n)) for n in core.theme.names]
        out = [{"icon": i, "text": t, "sub": s, "aid": core.act(fn)} for i, t, s, fn in actions
               if not term or term in t.casefold()]
        if not term:
            for nr in core.recent[:8]:
                out.append({"icon": "history", "text": format_nummer(nr), "sub": "zuletzt angesehen",
                            "aid": core.act(lambda nr=nr: prods.open_product(nr))})
            return out
        hits = queries.fetch_products(core.conn, ProductFilter(text=text, status="alle"), limit=15)
        if len(hits) < 15 and prods.st["inMerk"]:
            seen = {r["nummer"] for r in hits}
            hits += [r for r in queries.fetch_products(core.conn, ProductFilter(text=text, status="alle", in_merkmale=True),
                                                       limit=30) if r["nummer"] not in seen][:15 - len(hits)]
        for r in hits:
            out.append({"icon": "box", "text": f"{format_nummer(r['nummer'])}  {r['bezeichnung'] or ''}",
                        "sub": r["hersteller"] or "", "aid": core.act(lambda nr=r["nummer"]: prods.open_product(nr))})
        for n in [n for n in core.node_by_key.values() if term in n["label"].casefold()][:10]:
            out.append({"icon": "list", "text": n["label"], "sub": "Produktgruppe",
                        "aid": core.act(lambda key=n["key"]: (core.goto(0), core.tree.select_key(key)))})
        for lid, v in core.store.plists.items():
            if term in v["name"].casefold():
                out.append({"icon": "star", "text": v["name"], "sub": "meine Liste",
                            "aid": core.act(lambda lid=lid: core.detail.link(f"pliste:{lid}"))})
        for lid, r in core.lists.items():
            if term in r["name"].casefold():
                out.append({"icon": "list", "text": r["name"], "sub": "gemeinsame Liste",
                            "aid": core.act(lambda lid=lid: core.detail.link(f"liste:{lid}"))})
        return out
