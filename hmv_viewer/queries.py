"""Abfragen für GUI und Export (inkl. Schreibzugriffe für gemeinsame Listen)."""
from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
from dataclasses import dataclass
from typing import Iterator

from . import merkmale
from .model import ENTITY_LABELS, FIELD_LABELS, format_nummer

ORDER_COLUMNS = {
    "nummer": "p.nummer",
    "bezeichnung": "p.bezeichnung COLLATE NOCASE",
    "hersteller": "p.hersteller COLLATE NOCASE",
    "art": "p.gruppe, p.ort, p.untergruppe, p.art",
    "aufnahme": "p.aufnahmedatum",
    "aenderung": "p.aenderungsdatum",
    "version": "p.last_import_change",
    "fav": "p.nummer IN (SELECT k FROM favorit)",
    "kat": "(SELECT kat FROM markierung WHERE k=p.nummer) IS NULL, (SELECT kat FROM markierung WHERE k=p.nummer)",
}


@dataclass
class ProductFilter:
    text: str = ""
    in_merkmale: bool = False      # Suchbereich Merkmale (Volltext-Index)
    in_bez: bool = True            # Suchbereich Bezeichnung/Hersteller (Volltext-Index)
    in_notizen: bool = True        # Suchbereich eigene Notizen + Kommentare
    status: str = "aktiv"          # aktiv | entfernt | alle
    gruppe: int | None = None
    ort: int | None = None
    untergruppe: int | None = None
    art: int | None = None
    import_id: int | None = None   # nur Produkte, die in dieser Version eine Änderung hatten
    change_type: str | None = None  # NEU | GEAENDERT | ENTFERNT | REAKTIVIERT
    favoriten: bool = False        # nur als Favorit markierte Produkte
    hersteller: str = ""           # Teiltext im Herstellernamen
    liste_id: int | None = None    # nur Produkte dieser gemeinsamen Liste
    kategorie: str | None = None   # nur Produkte mit dieser persönlichen Farbkategorie
    pliste_id: str | None = None   # nur Produkte dieser privaten Liste (Favoriten-Datei)
    notiz_text: str = ""           # nur Produkte, deren Merkmale, eigene Notiz oder Kommentare diese Wörter enthalten
    nummern: tuple | None = None   # nur diese Produktnummern (z. B. „Zuletzt angesehen“, eingefügte Nummernliste)
    ohne_platzhalter: bool = False # „Nicht besetzt“-Positionen des HMV ausblenden


def _like(term: str) -> str:
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _member(source_sql: str) -> str:
    """Produkt gehört zu einer Liste: direkt eingetragen oder über eine eingetragene ganze Gruppe (Präfix).

    source_sql liefert die Einträge (Spalte k) und enthält höchstens einen Parameter -> Aufrufer übergibt ihn 2x.
    """
    return (f"(p.nummer IN ({source_sql}) OR EXISTS (SELECT 1 FROM ({source_sql}) g"
            f" WHERE length(g.k) < 10 AND substr(p.nummer, 1, length(g.k)) = g.k))")


_NOTE_CLAUSE = ("(p.nummer IN (SELECT k FROM notiz WHERE fold(text) LIKE ? ESCAPE '\\')"
                " OR p.nummer IN (SELECT nummer FROM kommentar WHERE fold(text) LIKE ? ESCAPE '\\'))")


MERKMALE_GEAENDERT = "GEAENDERT_MERKMALE"   # Pseudo-Änderungstyp: geändert UND Merkmale betroffen


def _type_cond(alias: str, change_type: str):
    """SQL-Bedingung für einen Änderungstyp (auch „Geändert – Merkmale“) auf die History-Tabelle alias."""
    if change_type == MERKMALE_GEAENDERT:
        return f"{alias}.change_type='GEAENDERT' AND json_extract({alias}.changes, '$.MERKMALE') IS NOT NULL", []
    return f"{alias}.change_type=?", [change_type]


def _build(f: ProductFilter):
    """Gibt (join_sql, where_sql, params) zurück. Tabellen-Alias: p (produkt), h (history)."""
    join, where, params = "", [], []
    if f.import_id is not None:
        join = " JOIN history h ON h.entity='PRODUKT' AND h.k=p.nummer AND h.import_id=?"
        params.append(f.import_id)
        if f.change_type:
            cond, extra = _type_cond("h", f.change_type)
            where.append(cond)
            params += extra
    elif f.change_type:
        cond, extra = _type_cond("hx", f.change_type)
        where.append(f"p.nummer IN (SELECT hx.k FROM history hx WHERE hx.entity='PRODUKT' AND {cond})")
        params += extra

    if f.favoriten:
        where.append(_member("SELECT k FROM favorit"))
    if f.pliste_id is not None:
        where.append(_member("SELECT k FROM pliste WHERE liste=?"))
        params += [f.pliste_id] * 2
    if f.nummern is not None:
        where.append("p.nummer IN (SELECT value FROM json_each(?))")
        params.append(json.dumps(list(f.nummern)))
    if f.kategorie is not None:
        where.append("p.nummer IN (SELECT k FROM markierung WHERE kat=?)")
        params.append(f.kategorie)
    if f.liste_id is not None:
        where.append(_member("SELECT nummer AS k FROM liste_eintrag WHERE liste_id=?"))
        params += [f.liste_id] * 2
    if f.ohne_platzhalter:
        where.append("COALESCE(fold(trim(p.bezeichnung)), '') <> 'nicht besetzt'")
    if f.status == "aktiv":
        where.append("p.active=1")
    elif f.status == "entfernt":
        where.append("p.active=0")

    for col in ("gruppe", "ort", "untergruppe", "art"):
        v = getattr(f, col)
        if v is not None:
            where.append(f"p.{col}=?")
            params.append(v)

    if f.hersteller.strip():
        where.append("fold(p.hersteller) LIKE ? ESCAPE '\\'")
        params.append(_like(f.hersteller.strip().casefold()))

    for term in f.notiz_text.split():
        where.append(f"(fold(p.merkmale) LIKE ? ESCAPE '\\' OR {_NOTE_CLAUSE})")
        params += [_like(term.casefold())] * 3

    if f.text.strip():
        # Volltext-Index (merkmale.py): Wortanfang, Zahlen nur ganz, "Phrase", -Ausschluss, vereinheitlicht
        q = merkmale.parse_query(f.text)
        found, found_params = [], []
        columns = [c for c, on in (("bez", f.in_bez), ("merk", f.in_merkmale)) if on]
        expr = q.fts(columns) if columns else None
        if expr:
            found.append(merkmale.FTS_MATCH)
            found_params.append(expr)
        if f.in_notizen and q.words:   # Notizen/Kommentare sind klein -> einfache Teiltext-Suche, alle Wörter
            found.append("(" + " AND ".join([_NOTE_CLAUSE] * len(q.words)) + ")")
            for w in q.words:
                found_params += [_like(w.casefold())] * 2
        if found:
            where.append("(" + " OR ".join(found) + ")")
            params += found_params
        elif q.include or q.words:
            where.append("0")   # gesucht, aber kein Suchbereich gewählt
        for number in q.numbers:
            digits = number.replace(".", "")
            where.append("p.nummer LIKE ?")
            params.append(digits + "%" if "." in number or len(digits) == 10 else _like(digits))
    return join, (" WHERE " + " AND ".join(where)) if where else "", params


def count_products(conn, f: ProductFilter) -> int:
    join, where, params = _build(f)
    return conn.execute(f"SELECT COUNT(*) FROM produkt p{join}{where}", params).fetchone()[0]


def fetch_products(conn, f: ProductFilter, order: str = "nummer", desc: bool = False,
                   limit: int = 500, offset: int = 0) -> list[sqlite3.Row]:
    join, where, params = _build(f)
    shown = "h.change_type" if f.import_id is not None else "NULL"
    order_sql = ORDER_COLUMNS.get(order, "p.nummer")
    direction = "DESC" if desc else "ASC"
    order_by = ", ".join(f"{c.strip()} {direction}" for c in order_sql.split(",")) + ", p.nummer ASC"
    sql = (f"SELECT p.*, {shown} AS shown_type FROM produkt p{join}{where}"
           f" ORDER BY {order_by} LIMIT ? OFFSET ?")
    return conn.execute(sql, params + [limit, offset]).fetchall()


def iter_products(conn, f: ProductFilter, batch: int = 2000) -> Iterator[sqlite3.Row]:
    join, where, params = _build(f)
    shown = "h.change_type" if f.import_id is not None else "NULL"
    cur = conn.execute(f"SELECT p.*, {shown} AS shown_type FROM produkt p{join}{where} ORDER BY p.nummer", params)
    while True:
        rows = cur.fetchmany(batch)
        if not rows:
            return
        yield from rows


def list_hersteller(conn) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT hersteller FROM produkt WHERE active=1 AND hersteller IS NOT NULL AND hersteller<>''"
        " ORDER BY hersteller COLLATE NOCASE")]


def get_product(conn, nummer: str):
    return conn.execute("SELECT * FROM produkt WHERE nummer=?", (nummer,)).fetchone()


# ----------------------------------------------------------------------------------------------
# Versionen
def list_versions(conn) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM imports ORDER BY id DESC").fetchall()


def first_import_id(conn) -> int | None:
    return conn.execute("SELECT MIN(id) FROM imports").fetchone()[0]


def latest_import_id(conn) -> int | None:
    return conn.execute("SELECT MAX(id) FROM imports").fetchone()[0]


def version_label(row) -> str:
    """z. B. 'V3 · Stand 2026-08-31'"""
    if row is None:
        return ""
    stamp = row["source_date"] or (row["imported_at"] or "")[:10]
    return f"V{row['id']} · Stand {stamp}"


def version_labels(conn) -> dict[int, str]:
    return {r["id"]: version_label(r) for r in list_versions(conn)}


def product_history(conn, nummer: str) -> list[dict]:
    rows = conn.execute(
        "SELECT h.*, i.imported_at, i.source_date, i.source_name FROM history h JOIN imports i ON i.id=h.import_id"
        " WHERE h.entity='PRODUKT' AND h.k=? ORDER BY h.import_id DESC", (nummer,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["changes"] = json.loads(r["changes"]) if r["changes"] else {}
        out.append(d)
    return out


def count_changes(conn, import_id: int, change_type: str | None = None) -> int:
    sql, params = "SELECT COUNT(*) FROM history h WHERE h.import_id=?", [import_id]
    if change_type:
        cond, extra = _type_cond("h", change_type)
        sql += " AND " + cond
        params += extra
    return conn.execute(sql, params).fetchone()[0]


def version_changes(conn, import_id: int, change_type: str | None = None, limit: int = 5000) -> list[dict]:
    sql = ("SELECT h.entity, h.k, h.change_type, h.changes, p.bezeichnung AS pname, s.data AS sdata"
           " FROM history h"
           " LEFT JOIN produkt p ON h.entity='PRODUKT' AND p.nummer=h.k"
           " LEFT JOIN stamm s ON s.entity=h.entity AND s.k=h.k"
           " WHERE h.import_id=?")
    params: list = [import_id]
    if change_type:
        cond, extra = _type_cond("h", change_type)
        sql += " AND " + cond
        params += extra
    sql += " ORDER BY (h.entity='PRODUKT'), h.entity, h.k LIMIT ?"
    params.append(limit)
    out = []
    for r in conn.execute(sql, params):
        name = r["pname"]
        if r["entity"] != "PRODUKT" and r["sdata"]:
            name = json.loads(r["sdata"]).get("BEZEICHNUNG")
        changes = json.loads(r["changes"]) if r["changes"] else {}
        out.append({
            "entity": r["entity"], "entity_label": ENTITY_LABELS.get(r["entity"], r["entity"]),
            "k": r["k"], "display_k": format_nummer(r["k"]) if r["entity"] == "PRODUKT" else r["k"],
            "change_type": r["change_type"], "name": name or "",
            "fields": ", ".join(FIELD_LABELS.get(f, f) for f in changes),
        })
    return out


# ----------------------------------------------------------------------------------------------
# Favoriten-Schlüssel (Produkte und Hierarchie-Knoten als Nummern-Präfix, Speicherung: favorites.py)
_PREFIX_PARTS = (("gruppe", 0, 2), ("ort", 2, 4), ("untergruppe", 4, 6), ("art", 6, 7))


def favorite_key(key: dict) -> str:
    """Hierarchie-Schlüssel -> Nummern-Präfix, z. B. {gruppe: 1, ort: 24} -> '0124'."""
    return "".join(str(key[c]).zfill(b - a) for c, a, b in _PREFIX_PARTS if key.get(c) is not None)


def key_from_prefix(k: str) -> dict:
    return {c: int(k[a:b]) for c, a, b in _PREFIX_PARTS if len(k) >= b}


# ----------------------------------------------------------------------------------------------
# Gemeinsame Listen (in der Datenbank, für alle Benutzer sichtbar)
def _now():
    return dt.datetime.now().isoformat(timespec="seconds")


def list_lists(conn) -> list[sqlite3.Row]:
    """Alle Listen mit n = Anzahl Einzelprodukte; parent_id für die Verschachtelung."""
    return conn.execute(
        "SELECT l.*, (SELECT COUNT(*) FROM liste_eintrag e WHERE e.liste_id=l.id AND length(e.nummer)=10) AS n"
        " FROM liste l ORDER BY l.name COLLATE NOCASE").fetchall()


def list_groups(conn, liste_id: int) -> list[str]:
    """Als ganze Gruppe eingetragene Präfixe einer Liste."""
    return [r[0] for r in conn.execute("SELECT nummer FROM liste_eintrag WHERE liste_id=? AND length(nummer)<10"
                                       " ORDER BY nummer", (liste_id,))]


def create_list(conn, name: str, user: str, parent_id: int | None = None) -> int:
    """Legt eine (Unter-)Liste an; gleicher Name auf derselben Ebene -> sqlite3.IntegrityError."""
    name = name.strip()
    if not name:
        raise ValueError("Bitte einen Namen angeben.")
    now = _now()
    lid = conn.execute("INSERT INTO liste(parent_id, name, created_by, created_at, changed_by, changed_at)"
                       " VALUES(?, ?, ?, ?, ?, ?)", (parent_id, name, user, now, user, now)).lastrowid
    _log(conn, lid, "angelegt", name, user)
    return lid


def _log(conn, liste_id: int, aktion: str, detail: str, user: str | None):
    conn.execute("INSERT INTO liste_log(liste_id, aktion, detail, user, at) VALUES(?, ?, ?, ?, ?)",
                 (liste_id, aktion, detail, user, _now()))


def _describe(keys) -> str:
    keys = list(keys)
    shown = ", ".join(format_nummer(k) if len(k) == 10 else f"Gruppe {k}" for k in keys[:8])
    return shown + (f" … (+{len(keys) - 8})" if len(keys) > 8 else "")


def list_log(conn, liste_id: int, limit: int = 500) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM liste_log WHERE liste_id=? ORDER BY id DESC LIMIT ?", (liste_id, limit)).fetchall()


def _touch_list(conn, liste_id: int, user: str | None):
    conn.execute("UPDATE liste SET changed_by=?, changed_at=? WHERE id=?", (user, _now(), liste_id))


def rename_list(conn, liste_id: int, name: str, user: str | None = None):
    if not name.strip():
        raise ValueError("Bitte einen Namen angeben.")
    conn.execute("UPDATE liste SET name=? WHERE id=?", (name.strip(), liste_id))
    _touch_list(conn, liste_id, user)
    _log(conn, liste_id, "umbenannt", name.strip(), user)


def delete_list(conn, liste_id: int):
    conn.execute("DELETE FROM liste WHERE id=?", (liste_id,))   # Unterlisten und Einträge per ON DELETE CASCADE


def add_to_list(conn, liste_id: int, nummern, user: str) -> int:
    before = conn.total_changes
    conn.executemany("INSERT OR IGNORE INTO liste_eintrag(liste_id, nummer, added_by, added_at) VALUES(?, ?, ?, ?)",
                     [(liste_id, n, user, _now()) for n in nummern])
    n = conn.total_changes - before
    if n:
        _touch_list(conn, liste_id, user)
        _log(conn, liste_id, "hinzugefügt", f"{n}: {_describe(nummern)}", user)
    return n


def remove_from_list(conn, liste_id: int, nummern, user: str | None = None) -> int:
    before = conn.total_changes
    conn.executemany("DELETE FROM liste_eintrag WHERE liste_id=? AND nummer=?", [(liste_id, n) for n in nummern])
    n = conn.total_changes - before
    if n:
        _touch_list(conn, liste_id, user)
        _log(conn, liste_id, "entfernt", f"{n}: {_describe(nummern)}", user)
    return n


def recent_lists(conn, limit: int = 8) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM liste ORDER BY COALESCE(changed_at, created_at) DESC LIMIT ?", (limit,)).fetchall()


# ----------------------------------------------------------------------------------------------
# Benutzer (nur Nachname) und gemeinsame Notizen
def list_users(conn) -> list[str]:
    return [r[0] for r in conn.execute("SELECT name FROM benutzer ORDER BY name COLLATE NOCASE")]


def create_user(conn, name: str) -> str:
    """Legt einen Benutzer an (falls neu) und gibt den gespeicherten Namen zurück."""
    name = " ".join(name.split())
    if not name or len(name) > 60:
        raise ValueError("Bitte einen Nachnamen mit höchstens 60 Zeichen angeben.")
    conn.execute("INSERT OR IGNORE INTO benutzer(name, created_at) VALUES(?, ?)", (name, _now()))
    return conn.execute("SELECT name FROM benutzer WHERE name=?", (name,)).fetchone()[0]


def add_comment(conn, nummer: str, text: str, user: str) -> int:
    text = text.strip()
    if not text:
        raise ValueError("Bitte einen Text eingeben.")
    return conn.execute("INSERT INTO kommentar(nummer, text, user, at) VALUES(?, ?, ?, ?)",
                        (nummer, text, user, _now())).lastrowid


def comments_for(conn, nummer: str) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM kommentar WHERE nummer=? ORDER BY id", (nummer,)).fetchall()


def delete_comment(conn, comment_id: int, user: str) -> int:
    """Löscht einen eigenen Kommentar; gibt 0 zurück, wenn er von jemand anderem stammt."""
    return conn.execute("DELETE FROM kommentar WHERE id=? AND user=?", (comment_id, user)).rowcount


def comment_summary(conn) -> dict[str, tuple]:
    """Produktnummer -> (Anzahl, letzter Kommentar als Row)."""
    out = {}
    for r in conn.execute("SELECT k.*, c.n FROM kommentar k JOIN (SELECT nummer, MAX(id) AS last, COUNT(*) AS n"
                          " FROM kommentar GROUP BY nummer) c ON c.last = k.id"):
        out[r["nummer"]] = (r["n"], r)
    return out


def comments_since(conn, since: str, not_by: str | None) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM kommentar WHERE at > ? AND COALESCE(user, '') <> COALESCE(?, '') ORDER BY id DESC",
                        (since, not_by)).fetchall()


def log_activity(conn, user: str, art: str, nummern, detail: str, farbe: str | None = None):
    now = _now()
    conn.executemany("INSERT INTO aktivitaet(at, user, art, nummer, detail, farbe) VALUES(?, ?, ?, ?, ?, ?)",
                     [(now, user, art, n, detail, farbe) for n in nummern])


ACTIVITY_KINDS = {"kommentar": "Kommentar", "kategorie": "Farbkategorie", "liste": "Gemeinsame Liste"}


def others_activity(conn, me: str | None, since: str = "", kind: str | None = None, user: str | None = None,
                    limit: int = 2000) -> list[sqlite3.Row]:
    """Was andere Benutzer getan haben: Kommentare, Farbmarkierungen, Änderungen an gemeinsamen Listen (neueste zuerst)."""
    parts, params = [], []
    if kind in (None, "kommentar"):
        parts.append("SELECT 'kommentar' AS art, k.at, k.user, k.nummer, k.text AS detail, NULL AS farbe, NULL AS liste_id"
                     " FROM kommentar k")
    if kind in (None, "kategorie"):
        parts.append("SELECT 'kategorie' AS art, a.at, a.user, a.nummer, a.detail, a.farbe, NULL AS liste_id FROM aktivitaet a"
                     " WHERE a.art='kategorie'")
    if kind in (None, "liste"):
        parts.append("SELECT 'liste' AS art, g.at, g.user, NULL AS nummer,"
                     " l.name || ': ' || g.aktion || COALESCE(' – ' || g.detail, '') AS detail,"
                     " NULL AS farbe, g.liste_id FROM liste_log g JOIN liste l ON l.id=g.liste_id")
    sql = ("SELECT x.*, p.bezeichnung FROM (" + " UNION ALL ".join(parts) + ") x LEFT JOIN produkt p ON p.nummer=x.nummer"
           " WHERE COALESCE(x.user, '') <> COALESCE(?, '') AND COALESCE(x.at, '') > ?")
    params += [me, since or ""]
    if user:
        sql += " AND x.user = ?"
        params.append(user)
    sql += " ORDER BY x.at DESC LIMIT ?"
    params.append(limit)
    return conn.execute(sql, params).fetchall()


def imports_since(conn, since: str) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM imports WHERE imported_at > ? ORDER BY id", (since,)).fetchall()


# ----------------------------------------------------------------------------------------------
# Sicherung / Notfall-Wiederherstellung der gemeinsamen Datenbank
def backup_db(conn, dest):
    """Konsistente Kopie der laufenden Datenbank (SQLite-Backup-API, auch während andere arbeiten)."""
    target = sqlite3.connect(str(dest))
    try:
        conn.backup(target)
    finally:
        target.close()


def check_backup(path) -> dict:
    """Prüft, ob eine Datei eine HMV-Datenbank ist; gibt Kennzahlen zurück, sonst ValueError."""
    try:
        src = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            tables = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"imports", "produkt", "history"} <= tables:
                raise ValueError("Die Datei ist keine HMV-Viewer-Datenbank.")
            return {"versionen": src.execute("SELECT COUNT(*) FROM imports").fetchone()[0],
                    "produkte": src.execute("SELECT COUNT(*) FROM produkt").fetchone()[0],
                    "listen": src.execute("SELECT COUNT(*) FROM liste").fetchone()[0] if "liste" in tables else 0}
        finally:
            src.close()
    except sqlite3.DatabaseError as exc:
        raise ValueError(f"Die Datei ist keine lesbare Datenbank: {exc}") from exc


def restore_db(conn, src_path):
    """Überschreibt den KOMPLETTEN Inhalt der Datenbank von conn mit der Sicherung src_path."""
    check_backup(src_path)
    src = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True)
    try:
        src.backup(conn)
    finally:
        src.close()


def lists_for_product(conn, nummer: str) -> list[sqlite3.Row]:
    """Gemeinsame Listen, die das Produkt direkt oder über eine ganze Gruppe enthalten."""
    return conn.execute("SELECT DISTINCT l.id, l.name FROM liste_eintrag e JOIN liste l ON l.id=e.liste_id"
                        " WHERE e.nummer=? OR (length(e.nummer)<10 AND substr(?, 1, length(e.nummer))=e.nummer)"
                        " ORDER BY l.name COLLATE NOCASE", (nummer, nummer)).fetchall()


# ----------------------------------------------------------------------------------------------
# Hierarchie
class Names:
    """Bezeichnungen der Hierarchieebenen (aktueller Stand)."""

    def __init__(self, conn):
        self.gruppe, self.ort, self.ug, self.art = {}, {}, {}, {}
        for r in conn.execute("SELECT entity, gruppe, ort, untergruppe, art, data FROM stamm"):
            name = json.loads(r["data"]).get("BEZEICHNUNG") or ""
            e = r["entity"]
            if e == "GRUPPE":
                self.gruppe[r["gruppe"]] = name
            elif e == "ORT":
                self.ort[r["ort"]] = name
            elif e == "UNTERGRUPPE":
                self.ug[(r["gruppe"], r["ort"], r["untergruppe"])] = name
            elif e == "ART":
                self.art[(r["gruppe"], r["ort"], r["untergruppe"], r["art"])] = name

    def path(self, p) -> dict:
        g, o, u, a = p["gruppe"], p["ort"], p["untergruppe"], p["art"]
        return {
            "gruppe": f"{g:02d} {self.gruppe.get(g, '')}".strip(),
            "ort": f"{o:02d} {self.ort.get(o, '')}".strip(),
            "untergruppe": f"{g:02d}.{o:02d}.{u:02d} {self.ug.get((g, o, u), '')}".strip(),
            "art": f"{g:02d}.{o:02d}.{u:02d}.{a} {self.art.get((g, o, u, a), '')}".strip(),
        }


def hierarchy_tree(conn) -> list[dict]:
    """Gruppe > Anwendungsort > Untergruppe > Produktart mit Produktanzahl (aktive Produkte).

    Knoten: {"label", "key": {gruppe/ort/untergruppe/art}, "count", "children": [...]}
    """
    names = Names(conn)
    counts: dict[tuple, int] = {}
    for r in conn.execute("SELECT gruppe, ort, untergruppe, art, COUNT(*) c FROM produkt WHERE active=1"
                          " GROUP BY gruppe, ort, untergruppe, art"):
        g, o, u, a, c = r["gruppe"], r["ort"], r["untergruppe"], r["art"], r["c"]
        for key in ((g,), (g, o), (g, o, u), (g, o, u, a)):
            counts[key] = counts.get(key, 0) + c

    groups: dict = {}
    for r in conn.execute("SELECT gruppe, ort, untergruppe, art FROM stamm WHERE entity='ART' AND active=1"
                          " ORDER BY gruppe, ort, untergruppe, art"):
        g, o, u, a = r["gruppe"], r["ort"], r["untergruppe"], r["art"]
        groups.setdefault(g, {}).setdefault(o, {}).setdefault(u, []).append(a)

    tree = []
    for g, orte in sorted(groups.items()):
        gnode = {"label": f"{g:02d} {names.gruppe.get(g, '')}", "key": {"gruppe": g},
                 "count": counts.get((g,), 0), "children": []}
        for o, ugs in sorted(orte.items()):
            onode = {"label": f"{o:02d} {names.ort.get(o, '')}", "key": {"gruppe": g, "ort": o},
                     "count": counts.get((g, o), 0), "children": []}
            for u, arts in sorted(ugs.items()):
                unode = {"label": f"{g:02d}.{o:02d}.{u:02d} {names.ug.get((g, o, u), '')}",
                         "key": {"gruppe": g, "ort": o, "untergruppe": u},
                         "count": counts.get((g, o, u), 0), "children": []}
                for a in arts:
                    unode["children"].append({
                        "label": f"{g:02d}.{o:02d}.{u:02d}.{a} {names.art.get((g, o, u, a), '')}",
                        "key": {"gruppe": g, "ort": o, "untergruppe": u, "art": a},
                        "count": counts.get((g, o, u, a), 0), "children": []})
                onode["children"].append(unode)
            gnode["children"].append(onode)
        tree.append(gnode)
    return tree
