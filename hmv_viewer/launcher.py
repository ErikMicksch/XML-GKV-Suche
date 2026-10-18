"""Gemeinsamer Start (Einzeldatei, .exe, Projektordner): Konsole/DPI/Fehlerdialog."""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


def _prepare_streams():
    if sys.stdout is None:   # fensterlose .exe: keine Konsole vorhanden
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")


def _report_crash(exc_text):
    where = ""
    try:
        import getpass
        import tempfile
        from .config import default_db_path
        name = f"fehler_{getpass.getuser()}.log"   # je Benutzer: mehrere Personen starten dieselbe .exe
        for folder in (default_db_path().parent, Path(tempfile.gettempdir())):
            try:
                log = folder / name
                log.write_text(exc_text, encoding="utf-8")
                break
            except OSError:
                continue
        where = f"\n\nDetails in: {log}"
    except Exception:
        pass
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        QApplication.instance() or QApplication([])
        QMessageBox.critical(None, "HMV-Viewer – unerwarteter Fehler", exc_text[-1500:] + where)
    except Exception:
        print(exc_text, file=sys.__stderr__ or sys.stderr)


def _qt_missing_hint():
    return ("Für die Oberfläche wird PySide6 benötigt (einmalig, ohne Admin-Rechte):\n"
            "    python -m pip install --user PySide6\n"
            "Die Kommandozeile (import / export / versionen) funktioniert auch ohne.")


def run() -> int:
    _prepare_streams()   # DPI-Skalierung übernimmt Qt selbst
    try:
        from .__main__ import main
        # GUI-Start ohne Argumente braucht PySide6 -> freundliche Meldung statt Traceback
        if len(sys.argv) == 1:
            try:
                import PySide6  # noqa: F401
            except ImportError:
                print(_qt_missing_hint())
                return 1
        return main() or 0
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0
    except BaseException:
        _report_crash(traceback.format_exc())
        return 1
