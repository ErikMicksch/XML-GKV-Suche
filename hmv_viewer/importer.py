"""Import einer HMV-XML mit Versionierung.

Jeder Import erzeugt eine neue Version (Tabelle imports). Gegenüber dem bisherigen Bestand werden
Produkte (und Gruppen/Orte/Untergruppen/Arten) verglichen und jede Abweichung in der Tabelle history
festgehalten:
    NEU          Datensatz war bisher nicht vorhanden
    GEAENDERT    mindestens ein Feld hat sich geändert (alt/neu je Feld gespeichert)
    ENTFERNT     Datensatz fehlt in der neuen XML (bleibt als inaktiv erhalten)
    REAKTIVIERT  zuvor entfernter Datensatz ist wieder enthalten
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass, field
from typing import Callable

from .model import (ENTITY_DEFS, ENTITY_BY_NAME, GEAENDERT, ENTFERNT, NEU, REAKTIVIERT, make_key)
from .parser import open_source, parse_records, sha256_of_source, source_date_from_name

Progress = Callable[[str, int, int], None]

PRODUKT_COLS = ("onl_status", "bezeichnung", "hersteller", "merkmale", "aufnahmedatum", "aenderungsdatum")
MIN_RATIO = 0.5  # Schutz gegen unvollständige Dateien


class DuplicateImport(Exception):
    def __init__(self, import_id: int):
        super().__init__(f"Diese Datei wurde bereits als Version {import_id} importiert.")
        self.import_id = import_id


class SuspiciousImport(Exception):
    def __init__(self, old: int, new: int):
        super().__init__(
            f"Die neue Datei enthält nur {new} Produkte, bisher sind {old} aktiv. "
            "Möglicherweise ist die Datei unvollständig."
        )
        self.old, self.new = old, new


class EmptyImport(Exception):
    pass


@dataclass
class ImportResult:
    import_id: int
    n_total: int = 0
    n_new: int = 0
    n_changed: int = 0
    n_removed: int = 0
    n_reactivated: int = 0
    n_unchanged: int = 0
    n_stamm_changes: int = 0
    first_import: bool = False
    warnings: list = field(default_factory=list)


def _hash(values: tuple) -> str:
    return hashlib.sha1(repr(values).encode("utf-8")).hexdigest()


def _diff(old: dict, new: dict) -> dict:
    return {f: [old.get(f), new.get(f)] for f in new if old.get(f) != new.get(f)}


def import_file(conn: sqlite3.Connection, path, *, force: bool = False,
                progress: Progress | None = None) -> ImportResult:
    """Importiert eine XML/ZIP und versioniert alle Änderungen. Läuft in EINER Transaktion."""
    progress = progress or (lambda stage, cur, total: None)

    progress("Prüfsumme berechnen …", 0, 0)
    sha = sha256_of_source(path)
    row = conn.execute("SELECT id FROM imports WHERE source_sha256=?", (sha,)).fetchone()
    if row and not force:
        raise DuplicateImport(row["id"])

    # --- Einlesen -----------------------------------------------------------------------------
    progress("XML einlesen …", 0, 0)
    meta: dict = {}
    warnings: list[str] = []
    data: dict[str, dict] = {e.name: {} for e in ENTITY_DEFS}
    with open_source(path) as (stream, display_name, inner_name):
        count = 0
        for item in parse_records(stream):
            kind = item[0]
            if kind == "META":
                meta = item[1]
            elif kind == "WARN":
                warnings.append(item[1])
            else:
                entity, kv, fields = item
                k = make_key(entity, kv)
                if k in data[entity]:
                    warnings.append(f"{entity} {k}: doppelt in der Datei, letzter Eintrag gilt")
                data[entity][k] = (kv, fields)
                count += 1
                if count % 2000 == 0:
                    progress("XML einlesen …", count, 0)
    n_products = len(data["PRODUKT"])
    if n_products == 0:
        raise EmptyImport("In der Datei wurden keine Produkte (HMV_PRODUKT) gefunden.")

    old_active = conn.execute("SELECT COUNT(*) FROM produkt WHERE active=1").fetchone()[0]
    if not force and old_active and n_products < old_active * MIN_RATIO:
        raise SuspiciousImport(old_active, n_products)

    # --- Vergleichen und schreiben --------------------------------------------------------------
    now = dt.datetime.now().isoformat(timespec="seconds")
    src_date = source_date_from_name(inner_name, display_name)
    first = conn.execute("SELECT COUNT(*) FROM imports").fetchone()[0] == 0
    result = ImportResult(import_id=0, n_total=n_products, first_import=first, warnings=warnings)

    conn.execute("BEGIN IMMEDIATE")   # wartet, falls gerade ein anderer Benutzer schreibt
    try:
        # erneut prüfen: ein anderer Benutzer kann dieselbe Datei inzwischen importiert haben
        row = conn.execute("SELECT id FROM imports WHERE source_sha256=?", (sha,)).fetchone()
        if row and not force:
            raise DuplicateImport(row["id"])
        first = conn.execute("SELECT COUNT(*) FROM imports").fetchone()[0] == 0
        result.first_import = first
        cur = conn.execute(
            "INSERT INTO imports(imported_at, source_name, source_sha256, source_date, logische_version, n_total)"
            " VALUES (?,?,?,?,?,?)",
            (now, display_name, sha, src_date, meta.get("logische_version"), n_products))
        imp_id = cur.lastrowid
        result.import_id = imp_id

        for edef in ENTITY_DEFS:
            if edef.name == "PRODUKT":
                _apply_produkte(conn, imp_id, data["PRODUKT"], result, progress)
            else:
                _apply_stamm(conn, imp_id, edef.name, data[edef.name], result)

        conn.execute(
            "UPDATE imports SET n_new=?, n_changed=?, n_removed=?, n_reactivated=?, n_unchanged=?, n_stamm_changes=?"
            " WHERE id=?",
            (result.n_new, result.n_changed, result.n_removed, result.n_reactivated,
             result.n_unchanged, result.n_stamm_changes, imp_id))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    progress("Fertig", 1, 1)
    return result


# ---------------------------------------------------------------------------------------------------
def _apply_produkte(conn, imp_id, new: dict, result: ImportResult, progress: Progress):
    existing = {r["nummer"]: (r["content_hash"], r["active"])
                for r in conn.execute("SELECT nummer, content_hash, active FROM produkt")}
    inserts, updates, history = [], [], []
    total = len(new)
    for i, (k, (kv, fields)) in enumerate(new.items(), 1):
        values = tuple(fields[c.upper()] for c in PRODUKT_COLS)
        h = _hash(values)
        old = existing.get(k)
        if old is None:
            inserts.append((k, kv["GRUPPE"], kv["ORT"], kv["UNTERGRUPPE"], kv["ART"], kv["PRODUKT"],
                            *values, h, imp_id, imp_id, NEU))
            history.append((imp_id, "PRODUKT", k, NEU, None))
            result.n_new += 1
        elif old[0] != h or not old[1]:
            row = conn.execute("SELECT * FROM produkt WHERE nummer=?", (k,)).fetchone()
            old_fields = {c.upper(): row[c] for c in PRODUKT_COLS}
            diff = _diff(old_fields, fields)
            ctype = REAKTIVIERT if not old[1] else GEAENDERT
            updates.append((*values, h, imp_id, ctype, k))
            history.append((imp_id, "PRODUKT", k, ctype, json.dumps(diff, ensure_ascii=False)))
            if ctype == REAKTIVIERT:
                result.n_reactivated += 1
            else:
                result.n_changed += 1
        else:
            result.n_unchanged += 1
        if i % 5000 == 0:
            progress("Produkte vergleichen …", i, total)

    removed = [k for k, (_, active) in existing.items() if active and k not in new]
    result.n_removed += len(removed)
    for k in removed:
        history.append((imp_id, "PRODUKT", k, ENTFERNT, None))

    progress("Produkte speichern …", 0, 0)
    conn.executemany(
        "INSERT INTO produkt(nummer,gruppe,ort,untergruppe,art,produkt,"
        "onl_status,bezeichnung,hersteller,merkmale,aufnahmedatum,aenderungsdatum,"
        "content_hash,active,first_import,last_import_change,last_change_type)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?,?)", inserts)
    conn.executemany(
        "UPDATE produkt SET onl_status=?,bezeichnung=?,hersteller=?,merkmale=?,aufnahmedatum=?,aenderungsdatum=?,"
        "content_hash=?,active=1,removed_import=NULL,last_import_change=?,last_change_type=? WHERE nummer=?",
        updates)
    conn.executemany(
        "UPDATE produkt SET active=0, removed_import=?, last_import_change=?, last_change_type=? WHERE nummer=?",
        [(imp_id, imp_id, ENTFERNT, k) for k in removed])
    conn.executemany("INSERT INTO history(import_id,entity,k,change_type,changes) VALUES (?,?,?,?,?)", history)


def _apply_stamm(conn, imp_id, entity: str, new: dict, result: ImportResult):
    edef = ENTITY_BY_NAME[entity]
    existing = {r["k"]: (r["content_hash"], r["active"], r["data"])
                for r in conn.execute("SELECT k, content_hash, active, data FROM stamm WHERE entity=?", (entity,))}
    history = []
    for k, (kv, fields) in new.items():
        h = _hash(tuple(fields[f] for f in edef.fields))
        payload = json.dumps(fields, ensure_ascii=False)
        old = existing.get(k)
        if old is None:
            conn.execute(
                "INSERT INTO stamm(entity,k,gruppe,ort,untergruppe,art,data,content_hash,active,"
                "first_import,last_import_change,last_change_type) VALUES (?,?,?,?,?,?,?,?,1,?,?,?)",
                (entity, k, kv.get("GRUPPE"), kv.get("ORT"), kv.get("UNTERGRUPPE"), kv.get("ART"),
                 payload, h, imp_id, imp_id, NEU))
            history.append((imp_id, entity, k, NEU, None))
            result.n_stamm_changes += 1
        elif old[0] != h or not old[1]:
            ctype = REAKTIVIERT if not old[1] else GEAENDERT
            diff = _diff(json.loads(old[2]), fields)
            conn.execute(
                "UPDATE stamm SET data=?, content_hash=?, active=1, last_import_change=?, last_change_type=?"
                " WHERE entity=? AND k=?", (payload, h, imp_id, ctype, entity, k))
            history.append((imp_id, entity, k, ctype, json.dumps(diff, ensure_ascii=False)))
            result.n_stamm_changes += 1
    for k, (_, active, _) in existing.items():
        if active and k not in new:
            conn.execute("UPDATE stamm SET active=0, last_import_change=?, last_change_type=? WHERE entity=? AND k=?",
                         (imp_id, ENTFERNT, entity, k))
            history.append((imp_id, entity, k, ENTFERNT, None))
            result.n_stamm_changes += 1
    conn.executemany("INSERT INTO history(import_id,entity,k,change_type,changes) VALUES (?,?,?,?,?)", history)
