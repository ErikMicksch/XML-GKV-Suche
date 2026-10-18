"""Minimaler, abhängigkeitsfreier XLSX-Schreiber (nur Standardbibliothek, streamend).

Kann: mehrere Blätter, Kopfzeile mit Format, Spaltenbreiten, fixierte Kopfzeile, Autofilter,
Text/Zahl/Datum, Zeilenumbruch, Hintergrundfarben für Änderungstypen.
"""
from __future__ import annotations

import datetime as dt
import re
import zipfile
from xml.sax.saxutils import escape

# Zell-Formate (Index in cellXfs)
DEFAULT, HEADER, DATE, WRAP, FILL_NEU, FILL_GEAENDERT, FILL_ENTFERNT, FILL_REAKTIVIERT = range(8)
FILL_BY_CHANGE = {"NEU": FILL_NEU, "GEAENDERT": FILL_GEAENDERT,
                  "ENTFERNT": FILL_ENTFERNT, "REAKTIVIERT": FILL_REAKTIVIERT}

_EPOCH = dt.date(1899, 12, 30)
_ILLEGAL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")
_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def col_letter(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


class Sheet:
    def __init__(self, wb: "Workbook", index: int, name: str, header, widths, freeze: bool):
        self.wb, self.index, self.name = wb, index, name
        self.ncols = len(header) if header else (len(widths) if widths else 1)
        self.has_header = bool(header)
        self.nrows = 0
        self._buf: list[str] = []
        self._closed = False
        self._fh = wb._zf.open(f"xl/worksheets/sheet{index}.xml", "w", force_zip64=True)
        pane = ('<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
                '<selection pane="bottomLeft"/>') if (freeze and header) else ""
        selected = ' tabSelected="1"' if index == 1 else ""
        cols = ""
        if widths:
            cols = "<cols>" + "".join(
                f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>' for i, w in enumerate(widths, 1)) + "</cols>"
        self._write(f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    f'<worksheet xmlns="{_NS}"><sheetViews><sheetView{selected} workbookViewId="0">{pane}</sheetView>'
                    f'</sheetViews><sheetFormatPr defaultRowHeight="15"/>{cols}<sheetData>')
        if header:
            self.append([(h, HEADER) for h in header])

    def _write(self, text: str):
        self._fh.write(text.encode("utf-8"))

    def append(self, row):
        """row: Liste aus Werten oder (Wert, Format)-Tupeln. Werte: None, str, int, float, bool, date."""
        self.nrows += 1
        r = self.nrows
        cells = []
        for ci, item in enumerate(row, 1):
            value, style = item if isinstance(item, tuple) else (item, DEFAULT)
            if value is None:
                if style:
                    cells.append(f'<c r="{col_letter(ci)}{r}" s="{style}"/>')
                continue
            ref = f'{col_letter(ci)}{r}'
            s = f' s="{style}"' if style else ""
            if isinstance(value, bool):
                cells.append(f'<c r="{ref}"{s} t="b"><v>{int(value)}</v></c>')
            elif isinstance(value, (int, float)):
                cells.append(f'<c r="{ref}"{s}><v>{value}</v></c>')
            elif isinstance(value, dt.date):
                s = f' s="{style or DATE}"'
                cells.append(f'<c r="{ref}"{s}><v>{(value - _EPOCH).days}</v></c>')
            else:
                text = escape(_ILLEGAL.sub("", str(value)))
                cells.append(f'<c r="{ref}"{s} t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>')
        self._buf.append(f'<row r="{r}">{"".join(cells)}</row>')
        if len(self._buf) >= 500:
            self._flush()

    def _flush(self):
        if self._buf:
            self._write("".join(self._buf))
            self._buf = []

    def close(self):
        if self._closed:
            return
        self._flush()
        self._write("</sheetData>")
        if self.has_header and self.nrows >= 1:
            self._write(f'<autoFilter ref="A1:{col_letter(self.ncols)}{self.nrows}"/>')
        self._write("</worksheet>")
        self._fh.close()
        self._closed = True


class Workbook:
    def __init__(self, path):
        self._zf = zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED)
        self._sheets: list[Sheet] = []

    def add_sheet(self, name: str, header=None, widths=None, freeze: bool = True) -> Sheet:
        if self._sheets:
            self._sheets[-1].close()   # es wird immer nur ein Blatt gleichzeitig geschrieben
        name = re.sub(r"[\\/*?:\[\]]", "_", name)[:31]
        sheet = Sheet(self, len(self._sheets) + 1, name, header, widths, freeze)
        self._sheets.append(sheet)
        return sheet

    def close(self):
        for sh in self._sheets:
            sh.close()
        n = len(self._sheets)
        z = self._zf
        sheets_xml = "".join(f'<sheet name="{escape(s.name, {chr(34): "&quot;"})}" sheetId="{i}" r:id="rId{i}"/>'
                             for i, s in enumerate(self._sheets, 1))
        names = "".join(
            f'<definedName name="_xlnm._FilterDatabase" localSheetId="{i}" hidden="1">'
            f"'{escape(s.name)}'!$A$1:${col_letter(s.ncols)}${s.nrows}</definedName>"
            for i, s in enumerate(self._sheets) if s.has_header and s.nrows >= 1)
        z.writestr("xl/workbook.xml",
                   f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   f'<workbook xmlns="{_NS}" xmlns:r="{_REL}"><bookViews><workbookView/></bookViews>'
                   f'<sheets>{sheets_xml}</sheets>'
                   f'{"<definedNames>" + names + "</definedNames>" if names else ""}</workbook>')
        rels = "".join(f'<Relationship Id="rId{i}" Type="{_REL}/worksheet" Target="worksheets/sheet{i}.xml"/>'
                       for i in range(1, n + 1))
        rels += f'<Relationship Id="rId{n + 1}" Type="{_REL}/styles" Target="styles.xml"/>'
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>')
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   f'<Relationship Id="rId1" Type="{_REL}/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        overrides = "".join(
            f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for i in range(1, n + 1))
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" '
                   'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   '<Override PartName="/xl/styles.xml" '
                   'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                   f'{overrides}</Types>')
        z.writestr("xl/styles.xml", _STYLES)
        z.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.close()
        else:
            for sh in self._sheets:
                try:
                    sh.close()
                except Exception:
                    pass
            self._zf.close()


def _fill(rgb):
    return f'<fill><patternFill patternType="solid"><fgColor rgb="FF{rgb}"/><bgColor indexed="64"/></patternFill></fill>'


_STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<styleSheet xmlns="{_NS}">'
    '<numFmts count="1"><numFmt numFmtId="164" formatCode="DD.MM.YYYY"/></numFmts>'
    '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
    '<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font></fonts>'
    '<fills count="7"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'
    + _fill("1F4E78") + _fill("E2F0D9") + _fill("FFF2CC") + _fill("F8CBAD") + _fill("DDEBF7") + '</fills>'
    '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
    '<cellXfs count="8">'
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
    '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1">'
    '<alignment vertical="center" wrapText="1"/></xf>'
    '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1">'
    '<alignment vertical="top" wrapText="1"/></xf>'
    '<xf numFmtId="0" fontId="0" fillId="3" borderId="0" xfId="0" applyFill="1"/>'
    '<xf numFmtId="0" fontId="0" fillId="4" borderId="0" xfId="0" applyFill="1"/>'
    '<xf numFmtId="0" fontId="0" fillId="5" borderId="0" xfId="0" applyFill="1"/>'
    '<xf numFmtId="0" fontId="0" fillId="6" borderId="0" xfId="0" applyFill="1"/>'
    '</cellXfs>'
    '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
    '</styleSheet>'
)
