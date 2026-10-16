"""Gemeinsamer Start (Einzeldatei, .exe, Projektordner): Konsole/DPI/Fehlerdialog."""
from __future__ import annotations

import os
import sys
import traceback


def _prepare_streams():
    if sys.stdout is None:   # fensterlose .exe: keine Konsole vorhanden
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")


def _enable_dpi_awareness():
    if sys.platform == "win32":   # scharfe Schrift auf hochauflösenden Monitoren
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


def _report_crash(exc_text):
    where = ""
    try:
        from .config import default_db_path
        log = default_db_path().parent / "fehler.log"
        log.write_text(exc_text, encoding="utf-8")
        where = f"\n\nDetails in: {log}"
    except Exception:
        pass
    try:
        import tkinter
        from tkinter import messagebox
        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror("HMV-Viewer – unerwarteter Fehler", exc_text[-1500:] + where)
    except Exception:
        print(exc_text, file=sys.__stderr__ or sys.stderr)


def _tk_missing_hint():
    return ("tkinter ist in dieser Python-Installation nicht vorhanden.\n"
            "Windows/macOS: Python von python.org installieren (tkinter ist dabei).\n"
            "Linux:  sudo apt install python3-tk")


def run() -> int:
    _prepare_streams()
    _enable_dpi_awareness()
    try:
        from .__main__ import main
        # GUI-Start ohne Argumente braucht tkinter -> freundliche Meldung statt Traceback
        if len(sys.argv) == 1:
            try:
                import tkinter  # noqa: F401
            except ImportError:
                print(_tk_missing_hint())
                return 1
        return main() or 0
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0
    except BaseException:
        _report_crash(traceback.format_exc())
        return 1
