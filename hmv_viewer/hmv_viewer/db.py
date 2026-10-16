"""SQLite-Schema und Verbindungsaufbau."""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS imports(
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    imported_at      TEXT NOT NULL,          -- Zeitpunkt des Imports (lokal, ISO)
    source_name      TEXT,
    source_sha256    TEXT,
    source_date      TEXT,                   -- Stand-Datum (aus Dateiname, z. B. 20260831)
    logische_version TEXT,                   -- Attribut logische_version der XML
    n_total          INTEGER DEFAULT 0,      -- Produkte in der Datei
    n_new            INTEGER DEFAULT 0,
    n_changed        INTEGER DEFAULT 0,
    n_removed        INTEGER DEFAULT 0,
    n_reactivated    INTEGER DEFAULT 0,
    n_unchanged      INTEGER DEFAULT 0,
    n_stamm_changes  INTEGER DEFAULT 0       -- Änderungen an Gruppen/Orten/Untergruppen/Arten
);

CREATE TABLE IF NOT EXISTS produkt(
    nummer             TEXT PRIMARY KEY,     -- 10-stellig, nur Ziffern
    gruppe INTEGER, ort INTEGER, untergruppe INTEGER, art INTEGER, produkt INTEGER,
    onl_status         INTEGER,
    bezeichnung        TEXT,
    hersteller         TEXT,
    merkmale           TEXT,
    aufnahmedatum      TEXT,
    aenderungsdatum    TEXT,
    content_hash       TEXT,
    active             INTEGER NOT NULL DEFAULT 1,
    first_import       INTEGER,
    last_import_change INTEGER,
    last_change_type   TEXT,
    removed_import     INTEGER
);
CREATE INDEX IF NOT EXISTS ix_produkt_gruppe ON produkt(gruppe, ort, untergruppe, art);
CREATE INDEX IF NOT EXISTS ix_produkt_lastchg ON produkt(last_import_change);

CREATE TABLE IF NOT EXISTS stamm(
    entity             TEXT NOT NULL,
    k                  TEXT NOT NULL,
    gruppe INTEGER, ort INTEGER, untergruppe INTEGER, art INTEGER,
    data               TEXT NOT NULL,        -- JSON der Datenfelder
    content_hash       TEXT,
    active             INTEGER NOT NULL DEFAULT 1,
    first_import       INTEGER,
    last_import_change INTEGER,
    last_change_type   TEXT,
    PRIMARY KEY(entity, k)
);

CREATE TABLE IF NOT EXISTS history(
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id   INTEGER NOT NULL REFERENCES imports(id),
    entity      TEXT NOT NULL,
    k           TEXT NOT NULL,
    change_type TEXT NOT NULL,
    changes     TEXT                         -- JSON {"FELD": [alt, neu]}
);
CREATE INDEX IF NOT EXISTS ix_history_entity_k ON history(entity, k);
CREATE INDEX IF NOT EXISTS ix_history_import ON history(import_id, entity, change_type);
"""


def _fold(value):
    return value.casefold() if isinstance(value, str) else None


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), isolation_level=None, timeout=60)  # manuelle Transaktionen
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.create_function("fold", 1, _fold, deterministic=True)
    conn.executescript(SCHEMA)
    conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
    return conn
