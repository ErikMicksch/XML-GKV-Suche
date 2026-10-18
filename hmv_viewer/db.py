"""SQLite-Schema und Verbindungsaufbau."""
from __future__ import annotations

import os
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

-- Gemeinsame Produktlisten (für alle Benutzer der Datenbank sichtbar), beliebig verschachtelt
CREATE TABLE IF NOT EXISTS liste(
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id  INTEGER REFERENCES liste(id) ON DELETE CASCADE,   -- NULL = oberste Ebene
    name       TEXT NOT NULL COLLATE NOCASE,
    created_by TEXT,
    created_at TEXT,
    changed_by TEXT,                -- zuletzt geändert von (Benutzer-Nachname)
    changed_at TEXT
);
CREATE TABLE IF NOT EXISTS liste_eintrag(
    liste_id INTEGER NOT NULL REFERENCES liste(id) ON DELETE CASCADE,
    nummer   TEXT NOT NULL,          -- Produkt (10 Stellen) oder ganze Gruppe (Präfix 2/4/6/7 Stellen)
    added_by TEXT,
    added_at TEXT,
    PRIMARY KEY(liste_id, nummer)
);

-- Benutzer (nur Nachname, ohne Passwort) - zur Anzeige, wer gemeinsame Daten zuletzt geändert hat
CREATE TABLE IF NOT EXISTS benutzer(
    name       TEXT PRIMARY KEY COLLATE NOCASE,
    created_at TEXT
);

-- Kommentare je Produkt (für alle sichtbar, mit Name und Zeitpunkt) – ersetzen die frühere einzelne Notiz
CREATE TABLE IF NOT EXISTS kommentar(
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    nummer TEXT NOT NULL,
    text   TEXT NOT NULL,
    user   TEXT,
    at     TEXT
);
CREATE INDEX IF NOT EXISTS ix_kommentar_nummer ON kommentar(nummer, id);

-- Verlauf der gemeinsamen Listen (wer hat wann was geändert)
CREATE TABLE IF NOT EXISTS liste_log(
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    liste_id INTEGER REFERENCES liste(id) ON DELETE CASCADE,
    aktion   TEXT NOT NULL,
    detail   TEXT,
    user     TEXT,
    at       TEXT
);
CREATE INDEX IF NOT EXISTS ix_liste_log ON liste_log(liste_id, id);

-- Aktivitäten (z. B. Farbmarkierungen), damit Kollegen unter „Änderungen anderer“ sehen, wer was markiert hat
CREATE TABLE IF NOT EXISTS aktivitaet(
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    at     TEXT,
    user   TEXT,
    art    TEXT NOT NULL,          -- 'kategorie'
    nummer TEXT,
    detail TEXT,                   -- z. B. Name der Kategorie ('' = entfernt)
    farbe  TEXT
);
CREATE INDEX IF NOT EXISTS ix_aktivitaet_at ON aktivitaet(at);

-- v2.2: einzelne gemeinsame Notiz je Produkt (wird beim Start in Kommentare übernommen)
CREATE TABLE IF NOT EXISTS notiz_gemeinsam(
    nummer     TEXT PRIMARY KEY,
    text       TEXT NOT NULL,
    changed_by TEXT,
    changed_at TEXT
);

"""

TEMP_SCHEMA = """
-- Favoriten liegen je Benutzer in einer Datei (favorites.py) und werden pro Verbindung hier hineinkopiert
CREATE TEMP TABLE IF NOT EXISTS favorit(k TEXT PRIMARY KEY);
CREATE TEMP TABLE IF NOT EXISTS notiz(k TEXT PRIMARY KEY, text TEXT);
CREATE TEMP TABLE IF NOT EXISTS markierung(k TEXT PRIMARY KEY, kat TEXT);
CREATE TEMP TABLE IF NOT EXISTS pliste(liste TEXT, k TEXT, PRIMARY KEY(liste, k));
"""


def _fold(value):
    return value.casefold() if isinstance(value, str) else None


def _migrate_lists(conn):
    """v2.0 -> v2.1: Listen bekommen parent_id (Unterlisten); Name nur noch je Ebene eindeutig."""
    if "parent_id" not in {r[1] for r in conn.execute("PRAGMA table_info(liste)")}:
        conn.execute("PRAGMA foreign_keys=OFF")   # sonst würde DROP TABLE die Einträge per Kaskade löschen
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                if "parent_id" not in {r[1] for r in conn.execute("PRAGMA table_info(liste)")}:  # evtl. parallel erledigt
                    conn.execute("CREATE TABLE liste_neu(id INTEGER PRIMARY KEY AUTOINCREMENT,"
                                 " parent_id INTEGER REFERENCES liste(id) ON DELETE CASCADE,"
                                 " name TEXT NOT NULL COLLATE NOCASE, created_by TEXT, created_at TEXT)")
                    conn.execute("INSERT INTO liste_neu(id, name, created_by, created_at)"
                                 " SELECT id, name, created_by, created_at FROM liste")
                    conn.execute("DROP TABLE liste")
                    conn.execute("ALTER TABLE liste_neu RENAME TO liste")
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
        finally:
            conn.execute("PRAGMA foreign_keys=ON")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(liste)")}
    for col in ("changed_by", "changed_at"):   # v2.1 -> v2.2
        if col not in cols:
            try:
                conn.execute(f"ALTER TABLE liste ADD COLUMN {col} TEXT")
            except sqlite3.OperationalError as exc:   # gleichzeitig von einem anderen Programm ergänzt
                if "duplicate column" not in str(exc):
                    raise
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_liste_name ON liste(COALESCE(parent_id, 0), name COLLATE NOCASE)")


def ensure_schema(conn):
    """Tabellen anlegen bzw. ältere Datenbanken (auch wiederhergestellte Sicherungen) auf den aktuellen Stand bringen."""
    conn.executescript(SCHEMA)
    conn.executescript(TEMP_SCHEMA)
    _migrate_lists(conn)
    _migrate_shared_notes(conn)


def _migrate_shared_notes(conn):
    """v2.2 -> v2.3: gemeinsame Notizen werden zu (ersten) Kommentaren."""
    if not conn.execute("SELECT 1 FROM notiz_gemeinsam LIMIT 1").fetchone():
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("INSERT INTO kommentar(nummer, text, user, at)"
                     " SELECT nummer, text, changed_by, changed_at FROM notiz_gemeinsam")
        conn.execute("DELETE FROM notiz_gemeinsam")
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def is_read_only(path: str | Path) -> bool:
    """True, wenn der Benutzer die Datenbank (oder ihren Ordner, für die Journal-Datei) nicht beschreiben darf."""
    path = Path(path)
    return (path.exists() and not os.access(path, os.W_OK)) or not os.access(path.parent, os.W_OK)


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), isolation_level=None, timeout=60)  # manuelle Transaktionen
    conn.row_factory = sqlite3.Row
    # Mehrere Benutzer über ein Netzlaufwerk: WAL braucht gemeinsamen Speicher auf EINEM Rechner und ist auf
    # Netzlaufwerken nicht sicher -> klassisches Rollback-Journal (DELETE) mit voller Synchronisierung.
    # Klappt die Umstellung nicht (Nur-Lese-Zugriff oder ein älteres Programm hält die DB offen), geht es trotzdem weiter.
    try:
        conn.execute("PRAGMA journal_mode=DELETE")
    except sqlite3.OperationalError:
        pass
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("PRAGMA cache_size=-100000")   # bis ~100 MB: großer Import blockiert Leser erst beim COMMIT
    conn.execute("PRAGMA foreign_keys=ON")
    conn.create_function("fold", 1, _fold, deterministic=True)
    try:
        ensure_schema(conn)
        if conn.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
            conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
    except sqlite3.OperationalError as exc:
        if "readonly" not in str(exc) and "read-only" not in str(exc):
            raise
        conn.executescript(TEMP_SCHEMA)   # Nur-Lese-Zugriff: wenigstens die TEMP-Tabellen für Filter anlegen
    return conn
