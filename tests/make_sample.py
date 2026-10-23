"""Erzeugt kleine HMV-Beispieldateien (gleiche Struktur wie die echte XML) für die Tests."""
from xml.sax.saxutils import escape

HEAD = ('<?xml version="1.0" encoding="utf-8"?>\n<hv:HMV xmlns:xsi="http://www.w3.org/2001/XMLSchema" '
        'xmlns:GI4X-basis="GI4X:/xml-schema/GI4X-basis/2.0" logische_version="2.0.0" '
        'xmlns:hv="GI4X:/xml-schema/ESOL-HMV/1.0">\n')


def _el(tag, **fields):
    inner = "".join(f"<hv:{k}>{escape(str(v))}</hv:{k}>" for k, v in fields.items() if v is not None)
    return f"  <hv:{tag}>{inner}</hv:{tag}>\n"


def write_sample(path, variant=1):
    gname = "Absauggeräte" if variant == 1 else "Absauggeräte (neu)"
    out = [HEAD]
    out.append(_el("HMV_GRUPPE", GRUPPE=1, BEZEICHNUNG=gname, DEFINITION="Definition"))
    out.append(_el("HMV_ORT", ORT=24, BEZEICHNUNG="Atmungsorgane"))
    out.append(_el("HMV_UNTERGRUPPE", GRUPPE=1, ORT=24, UNTERGRUPPE=1, BEZEICHNUNG="Sekret-Absauggeräte"))
    out.append(_el("HMV_ART", GRUPPE=1, ORT=24, UNTERGRUPPE=1, ART=0, BEZEICHNUNG="Geräte, netzabhängig"))
    prods = {
        1: ("Muster Pumpe A", "Muster GmbH", "Gewicht: 4,5 kg\nLeistung: 100 VA", "2020-01-01"),
        2: ("Muster Pumpe B", "Muster GmbH", None, "2020-02-01"),
        3: ("Beispiel Pumpe C", "Beispiel AG", "Ä Ö Ü ß", "2020-03-01"),
        4: ("Nicht besetzt", "Nicht besetzt", None, "2020-04-01"),
    }
    if variant == 2:
        prods[1] = ("Muster Pumpe A", "Muster GmbH", "Gewicht: 4,7 kg\nLeistung: 100 VA", "2020-01-01")
        del prods[2]
        prods[5] = ("Neue Pumpe E", "Muster GmbH", "neu", "2026-02-01")
    if variant == 3:   # Umgruppierung: Pumpe B bekommt Nummer 7; Platzhalter 4 -> 8 darf NICHT als Umgruppierung zählen
        prods[7] = prods.pop(2)
        prods[8] = prods.pop(4)
    for nr, (name, maker, merk, date) in prods.items():
        out.append(_el("HMV_PRODUKT", GRUPPE=1, ORT=24, UNTERGRUPPE=1, ART=0, PRODUKT=nr,
                       BEZEICHNUNG=name, HERSTELLER=maker, MERKMALE=merk, AUFNAHMEDATUM=date))
    out.append("</hv:HMV>\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("".join(out))
    return path
