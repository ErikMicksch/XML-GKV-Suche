"""Baum links: Zuletzt angesehen, Meine Favoriten (mit privaten Listen), Gemeinsame Listen, Alle Produkte (Hierarchie).

Für QML als flache Liste (Einrückung = depth); Auf-/Zuklappen fügt Zeilen ein bzw. entfernt sie (Bildlauf bleibt).
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Property, Signal, Slot

from hmv_viewer import queries
from hmv_viewer.gui import _dots, _key_tuple, _who, fmt_date, prune
from hmv_viewer.queries import ProductFilter

from .core import SEP, entry
from .models import DictModel

ROLES = ("nid", "depth", "label", "countText", "icon", "iconColor", "bold", "hasChildren", "expanded", "selected",
         "tip", "droppable", "labelColor")


def count_label(keys):
    n_p = sum(len(k) == 10 for k in keys)
    n_g = sum(len(k) < 10 for k in keys)
    return f"{n_p} Produkte" + (f", {n_g} Gruppe{'n' if n_g != 1 else ''}" if n_g else "")


def _kstr(key):
    return "".join(f"{c[0]}{key[c]}" for c in ("gruppe", "ort", "untergruppe", "art") if c in key)


def _node(nid, label, count="", icon="", color="muted", bold=False, key=None, container=None, entry_=None,
          children=None, tip="", open_=False, label_color="text"):
    return {"nid": nid, "label": label, "count": count, "icon": icon, "color": color, "bold": bold,
            "key": key if key is not None else {}, "container": container, "entry": entry_, "children": children or [],
            "tip": tip, "open": open_, "label_color": label_color}


class Tree(QObject):
    changed = Signal()
    scrollTo = Signal(int)

    def __init__(self, core):
        super().__init__()
        self.core = core
        self.model = DictModel(ROLES, self)
        self.roots, self.by_id, self.parent_of = [], {}, {}
        self.state = {}            # nid -> aufgeklappt (überschreibt die Vorgabe)
        self.current = "all"
        self.term = ""

    modelObj = Property(QObject, lambda self: self.model, constant=True)
    filterText = Property(str, lambda self: self.term, notify=changed)
    currentLabel = Property(str, lambda self: self.label_of(self.current), notify=changed)
    currentId = Property(str, lambda self: self.current, notify=changed)

    # ------------------------------------------------------------------ Aufbau
    def _hier(self, nodes, prefix, color="muted"):
        out = []
        for n in nodes:
            nid = f"{prefix}/{_kstr(n['key'])}"
            out.append(_node(nid, n["label"], f"({n['count']})", key=n["key"], children=self._hier(n["children"], nid),
                             tip=n["label"], open_=n.get("open", False)))
        return out

    def _containers(self, kind, parent_id, prefix):
        core = self.core
        if kind == "pliste":
            rows = sorted(((lid, v["name"], v["items"]) for lid, v in core.store.plists.items() if v["parent"] == parent_id),
                          key=lambda r: r[1].casefold())
        else:
            rows = [(lid, r["name"], None) for lid, r in core.lists.items() if r["parent_id"] == parent_id]
        out = []
        for lid, name, items in rows:
            nid = f"{prefix}/{kind}:{lid}"
            if items is None:
                groups = queries.list_groups(core.conn, lid)
                r = core.lists[lid]
                label = f"{r['n']} Produkte" + (f", {len(groups)} Gruppe{'n' if len(groups) != 1 else ''}" if groups else "")
                tip = (f"Gemeinsame Liste · angelegt von {r['created_by'] or '?'} am {fmt_date(r['created_at'])}"
                       f" · zuletzt geändert: {_who(r)}")
                abo = lid in core.store.abos
                icon, color = ("bell", "gold") if abo else ("list", "green")
                tip += " · abonniert" if abo else ""
            else:
                groups = [k for k in items if len(k) < 10]
                label, tip, icon, color = count_label(items), "Private Liste · nur für Sie sichtbar", "star", "gold"
            children = self._containers(kind, lid, nid) + self._groups(nid, (kind, lid), groups)
            out.append(_node(nid, name, f"({label})", icon, color, key={kind: lid}, container=(kind, lid),
                             children=children, tip=tip + " · Rechtsklick: Unterliste, umbenennen, löschen", open_=True))
        return out

    def _groups(self, prefix, container, keys):
        """Als ganze Gruppe eingetragene Präfixe als aufklappbaren Hierarchie-Baum."""
        out = []
        for k in sorted(k for k in keys if len(k) < 10):
            n = self.core.node_by_key.get(_key_tuple(queries.key_from_prefix(k)))
            nid = f"{prefix}/e:{k}"
            full = ".".join(part for part in (k[0:2], k[2:4], k[4:6], k[6:7]) if part)
            if n:
                node = _node(nid, f"{full} {n['label'].split(' ', 1)[-1]}", f"({n['count']})", key=n["key"],
                             children=self._hier(n["children"], nid))
            else:
                node = _node(nid, f"{k} (nicht mehr im Verzeichnis)", key=queries.key_from_prefix(k))
            node.update(entry=(container, k), label_color="green",
                        tip="Ganze Produktgruppe – neue Produkte der Gruppe gehören automatisch dazu")
            out.append(node)
        return out

    def rebuild(self):
        core = self.core
        store = core.store
        hier = prune(core.hier_data, self.term) if self.term else core.hier_data
        total = core.total_active
        recent = _node("recent", "Zuletzt angesehen", f"({len(core.recent)})", "history", key={"zuletzt": True},
                       tip="Ihre zuletzt geöffneten Produkte (max. 20)")
        fav = _node("fav", "Meine Favoriten", f"({count_label(store.favs)})", "starFilled", "gold", True,
                    key={"favoriten": True}, container=("fav", None), open_=True,
                    children=self._containers("pliste", None, "fav") + self._groups("fav", ("fav", None), store.favs),
                    tip="Nur für Sie: gemerkte Produkte, ganze Gruppen und private Listen · Rechtsklick: neue Liste")
        lists = _node("lists", "Gemeinsame Listen", f"({len(core.lists)})", "list", "green", True,
                      key={"listen_root": True}, open_=True, children=self._containers("liste", None, "lists"),
                      tip="Für alle Benutzer sichtbar · Rechtsklick: neue Liste")
        allp = _node("all", "Alle Produkte", f"({_dots(total)})", "box", "text", True, key={}, open_=True,
                     children=self._hier(hier, "all"))
        self.roots = [recent, fav, lists, allp]
        self.by_id, self.parent_of = {}, {}

        def index(nodes, parent):
            for n in nodes:
                self.by_id[n["nid"]] = n
                self.parent_of[n["nid"]] = parent
                index(n["children"], n["nid"])

        index(self.roots, None)
        if self.current not in self.by_id:
            self.current = "all"
        self.flatten()

    def _is_open(self, n):
        return self.state.get(n["nid"], n["open"]) if n["children"] else False

    def flatten(self):
        rows = []

        def walk(nodes, depth):
            for n in nodes:
                rows.append({"nid": n["nid"], "depth": depth, "label": n["label"], "countText": n["count"],
                             "icon": n["icon"], "iconColor": n["color"], "bold": n["bold"],
                             "hasChildren": bool(n["children"]), "expanded": self._is_open(n),
                             "selected": n["nid"] == self.current, "tip": n["tip"],
                             "droppable": n["container"] is not None, "labelColor": n["label_color"]})
                if self._is_open(n):
                    walk(n["children"], depth + 1)

        walk(self.roots, 0)
        self.model.sync(rows, "nid")
        self.changed.emit()

    def refresh_collections(self):
        """Favoriten/Listen neu aufbauen (auch Änderungen anderer); Auswahl und Aufklappzustand bleiben."""
        cur = self.current
        in_collections = cur.startswith(("fav", "lists"))
        self.rebuild()
        if in_collections and self.current != cur:   # Liste wurde (evtl. von jemand anderem) gelöscht
            self.select("all")

    def update_recent_count(self):
        self.by_id["recent"]["count"] = f"({len(self.core.recent)})"
        self.flatten()

    # ------------------------------------------------------------------ Auswahl
    def current_key(self):
        n = self.by_id.get(self.current)
        return dict(n["key"]) if n else {}

    def current_container(self):
        n = self.by_id.get(self.current)
        return n["container"] if n else None

    def label_of(self, nid):
        n = self.by_id.get(nid)
        return n["label"] if n else "Produkte"

    @Slot(str)
    def select(self, nid, refresh=True):
        n = self.by_id.get(nid)
        if n is None:
            return
        if n["key"].get("listen_root"):   # nur Ordner, kein Filter
            self.toggle(nid)
            return
        self.current = nid
        p = self.parent_of.get(nid)
        while p:   # Vorfahren aufklappen, damit die Auswahl sichtbar ist
            self.state[p] = True
            p = self.parent_of.get(p)
        self.flatten()
        idx = next((i for i, r in enumerate(self.model.rows) if r["nid"] == nid), -1)
        if idx >= 0:
            self.scrollTo.emit(idx)
        if refresh:
            self.core.products.on_area_changed()

    @Slot(str)
    def toggle(self, nid):
        n = self.by_id.get(nid)
        if n and n["children"]:
            self.state[nid] = not self._is_open(n)
            self.flatten()

    @Slot(int)
    def move(self, delta):
        rows = self.model.rows
        i = next((k for k, r in enumerate(rows) if r["nid"] == self.current), 0)
        j = i + delta
        while 0 <= j < len(rows) and rows[j]["nid"] == "lists":
            j += delta
        if 0 <= j < len(rows):
            self.select(rows[j]["nid"])

    @Slot(bool)
    def expandCurrent(self, on):
        n = self.by_id.get(self.current)
        if n is None:
            return
        if n["children"] and self._is_open(n) != on:
            self.toggle(self.current)
        elif not on and self.parent_of.get(self.current) not in (None, "lists"):
            self.select(self.parent_of[self.current])

    @Slot(str)
    def setFilter(self, text):
        self.term = text.strip().casefold()
        prev = self.current
        self.state = {k: v for k, v in self.state.items() if not k.startswith("all/")}   # Treffer aufklappen
        self.rebuild()
        if self.current != prev:
            self.core.products.on_area_changed()

    def nid_for_key(self, key):
        if key.get("zuletzt"):
            return "recent"
        if key.get("favoriten"):
            return "fav"
        if not key:
            return "all"
        if "pliste" in key or "liste" in key:
            return next((nid for nid, n in self.by_id.items() if n["key"] == key and n["container"]), None)
        parts, nid = [], "all"
        for c in ("gruppe", "ort", "untergruppe", "art"):
            if c in key:
                parts.append(c)
                nid += "/" + _kstr({p: key[p] for p in parts})
        return nid if nid in self.by_id else None

    def select_key(self, key, refresh=True):
        nid = self.nid_for_key(key)
        if nid is None and self.term:   # durch den Filter verborgen
            self.term = ""
            self.rebuild()
            nid = self.nid_for_key(key)
        if nid is not None:
            self.select(nid, refresh)
        return nid is not None

    # ------------------------------------------------------------------ Kontextmenü, Ziehen & Ablegen
    @Slot(str)
    def openMenu(self, nid):
        n = self.by_id.get(nid)
        if n is None or not n["key"] and nid == "all":   # „Alle Produkte“: zu groß für eine Liste
            return
        core, lists = self.core, self.core.lists_ctl
        key, c = n["key"], n["container"]
        items = []
        if key.get("listen_root"):
            items.append(entry("Neue gemeinsame Liste …", lambda: lists.new_container(("liste", None)), "plus"))
        elif c:
            kind, lid = c
            if kind == "fav":
                items.append(entry("Neue private Liste …", lambda: lists.new_container(("pliste", None)), "plus"))
            else:
                items += [entry("Unterliste anlegen …", lambda: lists.new_container(c), "plus"),
                          entry("Umbenennen …", lambda: lists.rename_container(c), "edit"),
                          entry("Löschen …", lambda: lists.delete_container(c), "trash")]
                if kind == "liste":
                    abo = lid in core.store.abos
                    items += [SEP, entry("Verlauf anzeigen …", lambda: lists.show_log(lid), "history"),
                              entry("Abo beenden" if abo else "Abonnieren (Hinweis bei Änderungen anderer)",
                                    lambda: lists.toggle_abo(lid), "bell")]
            entries = lists.entries(c)
            if entries:
                items += [SEP, entry(f"Inhalt in andere Liste kopieren …  ({count_label(entries)})",
                                     lambda: lists.open_add(entries, f"Inhalt von „{lists.name(c)}“"), "copy")]
        elif key and not key.get("zuletzt"):   # Produktgruppe / Ort / Untergruppe / Art (auch innerhalb einer Liste)
            k = queries.favorite_key(key)
            if n["entry"]:
                ec, ek = n["entry"]
                items += [entry(f"Aus „{lists.name(ec)}“ entfernen", lambda: lists.remove(ec, [ek]), "close"), SEP]
            items.append(entry("Ganze Gruppe aus Meine Favoriten entfernen" if k in core.store.favs
                               else "Ganze Gruppe zu Meine Favoriten", lambda: lists.toggle_fav(k), "star"))
            f = ProductFilter(status="aktiv", **{c2: key[c2] for c2 in ("gruppe", "ort", "untergruppe", "art") if c2 in key})
            count = queries.count_products(core.conn, f)
            items.append(entry("Zu Liste hinzufügen …  (ganze Gruppe oder einzelne Produkte)",
                               lambda: lists.open_add(None, n["label"], group=(k, f, count)), "list"))
        if items:
            core.popup_menu(items)

    @Slot(str, result=bool)
    def canDrop(self, nid):
        n = self.by_id.get(nid)
        return bool(n and n["container"])

    @Slot(str)
    def drop(self, nid):
        n = self.by_id.get(nid)
        if n and n["container"]:
            self.core.lists_ctl.add(n["container"], self.core.products.selected_nummern())
