"""Persönliche Favoriten, Notizen und Farbkategorien – je Benutzer eine JSON-Datei in einem frei wählbaren Ordner.

Schlüssel k = Nummern-Präfix: 2/4/6/7 Stellen = Gruppe/Ort/Untergruppe/Art, 10 Stellen = Produkt.
Neben „Meine Favoriten“ (favs) gibt es beliebig verschachtelte private Listen (plists). Einträge sind wie bei
den Favoriten Produkte (10 Stellen) oder ganze Gruppen (Präfix).
Für SQL-Abfragen (Filter, Suche, Sortierung) werden die Daten in TEMP-Tabellen der jeweiligen Verbindung
kopiert (attach): favorit, pliste, notiz, markierung.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

FILE_NAME = "HMV_Favoriten.json"
DEFAULT_CATEGORIES = {
    "1": {"name": "Erledigt", "farbe": "#2E9E5B"},
    "2": {"name": "In Prüfung", "farbe": "#E8A317"},
    "3": {"name": "Kritisch", "farbe": "#D64541"},
}


class FavoriteStore:
    def __init__(self, folder):
        self.path = Path(folder) / FILE_NAME
        self.favs: dict[str, str] = {}     # k -> hinzugefügt am
        self.notes: dict[str, str] = {}    # Produktnummer -> Notiz
        self.categories: dict[str, dict] = {k: dict(v) for k, v in DEFAULT_CATEGORIES.items()}  # id -> name, farbe
        self.marks: dict[str, str] = {}    # Produktnummer -> Kategorie-id
        self.plists: dict[str, dict] = {}  # id -> {"name", "parent" (id oder None), "items": {k: hinzugefügt am}}
        self.searches: dict[str, dict] = {}  # Name -> gespeicherter Filterzustand
        self.abos: list[int] = []            # abonnierte gemeinsame Listen (Hinweis bei Änderungen)
        self.user_name: str | None = None    # Nachname des Benutzers (einmalig beim ersten Start festgelegt)
        self.recovered: Path | None = None  # Sicherung einer unlesbaren Datei
        self.is_new = not self.path.exists()
        if not self.is_new:
            self._load()

    def _load(self):
        raw = self.path.read_text(encoding="utf-8")   # OSError (z. B. Netzlaufwerk weg) geht an den Aufrufer
        try:
            data = json.loads(raw)
            self.favs = {str(k): str(v) for k, v in data.get("favoriten", {}).items()}
            self.notes = {str(k): str(v) for k, v in data.get("notizen", {}).items()}
            if "kategorien" in data:   # ältere Dateien ohne Kategorien behalten die Vorgaben
                self.categories = {str(k): {"name": str(v["name"]), "farbe": str(v["farbe"])}
                                   for k, v in data["kategorien"].items()}
            self.marks = {str(k): str(v) for k, v in data.get("markierungen", {}).items() if str(v) in self.categories}
            self.plists = {str(k): {"name": str(v["name"]), "parent": None if v.get("parent") is None else str(v["parent"]),
                                    "items": {str(i): str(d) for i, d in v.get("items", {}).items()}}
                           for k, v in data.get("listen", {}).items()}
            self.searches = {str(k): dict(v) for k, v in data.get("suchen", {}).items()}
            self.abos = [int(x) for x in data.get("abos", [])]
            self.user_name = str(data["benutzer"]).strip() or None if data.get("benutzer") else None
        except (ValueError, AttributeError, KeyError, TypeError):
            # Datei kaputt: nicht überschreiben, sondern beiseitelegen und leer weitermachen
            stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.recovered = self.path.with_name(f"{self.path.stem}.defekt_{stamp}.json")
            os.replace(self.path, self.recovered)
            self.favs, self.notes, self.marks, self.plists = {}, {}, {}, {}
            self.categories = {k: dict(v) for k, v in DEFAULT_CATEGORIES.items()}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": 4, "favoriten": self.favs, "notizen": self.notes,
                                   "kategorien": self.categories, "markierungen": self.marks, "listen": self.plists,
                                   "suchen": self.searches, "abos": self.abos, "benutzer": self.user_name},
                                  ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)   # atomar: bei Absturz bleibt die alte Datei vollständig
        self.is_new = False

    def toggle(self, k: str) -> bool:
        """Schaltet den Favoriten um und speichert; True = jetzt Favorit."""
        added = k not in self.favs
        if added:
            self.favs[k] = dt.datetime.now().isoformat(timespec="seconds")
        else:
            del self.favs[k]
        self.save()
        return added

    def add(self, keys) -> int:
        new = [k for k in keys if k not in self.favs]
        now = dt.datetime.now().isoformat(timespec="seconds")
        self.favs.update({k: now for k in new})
        if new:
            self.save()
        return len(new)

    def set_note(self, k: str, text: str):
        text = text.strip()
        if text:
            self.notes[k] = text
        else:
            self.notes.pop(k, None)
        self.save()

    # ---- Farbkategorien
    def add_category(self, name: str, color: str) -> str:
        cid = str(max((int(k) for k in self.categories), default=0) + 1)
        self.categories[cid] = {"name": name.strip(), "farbe": color}
        self.save()
        return cid

    def update_category(self, cid: str, name: str | None = None, color: str | None = None):
        if name is not None:
            self.categories[cid]["name"] = name.strip()
        if color is not None:
            self.categories[cid]["farbe"] = color
        self.save()

    def delete_category(self, cid: str):
        self.categories.pop(cid, None)
        self.marks = {k: v for k, v in self.marks.items() if v != cid}
        self.save()

    def set_mark(self, nummern, cid: str | None):
        """Kategorie für Produkte setzen (None = Markierung entfernen)."""
        for k in nummern:
            if cid is None:
                self.marks.pop(k, None)
            else:
                self.marks[k] = cid
        self.save()

    # ---- private Listen
    def create_plist(self, name: str, parent: str | None = None) -> str:
        name = name.strip()
        if not name:
            raise ValueError("Bitte einen Namen angeben.")
        if any(v["parent"] == parent and v["name"].casefold() == name.casefold() for v in self.plists.values()):
            raise ValueError(f"Es gibt auf dieser Ebene schon eine Liste „{name}“.")
        lid = str(max((int(k) for k in self.plists), default=0) + 1)
        self.plists[lid] = {"name": name, "parent": parent, "items": {}}
        self.save()
        return lid

    def rename_plist(self, lid: str, name: str):
        name = name.strip()
        parent = self.plists[lid]["parent"]
        if not name or any(k != lid and v["parent"] == parent and v["name"].casefold() == name.casefold()
                           for k, v in self.plists.items()):
            raise ValueError(f"Name „{name}“ ist leer oder auf dieser Ebene schon vergeben.")
        self.plists[lid]["name"] = name
        self.save()

    def delete_plist(self, lid: str):
        """Löscht die Liste samt Unterlisten."""
        doomed, todo = set(), [lid]
        while todo:
            cur = todo.pop()
            doomed.add(cur)
            todo += [k for k, v in self.plists.items() if v["parent"] == cur]
        for k in doomed:
            self.plists.pop(k, None)
        self.save()

    def add_to_plist(self, lid: str, keys) -> int:
        items = self.plists[lid]["items"]
        new = [k for k in keys if k not in items]
        now = dt.datetime.now().isoformat(timespec="seconds")
        items.update({k: now for k in new})
        if new:
            self.save()
        return len(new)

    def remove_from_plist(self, lid: str, keys) -> int:
        items = self.plists[lid]["items"]
        gone = [k for k in keys if items.pop(k, None) is not None]
        if gone:
            self.save()
        return len(gone)

    # ---- gespeicherte Suchen und Abos
    def save_search(self, name: str, state: dict):
        name = name.strip()
        if not name:
            raise ValueError("Bitte einen Namen angeben.")
        self.searches[name] = state
        self.save()

    def delete_search(self, name: str):
        self.searches.pop(name, None)
        self.save()

    def toggle_abo(self, liste_id: int) -> bool:
        if liste_id in self.abos:
            self.abos.remove(liste_id)
        else:
            self.abos.append(liste_id)
        self.save()
        return liste_id in self.abos

    def attach(self, conn):
        """Favoriten, Notizen und Markierungen in die TEMP-Tabellen dieser Verbindung übernehmen."""
        conn.execute("DELETE FROM temp.favorit")
        conn.executemany("INSERT INTO temp.favorit(k) VALUES(?)", [(k,) for k in self.favs])
        conn.execute("DELETE FROM temp.pliste")
        conn.executemany("INSERT INTO temp.pliste(liste, k) VALUES(?, ?)",
                         [(lid, k) for lid, v in self.plists.items() for k in v["items"]])
        conn.execute("DELETE FROM temp.notiz")
        conn.executemany("INSERT INTO temp.notiz(k, text) VALUES(?, ?)", list(self.notes.items()))
        conn.execute("DELETE FROM temp.markierung")
        conn.executemany("INSERT INTO temp.markierung(k, kat) VALUES(?, ?)", list(self.marks.items()))


def legacy_db_keys(conn) -> list[str]:
    """Favoriten aus der früheren gemeinsamen DB-Tabelle (vor v2.0), für die einmalige Übernahme."""
    try:
        return [r[0] for r in conn.execute("SELECT k FROM main.favorit")]
    except Exception:  # Tabelle gibt es nur in älteren Datenbanken
        return []
