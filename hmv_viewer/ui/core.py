"""Gemeinsamer Zustand: Datenbank, Favoriten-Datei, Benutzer, Dialoge (asynchron in QML), Menüs, Rückgängig."""
from __future__ import annotations

import datetime as dt
import getpass
import itertools
import sqlite3
from pathlib import Path

from PySide6.QtCore import QObject, Property, QSettings, QStandardPaths, QTimer, Signal, Slot
from PySide6.QtWidgets import QFileDialog

from hmv_viewer import db, queries
from hmv_viewer.favorites import FILE_NAME, FavoriteStore, legacy_db_keys
from hmv_viewer.queries import ProductFilter
from hmv_viewer.gui import _key_tuple

def qml_settings():
    """Einstellungen je Windows-Benutzer (HKCU\\Software\\HMV-Viewer\\HMV-Viewer) – keine Adminrechte nötig."""
    return QSettings("HMV-Viewer", "HMV-Viewer")


def flag(settings, key, default):
    return str(settings.value(key, default)).lower() in ("true", "1")


def entry(text, fn=None, icon="", enabled=True, children=None):
    """Menüeintrag für ActionMenu.qml (fn wird beim Aufbau in core.act registriert)."""
    return {"text": text, "fn": fn, "icon": icon, "enabled": enabled and (fn is not None or bool(children)),
            "children": children or [], "separator": False}


SEP = {"separator": True, "text": "", "icon": "", "enabled": False, "children": []}


class Core(QObject):
    changed = Signal()
    toastRequested = Signal(str, str, int)        # Text, Aktion („Rückgängig“), Aktions-id (-1 = keine)
    dialogRequested = Signal("QVariantMap")
    focusRequested = Signal(str)                  # search | note | tree | hersteller | table
    menuRequested = Signal("QVariantList")        # Kontextmenü an der Mausposition

    def __init__(self, db_path, settings=None, fav_dir=None, user=None):
        super().__init__()
        self.db_path = str(db_path)
        self.settings = settings or qml_settings()
        self.conn = db.connect(self.db_path)
        self.read_only = db.is_read_only(self.db_path)
        self.store = None
        self.user = None
        self.names = None
        self.first_id = self.latest_id = None
        self.lists = {}
        self.hier_data, self.node_by_key = [], {}
        self.comment_info = {}
        self.total_active = 0
        self.recent = self._load_recent()
        self.last_open = self.settings.value("zuletzt_geoeffnet")
        self._fav_dir_arg, self._user_arg = fav_dir, user
        self._ids = itertools.count(1)
        self._actions = {}
        self._pending = {}
        self._undo = []
        self._page = 2
        self._setup = False
        self._status = ""
        self.auto_answer = None   # Tests: fn(spec) -> (Knopf, Text) statt Dialog
        self.status_timer = QTimer(self, singleShot=True, timeout=lambda: self._set_status(""))
        # Bereiche (werden in app.py gesetzt)
        self.theme = self.products = self.tree = self.detail = self.lists_ctl = None
        self.dash = self.versions = self.activity = self.maint = None

    # ------------------------------------------------------------------ Eigenschaften für QML
    page = Property(int, lambda self: self._page, notify=changed)
    setupNeeded = Property(bool, lambda self: self._setup, notify=changed)
    userName = Property(str, lambda self: self.user or "", notify=changed)
    readOnly = Property(bool, lambda self: self.read_only, constant=True)
    status = Property(str, lambda self: self._status, notify=changed)
    dbPath = Property(str, lambda self: self.db_path, constant=True)
    favPath = Property(str, lambda self: str(self.store.path) if self.store else "", notify=changed)
    defaultFolder = Property(str, lambda self: self.settings.value("favoriten_ordner") or str(
        Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)) / "HMV-Viewer"),
        constant=True)
    defaultName = Property(str, lambda self: (self.store.user_name if self.store else None)
                           or self.settings.value("benutzer") or "", constant=True)

    def _set_status(self, text):
        self._status = text
        self.changed.emit()

    def show_status(self, text, ms=0):
        self._set_status(text)
        if ms:
            self.status_timer.start(ms)

    # ------------------------------------------------------------------ Start
    def start(self):
        """Favoriten-Datei und Benutzer; fehlt eines davon, zeigt QML die Einrichtungsseite."""
        folder = self._fav_dir_arg or self.settings.value("favoriten_ordner")
        if folder:
            self.open_store(folder, reload=False)
        name = self._user_arg or (self.store.user_name if self.store else None) or self.settings.value("benutzer")
        if self.store is None or not name:
            self._setup = True
            self.changed.emit()
            return
        self.set_user(name)
        self.after_start()

    @Slot(result=str)
    def chooseFolder(self):
        return QFileDialog.getExistingDirectory(None, "Ordner für Favoriten & Notizen wählen", self.defaultFolder) or ""

    @Slot(str, str)
    def finishSetup(self, folder, name):
        if not self.open_store(folder.strip() or self.defaultFolder, reload=False):
            return
        self.set_user(name.strip() or getpass.getuser())   # ohne Angabe: Windows-Anmeldename
        self._setup = False
        self.after_start()

    def after_start(self):
        self.reload_all()
        if not queries.list_versions(self.conn):
            QTimer.singleShot(300, self.maint.offer_first_import)
        else:
            self.goto(2)
            if self.last_open:
                QTimer.singleShot(700, lambda: self.maint.whats_new(auto=True))
        if not self.last_open:
            self.settings.setValue("zuletzt_geoeffnet", dt.datetime.now().isoformat(timespec="seconds"))
        self.changed.emit()

    # ------------------------------------------------------------------ Favoriten-Datei und Benutzer
    def open_store(self, folder, reload=True, carry=None):
        try:
            store = FavoriteStore(folder)
        except OSError as exc:
            fallback = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
            self.ask("Favoriten nicht lesbar", f"Die Favoriten-Datei in<br><b>{folder}</b><br>kann nicht gelesen werden:"
                     f"<br>{exc}<br><br>Vorübergehend wird <b>{fallback}</b> verwendet.",
                     [("later", "Später"), ("pick", "Anderen Ordner wählen …", True)],
                     lambda b, _t: b == "pick" and self.change_fav_folder(), icon="alert")
            if self.store is not None:
                return False
            folder, store = fallback, FavoriteStore(fallback)
        if store.recovered:
            self.info("Favoriten-Datei beschädigt", f"Die Datei war beschädigt und wurde gesichert als:<br>{store.recovered}"
                      "<br><br>Es wird mit leeren Favoriten weitergearbeitet.", icon="alert")
        if store.is_new:   # Übernahme aus dem bisherigen Ordner bzw. aus der gemeinsamen DB von v1.x
            for k in (list(carry.favs) if carry else legacy_db_keys(self.conn)):
                store.favs.setdefault(k, dt.datetime.now().isoformat(timespec="seconds"))
            if carry:
                store.notes.update(carry.notes)
            if self.persist(store.save) is None and self.store is not None:
                return False
        self.store = store
        if self.user is not None:
            self.set_user(store.user_name or self.user)
        self.settings.setValue("favoriten_ordner", str(Path(folder)))
        self.store.attach(self.conn)
        if reload:
            self.reload_all()
        self.changed.emit()
        return True

    def change_fav_folder(self):
        folder = QFileDialog.getExistingDirectory(None, "Ordner für Favoriten & Notizen wählen", str(self.store.path.parent))
        if not folder or Path(folder) == self.store.path.parent:
            return
        self.detail.save_note()

        def switch(carry):
            if self.open_store(folder, carry=carry):
                self.show_status(f"Favoriten werden jetzt gespeichert in {self.store.path}", 6000)

        if not (Path(folder) / FILE_NAME).exists() and (self.store.favs or self.store.notes):
            old = self.store
            self.ask("Favoriten übernehmen?", f"Im gewählten Ordner gibt es noch keine Favoriten-Datei.<br><br>Ihre aktuellen "
                     f"{len(old.favs)} Favoriten und {len(old.notes)} Notizen dorthin übernehmen?",
                     [("no", "Nein"), ("yes", "Ja, übernehmen", True)], lambda b, _t: switch(old if b == "yes" else None))
        else:
            switch(None)

    def set_user(self, name):
        if not name:
            return
        try:
            stored = None if self.read_only else self.list_db(queries.create_user, name)
        except ValueError as exc:
            self.info("Ungültiger Name", str(exc), icon="alert")
            return
        self.user = stored or name   # DB schreibgeschützt: Name trotzdem für diese Sitzung
        if self.store is not None and self.store.user_name != self.user:
            self.store.user_name = self.user
            self.persist(self.store.save)
        self.show_status(f"Angemeldet als {self.user}", 4000)
        self.changed.emit()

    @Slot()
    def showUser(self):
        self.toast(f"Angemeldet als {self.user} – der Name steht in Ihrer Favoriten-Datei ({self.store.path.name})")

    def persist(self, fn, *args):
        """Speichern in der Favoriten-Datei; Fehler (z. B. Netzlaufwerk weg) melden. None = fehlgeschlagen."""
        try:
            result = fn(*args)
        except OSError as exc:
            self.info("Speichern fehlgeschlagen", f"Favoriten/Notizen konnten nicht gespeichert werden:<br>{exc}<br><br>"
                      "Ist der Ordner erreichbar? Speicherort ändern unter <b>Menü → Einstellungen</b>.", icon="alert")
            return None
        return True if result is None else result

    def list_db(self, fn, *args):
        """Schreibzugriff auf die gemeinsame DB mit verständlicher Meldung. None = fehlgeschlagen."""
        try:
            result = fn(self.conn, *args)
        except sqlite3.IntegrityError:
            self.info("Name bereits vergeben", "Es gibt schon eine Liste mit diesem Namen.", icon="alert")
            return None
        except sqlite3.OperationalError as exc:
            reason = ("Ein anderer Benutzer ändert gerade die Datenbank (z. B. ein Import). Bitte gleich erneut versuchen."
                      if "locked" in str(exc) else "Sie haben keine Schreibrechte auf die gemeinsame Datenbank."
                      if "readonly" in str(exc) or "read-only" in str(exc) else str(exc))
            self.info("Speichern fehlgeschlagen", f"Die Änderung wurde nicht gespeichert.<br><br>{reason}", icon="alert")
            return None
        return True if result is None else result

    # ------------------------------------------------------------------ Laden / Seiten
    def reload_all(self):
        self.store.attach(self.conn)
        self.names = queries.Names(self.conn)
        self.first_id = queries.first_import_id(self.conn)
        self.latest_id = queries.latest_import_id(self.conn)
        self.lists = {r["id"]: r for r in queries.list_lists(self.conn)}
        self.comment_info = queries.comment_summary(self.conn)
        self.hier_data = queries.hierarchy_tree(self.conn)
        # einmal je Laden zählen – nicht bei jedem Fensterwechsel erneut über das Netzlaufwerk
        self.total_active = queries.count_products(self.conn, ProductFilter(status="aktiv"))
        self.node_by_key = {}

        def index(nodes):
            for n in nodes:
                self.node_by_key[_key_tuple(n["key"])] = n
                index(n["children"])

        index(self.hier_data)
        self.tree.rebuild()
        self.products.reload_options()
        self.products.refresh()
        self.versions.load()
        if self._page == 2:
            self.dash.refresh()
        self.activity.update_badge()
        self.changed.emit()

    @Slot()
    def reload(self):
        self.reload_all()
        self.toast("Neu geladen")

    @Slot(int)
    def goto(self, page):
        """0 Produkte, 1 Versionen, 2 Startseite, 3 Änderungen anderer."""
        self._page = page
        self.changed.emit()
        if page == 2:
            self.dash.refresh()
        elif page == 3:
            self.activity.refresh(mark_seen=True)

    @Slot()
    def activated(self):
        """Fenster wieder aktiv: Änderungen anderer Benutzer übernehmen (eine Datenbank, mehrere Personen)."""
        if self.store is None or self._setup:
            return
        try:
            if queries.latest_import_id(self.conn) != self.latest_id:
                self.reload_all()
                self.show_status("Neue Version von einem anderen Benutzer importiert – Ansicht aktualisiert", 6000)
            else:
                self.lists = {r["id"]: r for r in queries.list_lists(self.conn)}
                self.tree.refresh_collections()
            self.activity.update_badge()
        except sqlite3.OperationalError:
            pass   # gerade gesperrt (z. B. Import eines Kollegen) – beim nächsten Mal

    def after_list_change(self):
        """Nach Änderungen an Favoriten/Listen: SQL-Tabellen, Baum, Sterne und ggf. die Liste aktualisieren."""
        self.store.attach(self.conn)
        self.lists = {r["id"]: r for r in queries.list_lists(self.conn)}
        self.tree.refresh_collections()
        if self.lists_ctl.current_container() is not None:
            self.products.refresh()
        else:
            self.products.update_stars()
            self.detail.reload()

    # ------------------------------------------------------------------ zuletzt angesehen
    def _load_recent(self):
        value = self.settings.value("zuletzt_angesehen") or []
        return [value] if isinstance(value, str) else list(value)

    def remember_recent(self, nummer):
        if self.recent[:1] == [nummer]:
            return
        self.recent = [nummer] + [n for n in self.recent if n != nummer][:19]
        self.settings.setValue("zuletzt_angesehen", self.recent)
        self.tree.update_recent_count()

    # ------------------------------------------------------------------ Aktionen, Menüs, Dialoge, Hinweise
    def act(self, fn):
        aid = next(self._ids)
        self._actions[aid] = fn
        if len(self._actions) > 4000:   # alte Menü-Aktionen vergessen
            for k in list(self._actions)[:2000]:
                del self._actions[k]
        return aid

    @Slot(int)
    def run(self, aid):
        fn = self._actions.get(aid)
        if fn is not None:
            fn()

    def menu_spec(self, entries):
        """Menüeinträge mit Funktionen -> Liste für QML (Funktionen als Aktions-ids)."""
        out = []
        for e in entries:
            e = dict(e)
            fn = e.pop("fn", None)
            e["aid"] = self.act(fn) if fn else -1
            e["children"] = self.menu_spec(e.get("children") or [])
            out.append(e)
        return out

    def popup_menu(self, entries):
        self.menuRequested.emit(self.menu_spec(entries))

    def ask(self, title, text, buttons=None, on_answer=None, input=None, on_link=None, wide=False, icon="", danger=False):
        """Dialog in QML. buttons: [(id, Text, primär?, gefährlich?)]; on_answer(Knopf-id, eingegebener Text)."""
        buttons = buttons or [("ok", "OK", True)]
        did = next(self._ids)
        spec = {"id": did, "title": title, "text": text, "wide": wide, "icon": icon, "danger": danger,
                "buttons": [{"id": b[0], "text": b[1], "primary": len(b) > 2 and b[2], "danger": len(b) > 3 and b[3]}
                            for b in buttons],
                "hasInput": input is not None, "inputLabel": (input or {}).get("label", ""),
                "inputText": (input or {}).get("text", ""), "placeholder": (input or {}).get("placeholder", "")}
        if self.auto_answer is not None:
            button, text_in = self.auto_answer(spec)
            if on_answer:
                on_answer(button, text_in)
            return
        self._pending[did] = (on_answer, on_link)
        self.dialogRequested.emit(spec)

    @Slot(int, str, str)
    def answer(self, did, button, text):
        on_answer, _ = self._pending.pop(did, (None, None))
        if on_answer:
            on_answer(button, text)

    @Slot(int, str)
    def link(self, did, href):
        _, on_link = self._pending.pop(did, (None, None))
        if on_link:
            on_link(href)

    def info(self, title, text, **kw):
        self.ask(title, text, [("ok", "OK", True)], **kw)

    def confirm(self, title, text, fn, yes="Ja", no="Abbrechen", danger=False):
        self.ask(title, text, [("no", no), ("yes", yes, True, danger)], lambda b, _t: b == "yes" and fn(),
                 icon="alert" if danger else "help", danger=danger)

    def prompt(self, title, label, fn, text="", placeholder=""):
        self.ask(title, "", [("cancel", "Abbrechen"), ("ok", "OK", True)],
                 lambda b, t: b == "ok" and t.strip() and fn(t.strip()),
                 input={"label": label, "text": text, "placeholder": placeholder})

    def toast(self, text, action_text="", fn=None):
        self.toastRequested.emit(text, action_text, self.act(fn) if fn else -1)

    def push_undo(self, label, fn):
        self._undo.append((label, fn))
        del self._undo[:-30]
        self.toast(label, "Rückgängig", self.undo)

    @Slot()
    def undo(self):
        if not self._undo:
            self.toast("Nichts zum Rückgängigmachen")
            return
        label, fn = self._undo.pop()
        fn()
        self.toast(f"Rückgängig: {label}")

    @Slot(str)
    def requestFocus(self, what):
        if what in ("search", "hersteller", "tree"):
            self.goto(0)
        self.focusRequested.emit(what)

    def close(self):
        self.detail.save_note()
        self.settings.setValue("zuletzt_geoeffnet", dt.datetime.now().isoformat(timespec="seconds"))
