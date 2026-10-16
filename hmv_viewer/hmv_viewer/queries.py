"""Lese-Abfragen für GUI und Export."""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from typing import Iterator

from .model import ENTITY_LABELS, FIELD_LABELS, format_nummer

ORDER_COLUMNS = {
    "nummer": "p.nummer",
    "bezeichnung": "p.bezeichnung COLLATE NOCASE",
    "hersteller": "p.hersteller COLLATE NOCASE",
    "art": "p.gruppe, p.ort, p.untergruppe, p.art",
    "aufnahme": "p.aufnahmedatum",
    "aenderung": "p.aenderungsdatum",
    "version": "p.last_import_change",
}


@dataclass
class ProductFilter:
    text: str = ""
    in_merkmale: bool = False
    status: str = "aktiv"          # aktiv | entfernt | alle
    gruppe: int | None = None
    ort: int | None = None
    untergruppe: int | None = None
    art: int | None = None
    import_id: int | None = None   # nur Produkte, die in dieser Version eine Änderung hatten
    change_type: str | None = None  # NEU | GEAENDERT | ENTFERNT | REAKTIVIERT


def _like(term: str) -> str:
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _build(f: ProductFilter):
    """Gibt (join_sql, where_sql, params) zurück. Tabellen-Alias: p (produkt), h (history)."""
    join, where, params = "", [], []
    if f.import_id is not None:
        join = " JOIN history h ON h.entity='PRODUKT' AND h.k=p.nummer AND h.import_id=?"
        params.append(f.import_id)
        if f.change_type:
            where.append("h.change_type=?")
            params.append(f.change_type)
    elif f.change_type:
        where.append("p.nummer IN (SELECT k FROM history WHERE entity='PRODUKT' AND change_type=?)")
        params.append(f.change_type)

    if f.status == "aktiv":
        where.append("p.active=1")
    elif f.status == "entfernt":
        where.append("p.active=0")

    for col in ("gruppe", "ort", "untergruppe", "art"):
        v = getattr(f, col)
        if v is not None:
            where.append(f"p.{col}=?")
            params.append(v)

    for term in f.text.split():
        clauses = ["fold(p.bezeichnung) LIKE ? ESCAPE '\\'", "fold(p.hersteller) LIKE ? ESCAPE '\\'"]
        params += [_like(term.casefold())] * 2
        if f.in_merkmale:
            clauses.append("fold(p.merkmale) LIKE ? ESCAPE '\\'")
            params.append(_like(term.casefold()))
        digits = term.replace(".", "")
        if digits.isdigit():
            if "." in term:   # 01.24.01 -> Präfix-Suche in der Hilfsmittelnummer
                clauses.append("p.nummer LIKE ? ESCAPE '\\'")
                params.append(digits + "%")
            else:
                clauses.append("p.nummer LIKE ? ESCAPE '\\'")
                params.append(_like(digits))
        where.append("(" + " OR ".join(clauses) + ")")
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
    sql, params = "SELECT COUNT(*) FROM history WHERE import_id=?", [import_id]
    if change_type:
        sql += " AND change_type=?"
        params.append(change_type)
    return conn.execute(sql, params).fetchone()[0]


def version_changes(conn, import_id: int, change_type: str | None = None, limit: int = 5000) -> list[dict]:
    sql = ("SELECT h.entity, h.k, h.change_type, h.changes, p.bezeichnung AS pname, s.data AS sdata"
           " FROM history h"
           " LEFT JOIN produkt p ON h.entity='PRODUKT' AND p.nummer=h.k"
           " LEFT JOIN stamm s ON s.entity=h.entity AND s.k=h.k"
           " WHERE h.import_id=?")
    params: list = [import_id]
    if change_type:
        sql += " AND h.change_type=?"
        params.append(change_type)
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
