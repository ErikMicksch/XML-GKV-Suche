"""Pfad-Konfiguration.

Datenbank-Speicherort (in dieser Reihenfolge):
  1. Umgebungsvariable HMV_DB
  2. Pfad-Datei hmv_pfade.json neben dem Programm (bzw. Umgebungsvariable HMV_PFADE) – zieht die Datenbank oder der
     Sicherungsordner um, genügt es, diese eine Datei auszutauschen:
         {"datenbank": "\\\\server\\HMV\\data\\hmv.db", "sicherungen": "\\\\server\\HMV\\data\\sicherungen"}
     Relative Angaben gelten ab dem Ordner der Datei, %VARIABLEN% werden ersetzt. Fehlt "sicherungen":
     Ordner "sicherungen" neben der Datenbank.
  3. Ordner "data" neben der gestarteten Datei (Einzeldatei hmv_viewer_app.py bzw. .exe, sonst Projektordner) –
     liegt dort schon eine hmv.db, wird sie auch ohne Schreibrecht genutzt (dann nur lesen)
  4. sonst, falls dort nicht beschreibbar: %LOCALAPPDATA%\\HMV-Viewer (Windows) bzw. ~/HMV-Viewer
Es werden nie Adminrechte benötigt: geschrieben wird nur in den Datenordner, %LOCALAPPDATA%, die Benutzer-Registry
(HKCU) und den selbst gewählten Favoriten-Ordner.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# In der Einzeldatei-Variante gibt es kein __file__ (Module liegen im Speicher)
PROJECT_ROOT = Path(__file__).resolve().parent.parent if "__file__" in globals() else Path.cwd()


def app_dir() -> Path:
    """Ordner der gestarteten Anwendung (portabel)."""
    env = os.environ.get("HMV_APP_DIR")
    if env:
        return Path(env)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return PROJECT_ROOT


def _writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("x")
        probe.unlink()
        return True
    except OSError:
        return False


PATHS_FILE = "hmv_pfade.json"
PATH_KEYS = ("datenbank", "sicherungen")


def paths_file() -> Path:
    env = os.environ.get("HMV_PFADE")
    return Path(env) if env else app_dir() / PATHS_FILE


def load_paths() -> dict:
    """Pfade aus der Pfad-Datei ({"datenbank": Path, "sicherungen": Path}); fehlt die Datei: {}."""
    f = paths_file()
    try:
        raw = f.read_text(encoding="utf-8-sig")
    except OSError:
        return {}
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("kein JSON-Objekt")
    except ValueError as exc:   # lieber deutlich abbrechen als still eine falsche Datenbank öffnen
        raise ValueError(f"Die Pfad-Datei {f} ist fehlerhaft ({exc}).\n"
                         'Erwartet z. B.: {"datenbank": "D:\\\\HMV\\\\hmv.db", "sicherungen": "D:\\\\HMV\\\\sicherungen"}\n'
                         "Hinweis: Backslashes in JSON doppelt schreiben (\\\\) oder / verwenden.") from exc
    return {k: f.parent / os.path.expandvars(str(data[k]).strip()) for k in PATH_KEYS if str(data.get(k) or "").strip()}


def save_paths(db_path, backup_dir) -> Path:
    """Pfad-Datei schreiben (atomar); OSError z. B. ohne Schreibrecht geht an den Aufrufer."""
    f = paths_file()
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps({"datenbank": str(db_path), "sicherungen": str(backup_dir)}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    os.replace(tmp, f)
    return f


def backup_dir(db_path) -> Path:
    """Ordner für Sicherungen: aus der Pfad-Datei, sonst „sicherungen“ neben der Datenbank."""
    return load_paths().get("sicherungen") or Path(db_path).parent / "sicherungen"


def default_db_path() -> Path:
    env = os.environ.get("HMV_DB")
    if env:
        return Path(env).expanduser()
    configured = load_paths().get("datenbank")
    if configured:
        return configured
    beside = app_dir() / "data"
    if (beside / "hmv.db").exists():   # gemeinsame DB neben der .exe immer nutzen, auch ohne Schreibrecht (nur lesen)
        return beside / "hmv.db"
    if _writable_dir(beside):
        return beside / "hmv.db"
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) / "HMV-Viewer" if local else Path.home() / "HMV-Viewer"
    return base / "hmv.db"
