"""Excel-Export (eigener, abhängigkeitsfreier XLSX-Schreiber, siehe xlsx.py)."""
from __future__ import annotations

import datetime as dt
import json
from typing import Callable

from . import queries, xlsx
from .model import CHANGE_LABELS, FIELD_LABELS, format_nummer
from .queries import Names, ProductFilter

Progress = Callable[[str, int, int], None]

_MAX_CELL = 32000  # Excel erlaubt 32.767 Zeichen pro Zelle


def _txt(v):
    if v is None:
        return None
    s = str(v)
    return s[:_MAX_CELL] + " …[gekürzt]" if len(s) > _MAX_CELL else s


def _date(v):
    if not v:
        return None
    try:
        return dt.date.fromisoformat(v[:10])
    except ValueError:
        return v


def export_excel(conn, path, f: ProductFilter, *, include_history: bool = True,
                 include_versions: bool = True, include_initial_in_history: bool = False,
                 progress: Progress | None = None, favorites=None) -> dict:
    """Schreibt die Produkte (gemäß Filter f) nach `path`. Gibt Zähler zurück.

    favorites: optional FavoriteStore -> zusätzliche Spalten „Favorit“ und „Notiz (persönlich)“.
    """
    progress = progress or (lambda s, c, t: None)
    names = Names(conn)
    vlabels = queries.version_labels(conn)
    first_id = queries.first_import_id(conn)
    total = queries.count_products(conn, f)
    n = n_hist = 0

    header = ["Hilfsmittelnummer (10-stellig)", "Hilfsmittelnummer", "Produktart-Nr. (7-stellig)",
              "Produktgruppe", "Anwendungsort", "Untergruppe", "Produktart", "Bezeichnung", "Hersteller",
              "Merkmale", "Aufnahmedatum", "Änderungsdatum (HMV)", "Status", "Letzte Änderung (Version)",
              "Änderungstyp", "Kommentare (für alle sichtbar)"]
    widths = [18, 16, 14, 28, 28, 34, 38, 50, 32, 70, 14, 14, 10, 22, 16, 60]
    comments = {}
    for c in conn.execute("SELECT * FROM kommentar ORDER BY id"):
        comments.setdefault(c["nummer"], []).append(f"{c['user'] or '?'}, {(c['at'] or '')[:16].replace('T', ' ')}: {c['text']}")
    if favorites is not None:
        header += ["Favorit", "Kategorie (persönlich)", "Notiz (persönlich)"]
        widths += [9, 20, 50]

    with xlsx.Workbook(path) as wb:
        # ---- Blatt Produkte ------------------------------------------------------------------
        ws = wb.add_sheet("Produkte", header=header, widths=widths)
        for p in queries.iter_products(conn, f):
            path_ = names.path(p)
            nr = p["nummer"]
            ctype = p["last_change_type"]
            is_baseline = p["last_import_change"] == first_id and ctype == "NEU"
            fill = xlsx.DEFAULT if is_baseline else xlsx.FILL_BY_CHANGE.get(ctype, xlsx.DEFAULT)
            row = [
                nr, format_nummer(nr), format_nummer(nr[:7]),
                path_["gruppe"], path_["ort"], path_["untergruppe"], path_["art"],
                _txt(p["bezeichnung"]), _txt(p["hersteller"]), (_txt(p["merkmale"]), xlsx.WRAP),
                _date(p["aufnahmedatum"]), _date(p["aenderungsdatum"]),
                ("aktiv" if p["active"] else "entfernt", fill),
                ("Erstimport" if is_baseline else vlabels.get(p["last_import_change"], ""), fill),
                ("" if is_baseline else CHANGE_LABELS.get(ctype, ctype or ""), fill),
            ]
            row.append((_txt("\n".join(comments[nr])), xlsx.WRAP) if nr in comments else None)
            if favorites is not None:
                cat = favorites.categories.get(favorites.marks.get(nr), {}).get("name", "")
                row += ["ja" if nr in favorites.favs else "", cat, (_txt(favorites.notes.get(nr)), xlsx.WRAP)]
            ws.append(row)
            n += 1
            if n % 2000 == 0:
                progress("Produkte schreiben …", n, total)

        # ---- Blatt Historie ------------------------------------------------------------------
        if include_history:
            progress("Änderungshistorie schreiben …", 0, 0)
            wh = wb.add_sheet(
                "Änderungshistorie",
                header=["Version", "Import am", "Hilfsmittelnummer (10-stellig)", "Hilfsmittelnummer",
                        "Bezeichnung (aktuell)", "Änderungstyp", "Feld", "Alter Wert", "Neuer Wert"],
                widths=[22, 18, 18, 16, 50, 16, 18, 60, 60])
            base_filter = ProductFilter(**{**f.__dict__, "import_id": None, "change_type": None})
            _, where, params = queries._build(base_filter)
            conds = ["h.entity='PRODUKT'"]
            if where:
                conds.append(where[len(" WHERE "):])
            params = list(params)
            if f.import_id is not None:
                conds.append("h.import_id=?")
                params.append(f.import_id)
            if f.change_type:
                cond, extra = queries._type_cond("h", f.change_type)
                conds.append(cond)
                params += extra
            if not include_initial_in_history and first_id is not None:
                conds.append("NOT (h.import_id=? AND h.change_type='NEU')")
                params.append(first_id)
            sql = ("SELECT h.import_id, h.k, h.change_type, h.changes, i.imported_at, p.bezeichnung"
                   " FROM history h JOIN imports i ON i.id=h.import_id JOIN produkt p ON p.nummer=h.k"
                   " WHERE " + " AND ".join(conds) + " ORDER BY h.import_id DESC, h.k")
            for r in conn.execute(sql, params):
                base = [vlabels.get(r["import_id"], ""), r["imported_at"].replace("T", " "), r["k"],
                        format_nummer(r["k"]), _txt(r["bezeichnung"])]
                typ = (CHANGE_LABELS.get(r["change_type"], r["change_type"]),
                       xlsx.FILL_BY_CHANGE.get(r["change_type"], xlsx.DEFAULT))
                changes = json.loads(r["changes"]) if r["changes"] else {}
                lines = [(FIELD_LABELS.get(fld, fld), old, new) for fld, (old, new) in changes.items()] or [("", None, None)]
                for fld, old, new in lines:
                    wh.append(base + [typ, fld, (_txt(old), xlsx.WRAP), (_txt(new), xlsx.WRAP)])
                    n_hist += 1

        # ---- Blatt Versionen -----------------------------------------------------------------
        if include_versions:
            wv = wb.add_sheet(
                "Versionen",
                header=["Version", "Import am", "Quelle", "Stand-Datum", "logische Version", "Produkte gesamt", "Neu",
                        "Geändert", "Entfernt", "Wieder aufgenommen", "Umgruppiert", "Unverändert", "Änderungen Stammdaten"],
                widths=[10, 20, 52, 14, 16, 16, 10, 10, 10, 18, 12, 14, 22])
            for v in sorted(queries.list_versions(conn), key=lambda r: r["id"]):
                wv.append([v["id"], v["imported_at"].replace("T", " "), v["source_name"], _date(v["source_date"]),
                           v["logische_version"], v["n_total"], v["n_new"], v["n_changed"], v["n_removed"],
                           v["n_reactivated"], v["n_regrouped"], v["n_unchanged"], v["n_stamm_changes"]])

    progress("Fertig", total, total)
    return {"products": n, "history_rows": n_hist}
