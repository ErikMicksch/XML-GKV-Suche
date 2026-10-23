"""Startseite, Versionen und „Änderungen anderer“."""
from __future__ import annotations

import datetime as dt
import sqlite3

from PySide6.QtCore import QObject, Property, Signal, Slot

from hmv_viewer import queries
from hmv_viewer.gui import TYPE_CHOICES, _clean, _dots, _when, _who, fmt_date
from hmv_viewer.model import CHANGE_LABELS, ENTFERNT, GEAENDERT, NEU, REAKTIVIERT, UMGRUPPIERT, format_nummer
from hmv_viewer.queries import ProductFilter

from .models import DictModel
from .tree import count_label

TABLE_ROLES = ("idx", "c", "bg", "selected", "tips", "icon", "iconColor")


class Dashboard(QObject):
    changed = Signal()

    def __init__(self, core):
        super().__init__()
        self.core = core
        self.recent = DictModel(("aid", "text", "icon"), self)
        self.lists = DictModel(("aid", "text", "icon"), self)
        self._d = {}

    recentModel = Property(QObject, lambda self: self.recent, constant=True)
    listsModel = Property(QObject, lambda self: self.lists, constant=True)
    data = Property("QVariantMap", lambda self: dict(self._d), notify=changed)

    def refresh(self):
        core = self.core
        if core.store is None or core.names is None:
            return
        hour = dt.datetime.now().hour
        greet = "Guten Morgen" if hour < 11 else "Guten Tag" if hour < 18 else "Guten Abend"
        total = queries.count_products(core.conn, ProductFilter(status="aktiv"))
        versions = queries.list_versions(core.conn)
        n_fav = queries.count_products(core.conn, ProductFilter(status="aktiv", favoriten=True))
        prods = core.products
        tiles = [{"title": "Produkte im Verzeichnis", "icon": "box", "value": _dots(total),
                  "sub": f"{len(core.hier_data)} Produktgruppen", "aid": core.act(lambda: (core.goto(0), prods.resetFilter()))},
                 {"title": "Letzter Import", "icon": "import", "value": f"V{versions[0]['id']}" if versions else "–",
                  "sub": (f"{_when(versions[0]['imported_at'])} · {versions[0]['n_new']} neu, {versions[0]['n_changed']} geändert,"
                          f" {versions[0]['n_removed']} entfernt") if versions else "Noch kein Import",
                  "aid": core.act(lambda: core.goto(1))},
                 {"title": "Meine Favoriten", "icon": "starFilled", "value": _dots(n_fav),
                  "sub": f"{len(core.store.plists)} private Listen · {count_label(core.store.favs)} gemerkt",
                  "aid": core.act(prods.showFavorites)},
                 {"title": "Gemeinsame Listen", "icon": "list", "value": str(len(core.lists)),
                  "sub": f"{len(core.store.abos)} abonniert", "aid": core.act(lambda: (core.goto(0), core.tree.select("lists")))}]
        theme = core.theme
        bars = []
        for v in reversed(versions[:12]):
            if v["id"] == core.first_id:
                continue
            segs = [{"value": v[k], "color": theme.tag(t), "label": CHANGE_LABELS[t]} for k, t in (
                ("n_new", NEU), ("n_changed", GEAENDERT), ("n_reactivated", REAKTIVIERT), ("n_regrouped", UMGRUPPIERT),
                ("n_removed", ENTFERNT))]
            bars.append({"label": f"V{v['id']}", "segments": segs, "total": sum(s["value"] for s in segs),
                         "aid": core.act(lambda vid=v["id"]: core.versions.select_id(vid))})
        legend = [{"label": CHANGE_LABELS[t], "color": theme.tag(t)} for t in (NEU, GEAENDERT, REAKTIVIERT, UMGRUPPIERT,
                                                                                ENTFERNT)]
        self._d = {"greeting": f"{greet}, {core.user}", "tiles": tiles, "bars": bars, "legend": legend,
                   "maxBar": max([b["total"] for b in bars] + [1])}
        rows = []
        for nr in core.recent[:8]:
            p = queries.get_product(core.conn, nr)
            if p:
                rows.append({"aid": core.act(lambda nr=nr: prods.open_product(nr)), "icon": "box",
                             "text": f"{format_nummer(nr)}  {p['bezeichnung'] or ''}"})
        self.recent.set_rows(rows)
        self.lists.set_rows([{"aid": core.act(lambda lid=r["id"]: core.detail.link(f"liste:{lid}")),
                              "icon": "bell" if r["id"] in core.store.abos else "list",
                              "text": f"{r['name']}  ·  {_who(r)}"} for r in queries.recent_lists(core.conn)])
        self.changed.emit()


class Versions(QObject):
    changed = Signal()

    def __init__(self, core):
        super().__init__()
        self.core = core
        self.versions = DictModel(TABLE_ROLES, self)
        self.changes = DictModel(TABLE_ROLES, self)
        self.ids, self.change_rows = [], []
        self.current = None
        self.ctype = ""
        self._note = ""

    versionModel = Property(QObject, lambda self: self.versions, constant=True)
    changeModel = Property(QObject, lambda self: self.changes, constant=True)
    note = Property(str, lambda self: self._note, notify=changed)
    title = Property(str, lambda self: f"Änderungen in V{self.current}" if self.current else "Änderungen der Version",
                     notify=changed)
    typeOptions = Property("QVariantList", lambda self: [{"value": v or "", "text": k} for k, v in TYPE_CHOICES.items()],
                           constant=True)
    typeValue = Property(str, lambda self: self.ctype, notify=changed)
    versionColumns = Property("QVariantList", lambda self: [
        {"key": k, "title": t, "width": w} for k, t, w in (
            ("id", "Version", 80), ("imported", "Importiert am", 160), ("stand", "Stand-Datum", 120),
            ("logisch", "Log. Version", 110), ("total", "Produkte", 100), ("neu", "Neu", 70), ("geaendert", "Geändert", 90),
            ("entfernt", "Entfernt", 90), ("wieder", "Wieder aufgen.", 130), ("umgr", "Umgruppiert", 120),
            ("stamm", "Änd. Stammdaten", 150), ("quelle", "Quelle", 320))], constant=True)
    changeColumns = Property("QVariantList", lambda self: [
        {"key": k, "title": t, "width": w} for k, t, w in (
            ("typ", "Änderung", 150), ("ebene", "Ebene", 130), ("nummer", "Nummer", 140), ("name", "Bezeichnung", 480),
            ("felder", "Geänderte Felder", 300))], constant=True)

    def load(self):
        versions = queries.list_versions(self.core.conn)
        self.ids = [v["id"] for v in versions]
        self.versions.set_rows([{"idx": i, "selected": False, "bg": "", "tips": {}, "icon": "", "iconColor": "",
                                 "c": {"id": f"V{v['id']}", "imported": (v["imported_at"] or "").replace("T", " "),
                                       "stand": fmt_date(v["source_date"]), "logisch": v["logische_version"] or "",
                                       "total": _dots(v["n_total"]), "neu": str(v["n_new"]), "geaendert": str(v["n_changed"]),
                                       "entfernt": str(v["n_removed"]), "wieder": str(v["n_reactivated"]),
                                       "umgr": str(v["n_regrouped"]), "stamm": str(v["n_stamm_changes"]),
                                       "quelle": v["source_name"] or ""}} for i, v in enumerate(versions)])
        if versions:
            self.select(self.ids.index(self.current) if self.current in self.ids else 0)
        else:
            self.current = None
            self.changes.set_rows([])
            self._note = "Noch keine Version importiert."
            self.changed.emit()

    @Slot(int)
    def select(self, i):
        if not 0 <= i < len(self.ids):
            return
        self.current = self.ids[i]
        for k, r in enumerate(self.versions.rows):
            if r["selected"] != (k == i):
                self.versions.update_row(k, selected=k == i)
        self._load_changes()

    def select_id(self, vid):
        self.core.goto(1)
        if vid in self.ids:
            self.select(self.ids.index(vid))

    @Slot(str)
    def setType(self, ctype):
        self.ctype = ctype
        self._load_changes()

    def _load_changes(self):
        core, vid, limit = self.core, self.current, 5000
        ctype = self.ctype or None
        total = queries.count_changes(core.conn, vid, ctype)
        self.change_rows = queries.version_changes(core.conn, vid, ctype, limit)
        self.changes.set_rows([{"idx": i, "selected": False, "bg": core.theme.tag(r["change_type"]), "tips": {},
                                "icon": "", "iconColor": "",
                                "c": {"typ": CHANGE_LABELS.get(r["change_type"], r["change_type"]), "ebene": r["entity_label"],
                                      "nummer": r["display_k"], "name": r["name"], "felder": r["fields"]}}
                               for i, r in enumerate(self.change_rows)])
        note = f"{_dots(total)} Einträge"
        if vid == core.first_id:
            note += "  (Erstimport: alle Produkte gelten als „Neu“)"
        if total > limit:
            note += f"  –  angezeigt werden die ersten {_dots(limit)}"
        self._note = note
        self.changed.emit()

    @Slot()
    def showInProducts(self):
        if self.current is None:
            return
        prods = self.core.products
        prods.st.update(version=self.current, ctype=self.ctype, status="alle", text="")
        self.core.goto(0)
        prods.refresh()

    @Slot(int)
    def openChange(self, i):
        r = self.change_rows[i] if 0 <= i < len(self.change_rows) else None
        if not r or r["entity"] != "PRODUKT":
            return
        prods = self.core.products
        prods.st.update(version=self.current, ctype="", status="alle", text=r["display_k"])
        self.core.goto(0)
        prods.refresh(keep=r["k"])


class Activity(QObject):
    changed = Signal()
    PERIODS = (("Letzte 7 Tage", 7), ("Letzte 30 Tage", 30), ("Letzte 90 Tage", 90), ("Alles", 0))

    def __init__(self, core):
        super().__init__()
        self.core = core
        self.model = DictModel(TABLE_ROLES, self)
        self.rows = []
        self.days, self.kind, self.user, self.mine = 30, "", "", False
        self._badge = 0
        self._empty = {}

    modelObj = Property(QObject, lambda self: self.model, constant=True)
    badge = Property(int, lambda self: self._badge, notify=changed)
    empty = Property("QVariantMap", lambda self: dict(self._empty), notify=changed)
    info = Property(str, lambda self: f"{len(self.rows)} Einträge", notify=changed)
    state = Property("QVariantMap", lambda self: {"days": self.days, "kind": self.kind, "user": self.user,
                                                  "mine": self.mine}, notify=changed)
    periodOptions = Property("QVariantList", lambda self: [{"value": d, "text": t} for t, d in self.PERIODS], constant=True)
    kindOptions = Property("QVariantList", lambda self: [{"value": "", "text": "Alle Arten"}] + [
        {"value": k, "text": t} for k, t in queries.ACTIVITY_KINDS.items()], constant=True)
    columns = Property("QVariantList", lambda self: [
        {"key": k, "title": t, "width": w} for k, t, w in (
            ("at", "Zeitpunkt", 160), ("user", "Benutzer", 130), ("art", "Art", 190), ("nummer", "Hilfsmittelnummer", 160),
            ("name", "Bezeichnung", 320), ("detail", "Inhalt", 460))], constant=True)

    @Property("QVariantList", notify=changed)
    def userOptions(self):
        core = self.core
        names = [n for n in queries.list_users(core.conn) if self.mine or n != core.user] if core.store else []
        return [{"value": "", "text": "Alle Benutzer" if self.mine else "Alle anderen"}] + [
            {"value": n, "text": n} for n in names]

    @Slot(str, "QVariant")
    def set(self, key, value):
        setattr(self, key, value)
        self.refresh()

    def refresh(self, mark_seen=False):
        core = self.core
        if core.store is None:
            return
        since = (dt.datetime.now() - dt.timedelta(days=self.days)).isoformat(timespec="seconds") if self.days else ""
        self.rows = queries.others_activity(core.conn, None if self.mine else core.user, since, self.kind or None,
                                            self.user or None)
        icons = {"kommentar": "comment", "kategorie": "tag", "liste": "list"}
        out = []
        for i, a in enumerate(self.rows):
            detail = (f"eingefärbt: {a['detail']}" if a["detail"] else "Farbmarkierung entfernt") \
                if a["art"] == "kategorie" else a["detail"] or ""
            out.append({"idx": i, "selected": False, "bg": "", "tips": {"detail": detail},
                        "icon": icons.get(a["art"], ""), "iconColor": a["farbe"] or core.theme.get("green"),
                        "c": {"at": _when(a["at"]), "user": a["user"] or "?",
                              "art": queries.ACTIVITY_KINDS.get(a["art"], a["art"]),
                              "nummer": format_nummer(a["nummer"]) if a["nummer"] else "", "name": a["bezeichnung"] or "",
                              "detail": _clean(detail)}})
        self.model.set_rows(out)
        self._update_empty(since)
        if mark_seen:
            core.settings.setValue("aktivitaet_gesehen", dt.datetime.now().isoformat(timespec="seconds"))
        self.update_badge()

    def _update_empty(self, since):
        core = self.core
        if self.rows:
            self._empty = {}
            return
        own = 0 if self.mine else len(queries.others_activity(core.conn, None, since, self.kind or None, core.user,
                                                              limit=1000))
        others = [n for n in queries.list_users(core.conn) if n != core.user]
        title, text, action = "Keine Einträge im gewählten Zeitraum", "", ""
        if own:
            title = "Keine Änderungen anderer Benutzer"
            text = (f"Alle {own} Einträge in diesem Zeitraum stammen von Ihnen ({core.user}) und werden hier "
                    "ausgeblendet.")
            action = "Eigene Änderungen anzeigen"
        elif not self.mine:
            text = "Hier erscheint, was andere kommentieren, farblich markieren oder an gemeinsamen Listen ändern."
        if not others:
            text += (" Bisher ist nur ein Benutzer angelegt. Sobald Kolleginnen und Kollegen mit ihrem Namen arbeiten, "
                     "erscheinen ihre Änderungen hier.")
        self._empty = {"icon": "comment", "title": title, "text": text.strip(), "actionText": action}

    @Slot()
    def showMine(self):
        self.set("mine", True)

    def update_badge(self):
        try:
            self._badge = len(queries.others_activity(self.core.conn, self.core.user,
                                                      self.core.settings.value("aktivitaet_gesehen") or "", limit=100))
        except sqlite3.OperationalError:
            return
        self.changed.emit()

    @Slot(int)
    def open(self, i):
        a = self.rows[i] if 0 <= i < len(self.rows) else None
        if a is None:
            return
        if a["nummer"]:
            self.core.products.open_product(a["nummer"])
        elif a["liste_id"]:
            self.core.detail.link(f"liste:{a['liste_id']}")
