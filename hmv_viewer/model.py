"""Datenmodell des Hilfsmittelverzeichnisses (nach ESOL-HMV-1.0.0.xsd).

Die 10-stellige Hilfsmittelnummer setzt sich zusammen aus
    Produktgruppe (2) + Anwendungsort (2) + Untergruppe (2) + Produktart (1) + Produkt (3)
Beispiel: Gruppe 1, Ort 24, Untergruppe 1, Art 0, Produkt 2  ->  0124010002  (01.24.01.0002)
Die ersten 7 Stellen bezeichnen die Produktart ("7-Steller").
"""
from __future__ import annotations

from dataclasses import dataclass

NAMESPACE = "GI4X:/xml-schema/ESOL-HMV/1.0"

# Änderungstypen (in der DB ASCII, Anzeige deutsch)
NEU = "NEU"
GEAENDERT = "GEAENDERT"
ENTFERNT = "ENTFERNT"
REAKTIVIERT = "REAKTIVIERT"

CHANGE_LABELS = {
    NEU: "Neu",
    GEAENDERT: "Geändert",
    ENTFERNT: "Entfernt",
    REAKTIVIERT: "Wieder aufgenommen",
}

ENTITY_LABELS = {
    "GRUPPE": "Produktgruppe",
    "ORT": "Anwendungsort",
    "UNTERGRUPPE": "Untergruppe",
    "ART": "Produktart",
    "PRODUKT": "Produkt",
}

FIELD_LABELS = {
    "ONL_STATUS": "Online-Status",
    "BEZEICHNUNG": "Bezeichnung",
    "DEFINITION": "Definition",
    "INDIKATION": "Indikation",
    "QUERVERWEISE": "Querverweise",
    "ANFORDERUNGEN": "Anforderungen",
    "BESCHREIBUNG": "Beschreibung",
    "HERSTELLER": "Hersteller",
    "MERKMALE": "Merkmale",
    "AUFNAHMEDATUM": "Aufnahmedatum",
    "AENDERUNGSDATUM": "Änderungsdatum",
}


@dataclass(frozen=True)
class EntityDef:
    name: str            # interner Name, z. B. "PRODUKT"
    tag: str             # XML-Elementname, z. B. "HMV_PRODUKT"
    key_fields: tuple    # Schlüsselfelder (xs:int)
    fields: tuple        # Datenfelder (ONL_STATUS = int, Rest Text)


ENTITY_DEFS = (
    EntityDef("GRUPPE", "HMV_GRUPPE", ("GRUPPE",),
              ("ONL_STATUS", "BEZEICHNUNG", "DEFINITION", "INDIKATION", "QUERVERWEISE")),
    EntityDef("ORT", "HMV_ORT", ("ORT",),
              ("ONL_STATUS", "BEZEICHNUNG")),
    EntityDef("UNTERGRUPPE", "HMV_UNTERGRUPPE", ("GRUPPE", "ORT", "UNTERGRUPPE"),
              ("ONL_STATUS", "BEZEICHNUNG", "ANFORDERUNGEN")),
    EntityDef("ART", "HMV_ART", ("GRUPPE", "ORT", "UNTERGRUPPE", "ART"),
              ("ONL_STATUS", "BEZEICHNUNG", "BESCHREIBUNG", "INDIKATION")),
    EntityDef("PRODUKT", "HMV_PRODUKT", ("GRUPPE", "ORT", "UNTERGRUPPE", "ART", "PRODUKT"),
              ("ONL_STATUS", "BEZEICHNUNG", "HERSTELLER", "MERKMALE", "AUFNAHMEDATUM", "AENDERUNGSDATUM")),
)
ENTITY_BY_TAG = {e.tag: e for e in ENTITY_DEFS}
ENTITY_BY_NAME = {e.name: e for e in ENTITY_DEFS}
INT_FIELDS = {"ONL_STATUS"}


def nummer10(gruppe: int, ort: int, untergruppe: int, art: int, produkt: int) -> str:
    """Baut die 10-stellige Hilfsmittelnummer (nur Ziffern)."""
    return f"{gruppe:02d}{ort:02d}{untergruppe:02d}{art:01d}{produkt:03d}"


def format_nummer(nummer: str) -> str:
    """0124010002 -> 01.24.01.0002 (10-Steller); 7-Steller 0124010 -> 01.24.01.0."""
    n = nummer or ""
    if len(n) == 10:
        return f"{n[0:2]}.{n[2:4]}.{n[4:6]}.{n[6:10]}"
    if len(n) == 7:
        return f"{n[0:2]}.{n[2:4]}.{n[4:6]}.{n[6]}"
    return n


def make_key(entity: str, kv: dict) -> str:
    """Eindeutiger Textschlüssel eines Datensatzes (für Stammdaten-Tabelle und Historie)."""
    g, o, u, a, p = (kv.get(x) for x in ("GRUPPE", "ORT", "UNTERGRUPPE", "ART", "PRODUKT"))
    if entity == "GRUPPE":
        return f"{g:02d}"
    if entity == "ORT":
        return f"{o:02d}"
    if entity == "UNTERGRUPPE":
        return f"{g:02d}.{o:02d}.{u:02d}"
    if entity == "ART":
        return f"{g:02d}.{o:02d}.{u:02d}.{a}"
    if entity == "PRODUKT":
        return nummer10(g, o, u, a, p)
    raise ValueError(entity)
