"""Merkmal-Suche: Text vereinheitlichen, Volltext-Index (SQLite FTS5), Suchsyntax.

Suchsyntax (ein Feld):  Wörter = alle müssen vorkommen (Wortanfang genügt, Zahlen nur als ganzes Wort)
                        "genaue Phrase"   -Wort (ausschließen)   01.24.01 / 0124010001 = Hilfsmittelnummer
Vereinheitlicht wird beim Indexieren UND beim Suchen gleich: Silbentrennung am Zeilenende entfernt, Buchstaben/Ziffern
getrennt („PR70“ = „PR 70“), Groß/klein egal, Satzzeichen trennen Wörter („4,7 kg“ = „4.7kg“).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Platzsparend: Volltext-Index ohne Textkopie (content=''), rowid = Hilfsmittelnummer als Zahl (+24 MB bei der echten HMV).
# Die frühere Eigenschaft/Wert-Auswahl ist entfallen – ihre Tabellen werden entfernt.
SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS produkt_fts USING fts5(
    bez, merk, content = '', tokenize = "unicode61 remove_diacritics 0");
DROP TABLE IF EXISTS produkt_merkmal;
DROP TABLE IF EXISTS merkmal_wert;
"""
FTS_MATCH = "CAST(p.nummer AS INTEGER) IN (SELECT rowid FROM produkt_fts WHERE produkt_fts MATCH ?)"
FREE_TEXT = "Beschreibung"   # Fließtext ohne „Name: Wert“ – im Detail nicht anklickbar
MAX_VALUE = 150              # längere Werte sind Fließtext – im Detail nicht anklickbar

_BOUNDARY = re.compile(r"(?<=[^\W\d_])(?=\d)|(?<=\d)(?=[^\W\d_])")
_NUMBER_TOKEN = re.compile(r"\d[\d.]*")


def unwrap(text: str) -> str:
    """Silbentrennung am Zeilenende entfernen („hö-\\nhenverstellbar“ -> „höhenverstellbar“), Zeilen bleiben."""
    return re.sub(r"(?<=[^\W\d_])-\n(?=[a-zäöüß])", "", text or "")


def normalize(text: str) -> str:
    return _BOUNDARY.sub(" ", unwrap(text))


def parse_merkmale(text):
    """Merkmale in vergleichbare Eigenschaften zerlegen (drei Formen im HMV):

    „Name: Wert“-Zeilen (z. B. Hörgeräte)        -> {"Name": "Wert"}
    Abschnitt „Beschreibung / Aufbau:“ + Text     -> {"Beschreibung / Aufbau": "<Text>"}
    reiner Fließtext mit harten Umbrüchen         -> {"Beschreibung": "<Text, Umbrüche/Silbentrennung entfernt>"}
    """
    out = {}
    section = FREE_TEXT

    def append(key, line):
        prev = out.get(key, "")
        if prev.endswith("-") and line[:1].islower() and prev[-2:-1].isalpha():
            out[key] = prev[:-1] + line
        else:
            out[key] = f"{prev} {line}".strip()

    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        key, sep, value = line.partition(":")
        key, value = key.strip(" -•\t"), value.strip()
        if sep and key and len(key) <= 70 and len(key.split()) <= 8:   # kurzer Name vor dem Doppelpunkt, kein Satz
            if value:
                out[key] = value
                section = FREE_TEXT
            else:
                section = key
                out.setdefault(section, "")
        else:
            append(section, line)
    return {k: v for k, v in out.items() if v}


# ---------------------------------------------------------------------------------------------- Index
def ensure(conn):
    """Index anlegen; ist er leer (ältere Datenbank), einmalig aufbauen."""
    conn.executescript(SCHEMA)
    if conn.execute("SELECT 1 FROM produkt LIMIT 1").fetchone() and not conn.execute(
            "SELECT rowid FROM produkt_fts LIMIT 1").fetchone():
        conn.execute("BEGIN IMMEDIATE")
        try:
            if not conn.execute("SELECT rowid FROM produkt_fts LIMIT 1").fetchone():   # evtl. parallel erledigt
                rebuild(conn)
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise


def rebuild(conn):
    """Volltext-Index komplett neu aufbauen (läuft in der Transaktion des Aufrufers)."""
    conn.execute("INSERT INTO produkt_fts(produkt_fts) VALUES('delete-all')")   # so leert man einen Index ohne Textkopie
    conn.executemany("INSERT INTO produkt_fts(rowid, bez, merk) VALUES(?, ?, ?)",
                     [(int(r[0]), normalize(f"{r[1] or ''} {r[2] or ''}"), normalize(r[3] or ""))
                      for r in conn.execute("SELECT nummer, bezeichnung, hersteller, merkmale FROM produkt")])


# ---------------------------------------------------------------------------------------------- Suchsyntax
@dataclass
class Query:
    include: list = field(default_factory=list)   # FTS-Ausdrücke, alle müssen passen
    exclude: list = field(default_factory=list)   # FTS-Ausdrücke, dürfen nicht passen
    numbers: list = field(default_factory=list)   # Hilfsmittelnummern (Ziffern, mit Punkt = Präfix)
    words: list = field(default_factory=list)     # positive Wörter (für Notizen-Suche und Markierung)

    def fts(self, columns):
        if not self.include:
            return None
        expr = " AND ".join(self.include) + "".join(f" NOT {e}" for e in self.exclude)
        return "{" + " ".join(columns) + "} : (" + expr + ")"


def _phrase(text, prefix):
    tokens = re.findall(r"\w+", normalize(text))
    if not tokens:
        return None
    last_is_number = tokens[-1].isdigit()
    return '"' + " ".join(tokens) + '"' + (" *" if prefix and not last_is_number else "")


def parse_query(text: str) -> Query:
    q = Query()
    for m in re.finditer(r'(-?)"([^"]*)"|(\S+)', text or ""):
        neg, quoted, word = m.group(1) == "-", m.group(2), m.group(3)
        if word and word.startswith("-") and len(word) > 1:
            neg, word = True, word[1:]
        raw = quoted if quoted is not None else word
        digits = raw.replace(".", "")
        if quoted is None and not neg and _NUMBER_TOKEN.fullmatch(raw) and len(digits) >= 4:
            q.numbers.append(raw)     # sieht aus wie eine Hilfsmittelnummer
            continue
        expr = _phrase(raw, prefix=quoted is None)
        if expr is None:
            continue
        (q.exclude if neg else q.include).append(expr)
        if not neg:
            q.words += re.findall(r"\w+", raw) if quoted is None else [raw]
    return q


def fundstelle(merkmale: str, words) -> str:
    """Erste Merkmal-Zeile, die das erste Suchwort enthält (für die Spalte „Fundstelle“)."""
    if not merkmale or not words:
        return ""
    def flat(text):   # Groß/klein, Leerraum („Energiequelle:  Typ“) und PR70/PR 70 vereinheitlichen
        return " ".join(normalize(text).casefold().split())

    needle = flat(words[0])
    for key, value in parse_merkmale(merkmale).items():   # wie im Detail angezeigt
        line = value if key == FREE_TEXT else f"{key}: {value}"
        if needle in flat(line):
            return line
    return ""
