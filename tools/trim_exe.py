"""Entfernt aus dem PyInstaller-Programmordner alle Qt-Teile, die die Oberfläche nicht nutzt.

Aufruf (macht build_exe.bat automatisch):  python tools/trim_exe.py dist\\HMV-Viewer
PyInstaller übernimmt sonst alles, was Qt mitbringt (Web-Browser-Engine, 3D, PDF, Diagramme …):
aus ~410 MB werden so ~100 MB – schnellerer Start vom Netzlaufwerk, weniger Dateien für Virenscanner,
kürzere Pfade (Windows-Grenze 260 Zeichen).
"""
import fnmatch
import shutil
import sys
from pathlib import Path

# genutzte QML-Module: QtQuick (Controls/Basic, Layouts, Effects, Window …) und QtQml – der Rest fliegt raus
KEEP_QML = {"QtQml", "QtQuick"}
DROP_QTQUICK = {"Dialogs", "LocalStorage", "NativeStyle", "Particles", "Pdf", "Scene2D", "Scene3D", "Timeline",
                "VectorImage", "VirtualKeyboard", "tooling"}
KEEP_CONTROLS = {"Basic", "impl"}   # Stil „Basic“ (siehe hmv_viewer/ui/app.py), alle anderen Stile ungenutzt
DROP_FILES = ["Qt6WebEngine*", "Qt6WebChannel*", "Qt6WebSockets*", "Qt6WebView*", "Qt6Quick3D*", "Qt63D*", "Qt6Pdf*",
              "Qt6Charts*", "Qt6Graphs*", "Qt6DataVisualization*", "Qt6Multimedia*", "Qt6SpatialAudio*", "Qt6Location*",
              "Qt6Positioning*", "Qt6Sensors*", "Qt6TextToSpeech*", "Qt6RemoteObjects*", "Qt6Scxml*", "Qt6StateMachine*",
              "Qt6VirtualKeyboard*", "Qt6Test*", "Qt6Designer*", "Qt6Help*", "Qt6Bluetooth*", "Qt6Nfc*", "Qt6Serial*",
              "Qt6Sql*", "Qt6QuickParticles*", "Qt6QuickTimeline*", "Qt6QuickVectorImage*", "Qt6QuickDialogs2*",
              "Qt6QuickControls2Imagine*", "Qt6QuickControls2Material*", "Qt6QuickControls2Universal*",
              "Qt6QuickControls2FluentWinUI3*", "Qt6QuickControls2Fusion*", "Qt6QuickControls2Windows*",
              "Qt6Labs*", "Qt6HttpServer*", "Qt6NetworkAuth*", "Qt6Quick3D*", "Qt6ShaderTools*", "Qt6Concurrent*",
              "QtWebEngineProcess*", "qtwebengine*"]


def trim(dist: Path) -> int:
    qt = dist / "_internal" / "PySide6"
    if not qt.is_dir():
        raise SystemExit(f"Kein PySide6-Ordner gefunden: {qt}")
    before = sum(f.stat().st_size for f in dist.rglob("*") if f.is_file())
    qml = qt / "qml"
    for d in qml.iterdir():
        if d.is_dir() and d.name not in KEEP_QML:
            shutil.rmtree(d)
    for name in DROP_QTQUICK:
        shutil.rmtree(qml / "QtQuick" / name, ignore_errors=True)
    for d in (qml / "QtQuick" / "Controls").iterdir():
        if d.is_dir() and d.name not in KEEP_CONTROLS:
            shutil.rmtree(d)
    for f in list(qt.rglob("*")):
        if f.exists() and any(fnmatch.fnmatch(f.name, pat) for pat in DROP_FILES):
            shutil.rmtree(f) if f.is_dir() else f.unlink()
    after = sum(f.stat().st_size for f in dist.rglob("*") if f.is_file())
    print(f"{dist}: {before / 1e6:.0f} MB -> {after / 1e6:.0f} MB")
    return after


if __name__ == "__main__":
    trim(Path(sys.argv[1] if len(sys.argv) > 1 else "dist/HMV-Viewer"))
