"""Streaming-Parser für die HMV-XML (auch direkt aus einer ZIP-Datei)."""
from __future__ import annotations

import contextlib
import hashlib
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Iterator

from .model import ENTITY_BY_TAG, INT_FIELDS, NAMESPACE, make_key

_NS = "{" + NAMESPACE + "}"


class SourceError(Exception):
    pass


@contextlib.contextmanager
def open_source(path: str | Path):
    """Öffnet eine .xml oder .zip (mit der HMV-XML darin) und liefert (stream, anzeige_name, datei_name)."""
    path = Path(path)
    if not path.is_file():
        raise SourceError(f"Datei nicht gefunden: {path}")
    if zipfile.is_zipfile(path):
        zf = zipfile.ZipFile(path)
        try:
            candidates = [i for i in zf.infolist()
                          if i.filename.lower().endswith(".xml") and not i.is_dir()]
            if not candidates:
                raise SourceError("Die ZIP-Datei enthält keine XML-Datei.")
            # bevorzugt XML im Wurzelverzeichnis, sonst die größte
            candidates.sort(key=lambda i: ("/" in i.filename.strip("/"), -i.file_size))
            info = candidates[0]
            with zf.open(info) as fh:
                yield fh, f"{path.name}!{info.filename}", info.filename
        finally:
            zf.close()
    else:
        with open(path, "rb") as fh:
            yield fh, path.name, path.name


def sha256_of_source(path: str | Path) -> str:
    h = hashlib.sha256()
    with open_source(path) as (fh, _, _):
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def source_date_from_name(*names: str) -> str | None:
    """Zieht ein Datum der Form YYYYMMDD aus dem Dateinamen (z. B. 20260831_HMV.xml)."""
    for name in names:
        m = re.search(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)", name or "")
        if m:
            y, mo, d = m.groups()
            if 1 <= int(mo) <= 12 and 1 <= int(d) <= 31:
                return f"{y}-{mo}-{d}"
    return None


def parse_records(stream) -> Iterator[tuple]:
    """Liefert zuerst ("META", {Attribute der Wurzel}) und danach (entity, key_values, fields).

    key_values: {"GRUPPE": 1, ...} (int); fields: {"BEZEICHNUNG": "...", ...} (fehlende Felder = None).
    Ungültige Datensätze werden als ("WARN", text) gemeldet.
    """
    root = None
    for event, el in ET.iterparse(stream, events=("start", "end")):
        if event == "start":
            if root is None:
                root = el
                yield "META", dict(el.attrib)
            continue
        if not el.tag.startswith(_NS):
            continue
        edef = ENTITY_BY_TAG.get(el.tag[len(_NS):])
        if edef is None:
            continue
        values = {}
        for child in el:
            values[child.tag[len(_NS):] if child.tag.startswith(_NS) else child.tag] = child.text
        el.clear()
        root.clear()
        try:
            kv = {f: int(values[f].strip()) for f in edef.key_fields}
        except (KeyError, AttributeError, ValueError):
            yield "WARN", f"{edef.name}: Datensatz ohne gültigen Schlüssel übersprungen ({values.get('BEZEICHNUNG')!r})"
            continue
        fields = {}
        for f in edef.fields:
            v = values.get(f)
            if v is not None and f in INT_FIELDS:
                try:
                    v = int(v.strip())
                except ValueError:
                    v = None
            fields[f] = v
        yield edef.name, kv, fields
