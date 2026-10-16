"""Einstieg:  python -m hmv_viewer            -> GUI
             python -m hmv_viewer import DATEI.xml|zip [--force]
             python -m hmv_viewer export AUSGABE.xlsx [--scope aktiv|alle] [--suche TEXT] [--version N] [--ohne-historie]
             python -m hmv_viewer versionen
"""
from __future__ import annotations

import argparse
import sys

from . import db, exporter, importer, queries
from .config import default_db_path
from .model import CHANGE_LABELS


def _cli_progress(stage, cur, total):
    if total:
        print(f"\r{stage} {cur}/{total}   ", end="", flush=True)
    else:
        print(f"\r{stage}                ", end="", flush=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="hmv_viewer", description="Hilfsmittelverzeichnis-Viewer")
    parser.add_argument("--db", help="Pfad zur SQLite-Datenbank (Standard: data/hmv.db)")
    sub = parser.add_subparsers(dest="cmd")

    p_imp = sub.add_parser("import", help="XML/ZIP importieren (neue Version anlegen)")
    p_imp.add_argument("datei")
    p_imp.add_argument("--force", action="store_true", help="auch bei identischer Datei / Plausibilitätswarnung importieren")

    p_exp = sub.add_parser("export", help="Produkte nach Excel exportieren")
    p_exp.add_argument("ausgabe")
    p_exp.add_argument("--scope", choices=["aktiv", "alle"], default="aktiv")
    p_exp.add_argument("--suche", default="")
    p_exp.add_argument("--version", type=int, help="nur Produkte mit Änderung in dieser Version")
    p_exp.add_argument("--ohne-historie", action="store_true")

    sub.add_parser("versionen", help="Importierte Versionen auflisten")

    args = parser.parse_args(argv)
    path = args.db or default_db_path()

    if args.cmd is None:
        from .gui import run_gui
        run_gui(path)
        return 0

    conn = db.connect(path)
    if args.cmd == "import":
        try:
            r = importer.import_file(conn, args.datei, force=args.force, progress=_cli_progress)
        except importer.DuplicateImport as e:
            print(f"\n{e} Mit --force trotzdem importieren.")
            return 2
        except importer.SuspiciousImport as e:
            print(f"\n{e} Mit --force trotzdem importieren.")
            return 2
        print(f"\nVersion {r.import_id}: {r.n_total} Produkte | neu {r.n_new} | geändert {r.n_changed} | "
              f"entfernt {r.n_removed} | wieder aufgenommen {r.n_reactivated} | unverändert {r.n_unchanged} | "
              f"Stammdaten-Änderungen {r.n_stamm_changes}")
        for w in r.warnings[:20]:
            print("Warnung:", w)
    elif args.cmd == "export":
        f = queries.ProductFilter(text=args.suche, status="aktiv" if args.scope == "aktiv" else "alle",
                                  import_id=args.version)
        res = exporter.export_excel(conn, args.ausgabe, f, include_history=not args.ohne_historie,
                                    progress=_cli_progress)
        print(f"\n{res['products']} Produkte nach {args.ausgabe} exportiert.")
    elif args.cmd == "versionen":
        for v in reversed(queries.list_versions(conn)):
            print(f"V{v['id']}  {v['imported_at']}  Stand {v['source_date']}  {v['n_total']} Produkte  "
                  f"neu {v['n_new']}  geändert {v['n_changed']}  entfernt {v['n_removed']}  {v['source_name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
