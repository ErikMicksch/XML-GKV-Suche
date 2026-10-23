"""Meine Favoriten, private Listen (Favoriten-Datei) und gemeinsame Listen (Datenbank).

container = ("fav", None) | ("pliste", id) | ("liste", id)
"""
from __future__ import annotations

import html

from PySide6.QtCore import QObject, Property, Signal, Slot

from hmv_viewer import queries
from hmv_viewer.gui import _dots, _key_tuple, _when
from hmv_viewer.model import format_nummer

from .models import DictModel


class Lists(QObject):
    changed = Signal()
    addRequested = Signal("QVariantMap")    # Dialog „Zu Liste hinzufügen“ öffnen

    def __init__(self, core):
        super().__init__()
        self.core = core
        self.targets = DictModel(("cid", "label", "depth", "icon", "iconColor", "selectable"), self)
        self.last_target = "fav:"
        self._pending = None   # (keys, group)

    targetModel = Property(QObject, lambda self: self.targets, constant=True)
    lastTarget = Property(str, lambda self: self.last_target, notify=changed)

    # ------------------------------------------------------------------ Hilfen
    @staticmethod
    def cid(c):
        return f"{c[0]}:{'' if c[1] is None else c[1]}"

    @staticmethod
    def from_cid(cid):
        kind, _, lid = cid.partition(":")
        return kind, (None if lid == "" else int(lid) if kind == "liste" else lid)

    def name(self, c):
        kind, lid = c
        if kind == "fav":
            return "Meine Favoriten"
        if kind == "pliste":
            return self.core.store.plists.get(lid, {}).get("name", "?")
        r = self.core.lists.get(lid)
        return r["name"] if r else "?"

    def entries(self, c):
        kind, lid = c
        if kind == "fav":
            return list(self.core.store.favs)
        if kind == "pliste":
            return list(self.core.store.plists[lid]["items"])
        return [r[0] for r in self.core.conn.execute("SELECT nummer FROM liste_eintrag WHERE liste_id=?", (lid,))]

    def current_container(self):
        return self.core.tree.current_container()

    def star_for(self, nr):
        favs = self.core.store.favs
        if nr in favs:
            return "★"
        return "☆" if any(len(k) < 10 and nr.startswith(k) for k in favs) else ""

    # ------------------------------------------------------------------ anlegen, umbenennen, löschen
    def new_container(self, parent_c, select=True, done=None):
        kind, parent = parent_c
        kind = "pliste" if kind == "fav" else kind
        where = f" in „{self.name((kind, parent))}“" if parent is not None else ""
        hint = "für alle Benutzer sichtbar" if kind == "liste" else "nur für Sie sichtbar"

        def create(name):
            core = self.core
            if kind == "pliste":
                try:
                    lid = core.persist(core.store.create_plist, name, parent)
                except ValueError as exc:
                    core.info("Name bereits vergeben", str(exc), icon="alert")
                    return
            else:
                lid = core.list_db(queries.create_list, name, core.user, parent)
            if lid is None:
                return
            core.after_list_change()
            core.show_status(f"Liste „{name}“ angelegt" + (" – für alle sichtbar" if kind == "liste" else ""), 5000)
            if select:
                core.goto(0)
                core.tree.select_key({kind: lid})
            if done:
                done((kind, lid))

        self.core.prompt(f"Neue {'gemeinsame' if kind == 'liste' else 'private'} Liste{where}",
                         f"Name der Liste ({hint}):", create)

    @Slot(bool)
    def newList(self, shared):
        self.new_container(("liste" if shared else "pliste", None))

    def rename_container(self, c):
        kind, lid = c
        core = self.core

        def rename(name):
            if kind == "pliste":
                try:
                    ok = core.persist(core.store.rename_plist, lid, name)
                except ValueError as exc:
                    core.info("Name bereits vergeben", str(exc), icon="alert")
                    return
            else:
                ok = core.list_db(queries.rename_list, lid, name, core.user)
            if ok:
                core.after_list_change()

        core.prompt("Liste umbenennen", "Neuer Name:", rename, text=self.name(c))

    def delete_container(self, c):
        kind, lid = c
        core = self.core
        name = self.name(c)
        who = (f"für <b>ALLE</b> Benutzer (angelegt von {core.lists[lid]['created_by'] or '?'})" if kind == "liste"
               else "(nur Ihre private Liste)")

        def delete():
            ok = core.persist(core.store.delete_plist, lid) if kind == "pliste" else core.list_db(queries.delete_list, lid)
            if ok:
                core.after_list_change()
                core.show_status(f"Liste „{name}“ gelöscht", 5000)

        core.confirm("Liste löschen", f"Liste „{html.escape(name)}“ samt Unterlisten löschen {who}?", delete,
                     yes="Löschen", danger=True)

    # ------------------------------------------------------------------ hinzufügen / entfernen
    def open_add(self, keys, what, group=None):
        """Dialog „Zu Liste hinzufügen“. keys: feste Einträge; group: (Präfix, Filter, Anzahl) für eine Produktgruppe."""
        self._pending = (keys, group)
        self.fill_targets()
        n = len(keys or []) if group is None else group[2]
        self.addRequested.emit({"what": what, "isGroup": group is not None, "n": n, "nText": _dots(n)})

    def fill_targets(self):
        core = self.core
        rows = [{"cid": "fav:", "label": "Meine Favoriten", "depth": 0, "icon": "starFilled", "iconColor": "gold",
                 "selectable": True}]

        def add(kind, parent_id, depth):
            if kind == "pliste":
                items = sorted(((lid, v["name"]) for lid, v in core.store.plists.items() if v["parent"] == parent_id),
                               key=lambda r: r[1].casefold())
            else:
                items = [(lid, r["name"]) for lid, r in core.lists.items() if r["parent_id"] == parent_id]
            for lid, name in items:
                rows.append({"cid": self.cid((kind, lid)), "label": name, "depth": depth,
                             "icon": "star" if kind == "pliste" else "list",
                             "iconColor": "gold" if kind == "pliste" else "green", "selectable": True})
                add(kind, lid, depth + 1)

        add("pliste", None, 1)
        rows.append({"cid": "liste:", "label": "Gemeinsame Listen (für alle sichtbar)", "depth": 0, "icon": "list",
                     "iconColor": "green", "selectable": False})
        add("liste", None, 1)
        self.targets.set_rows(rows)
        if self.last_target not in {r["cid"] for r in rows if r["selectable"]}:
            self.last_target = "fav:"
        self.changed.emit()

    @Slot(str)
    def newTargetHere(self, cid):
        def created(c):
            self.last_target = self.cid(c)
            self.fill_targets()

        self.new_container(self.from_cid(cid or "fav:"), select=False, done=created)

    @Slot(str, bool)
    def acceptAdd(self, cid, whole_group):
        if self._pending is None:
            return
        keys, group = self._pending
        self._pending = None
        self.last_target = cid
        target = self.from_cid(cid)
        if group is None:
            self.add(target, keys)
            return
        k, f, n = group
        if whole_group:
            self.add(target, [k])
            return

        def add_all():
            self.add(target, [r["nummer"] for r in queries.iter_products(self.core.conn, f)])

        if n > 500:
            self.core.confirm("Viele Produkte", f"Wirklich {_dots(n)} Produkte einzeln zur Liste hinzufügen?", add_all,
                              yes="Hinzufügen")
        else:
            add_all()

    def add(self, c, keys, record=True):
        if c is None or not keys:
            return
        core = self.core
        kind, lid = c
        before = set(self.entries(c))
        if kind == "fav":
            n = core.persist(core.store.add, keys)
        elif kind == "pliste":
            n = core.persist(core.store.add_to_plist, lid, keys)
        else:
            n = core.list_db(queries.add_to_list, lid, keys, core.user)
        if n is None:
            return
        n = 0 if n is True else n
        added = [k for k in dict.fromkeys(keys) if k not in before]
        core.after_list_change()
        skipped = len(keys) - n
        what = "Gruppe" if len(keys) == 1 and len(keys[0]) < 10 else f"{n} Eintrag/Einträge"
        msg = f"{what} zu „{self.name(c)}“ hinzugefügt" + (f" ({skipped} waren schon drin)" if skipped else "")
        if record and added:
            core.push_undo(msg, lambda: self.remove(c, added, record=False))
        else:
            core.toast(msg)

    def remove(self, c, keys, record=True):
        core = self.core
        kind, lid = c
        direct = set(self.entries(c))
        keys = [k for k in keys if k in direct]   # über eine Gruppe enthaltene Produkte lassen sich nicht einzeln entfernen
        if kind == "fav":
            for k in keys:
                core.store.favs.pop(k, None)
            n = None if core.persist(core.store.save) is None else len(keys)
        elif kind == "pliste":
            n = core.persist(core.store.remove_from_plist, lid, keys)
        else:
            n = core.list_db(queries.remove_from_list, lid, keys, core.user)
        if n is None:
            return
        n = 0 if n is True else n
        core.after_list_change()
        msg = f"{n} Eintrag/Einträge aus „{self.name(c)}“ entfernt"
        if record and keys:
            core.push_undo(msg, lambda: self.add(c, keys, record=False))
        else:
            core.toast(msg)

    def remove_selected_from_current(self, sel):
        c = self.current_container()
        direct = set(self.entries(c))
        via_group = [k for k in sel if k not in direct]
        self.remove(c, sel)
        if via_group:
            self.core.info("Über Gruppe enthalten", f"{len(via_group)} Produkt(e) gehören über eine ganze Produktgruppe zur "
                           "Liste und wurden nicht entfernt. Entfernen Sie dafür die Gruppe (Rechtsklick links im Baum).")

    # ------------------------------------------------------------------ Favoriten
    def toggle_fav(self, k, record=True):
        core = self.core
        if core.persist(core.store.toggle, k) is None:
            return
        added = k in core.store.favs
        if len(k) == 10:
            label = format_nummer(k)
        else:
            node = core.node_by_key.get(_key_tuple(queries.key_from_prefix(k)))
            label = (node["label"] if node else k) + " (ganze Gruppe)"
        msg = f"{label} {'als Favorit gemerkt' if added else 'aus den Favoriten entfernt'}"
        core.after_list_change()
        if record:
            core.push_undo(msg, lambda: self.toggle_fav(k, record=False))
        else:
            core.toast(msg)

    # ------------------------------------------------------------------ gemeinsame Listen: Verlauf, Abo
    def show_log(self, lid):
        rows = queries.list_log(self.core.conn, lid)
        c = self.core.theme.colors
        body = "".join(f"<tr><td style='color:{c['muted']}'>{_when(r['at'])}</td><td><b>{html.escape(r['user'] or '?')}</b>"
                       f"</td><td>{html.escape(r['aktion'])}</td><td>{html.escape(r['detail'] or '')}</td></tr>" for r in rows)
        self.core.info(f"Verlauf: {self.core.lists[lid]['name']}",
                       f"<table cellpadding='5' width='100%'>{body or '<tr><td>Noch keine Einträge.</td></tr>'}</table>",
                       wide=True, icon="history")

    def toggle_abo(self, lid):
        core = self.core
        if core.persist(core.store.toggle_abo, lid) is None:
            return
        core.tree.refresh_collections()
        core.toast(f"„{core.lists[lid]['name']}“ " + ("abonniert – Sie werden beim Start über Änderungen informiert"
                                                      if lid in core.store.abos else "nicht mehr abonniert"))
