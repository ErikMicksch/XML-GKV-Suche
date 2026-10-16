"""Bündelt das Paket hmv_viewer in EINE Python-Datei:  python tools/build_single_file.py

Ergebnis: hmv_viewer_app.py im Projektordner. Läuft nur mit Python (Standardbibliothek + tkinter):
keine Installation, kein pip, keine Admin-Rechte. Die Moduldateien stecken komprimiert in der Datei
und werden beim Start direkt aus dem Speicher geladen (es wird nichts entpackt oder geschrieben).
"""
import base64
import io
import pathlib
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
PKG = ROOT / "hmv_viewer"
OUT = ROOT / "hmv_viewer_app.py"

TEMPLATE = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HMV-Viewer {version} - Hilfsmittelverzeichnis einsehen, versionieren, nach Excel exportieren.

Einzeldatei: einfach starten mit   python hmv_viewer_app.py   (Windows: Doppelklick bzw. py hmv_viewer_app.py)
Benoetigt nur Python 3.9+ mit tkinter. Keine Installation, keine Admin-Rechte.
Die Datenbank liegt im Ordner "data" neben dieser Datei.

AUTOMATISCH ERZEUGT aus dem Projekt (tools/build_single_file.py) - nicht von Hand bearbeiten.
"""
import base64
import importlib.abc
import importlib.util
import io
import os
import sys
import zipfile

_BUNDLE = (
{payload}
)


class _BundleFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Laedt das Paket hmv_viewer direkt aus dem eingebetteten ZIP (nur im Arbeitsspeicher)."""

    def __init__(self):
        self.zf = zipfile.ZipFile(io.BytesIO(base64.b64decode("".join(_BUNDLE))))
        self.names = set(self.zf.namelist())

    def _path(self, fullname):
        base = fullname.replace(".", "/")
        if base + ".py" in self.names:
            return base + ".py", False
        if base + "/__init__.py" in self.names:
            return base + "/__init__.py", True
        return None, False

    def find_spec(self, fullname, path=None, target=None):
        entry, is_pkg = self._path(fullname)
        if entry is None:
            return None
        return importlib.util.spec_from_loader(fullname, self, is_package=is_pkg, origin="bundle:" + entry)

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        entry, _ = self._path(module.__spec__.name)
        code = compile(self.zf.read(entry), "bundle:" + entry, "exec")
        exec(code, module.__dict__)

    def get_source(self, fullname):
        entry, _ = self._path(fullname)
        return self.zf.read(entry).decode("utf-8") if entry else None


if __name__ == "__main__":
    os.environ.setdefault("HMV_APP_DIR", os.path.dirname(os.path.abspath(__file__)))
    sys.meta_path.insert(0, _BundleFinder())
    from hmv_viewer.launcher import run
    sys.exit(run())
'''


def main():
    sys.path.insert(0, str(ROOT))
    version = None
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(PKG.glob("*.py")):
            z.write(f, f"hmv_viewer/{f.name}")
            if f.name == "__init__.py":
                for line in f.read_text(encoding="utf-8").splitlines():
                    if line.startswith("__version__"):
                        version = line.split("=")[1].strip().strip('"')
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    lines = [f'    "{b64[i:i + 100]}"' for i in range(0, len(b64), 100)]
    OUT.write_text(TEMPLATE.format(version=version or "", payload="\n".join(lines)), encoding="utf-8")
    print(f"{OUT}  ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
