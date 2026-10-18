"""Pfad-Konfiguration.

Datenbank-Speicherort (in dieser Reihenfolge):
  1. Umgebungsvariable HMV_DB
  2. Ordner "data" neben der gestarteten Datei (Einzeldatei hmv_viewer_app.py bzw. .exe, sonst Projektordner)
  3. falls dort nicht beschreibbar: %LOCALAPPDATA%\\HMV-Viewer (Windows) bzw. ~/HMV-Viewer
"""
from __future__ import annotations

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


def default_db_path() -> Path:
    env = os.environ.get("HMV_DB")
    if env:
        return Path(env).expanduser()
    beside = app_dir() / "data"
    if _writable_dir(beside):
        return beside / "hmv.db"
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) / "HMV-Viewer" if local else Path.home() / "HMV-Viewer"
    return base / "hmv.db"
