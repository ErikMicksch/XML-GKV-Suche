"""Start der Oberfläche (Qt Quick/QML): Bereiche anlegen, QML laden, Fenstergröße merken."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QFont
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from .core import Core
from .detail import Detail
from .dialogs import Compare, Palette, Picker
from .icons import IconProvider
from .lists import Lists
from .maint import Maint
from .pages import Activity, Dashboard, Versions
from .products import Products
from .theme import Theme
from .tree import Tree


def qml_dir():
    """Ordner mit Main.qml. In der Einzeldatei hmv_viewer_app.py liegen die QML-Dateien im eingebetteten Archiv
    und werden je Version einmal nach %LOCALAPPDATA%\\HMV-Viewer\\qml_<version> entpackt (QML braucht echte Dateien)."""
    if "__file__" in globals():
        here = Path(__file__).resolve().parent / "qml"
        if (here / "Main.qml").exists():
            return here
    import importlib.util
    from PySide6.QtCore import QStandardPaths
    from .. import __version__
    zf = importlib.util.find_spec(__name__).loader.zf
    target = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericDataLocation)) \
        / "HMV-Viewer" / f"qml_{__version__}"
    prefix = "hmv_viewer/ui/qml/"
    for name in zf.namelist():
        if name.startswith(prefix) and not name.endswith("/"):
            out = target / name[len(prefix):]
            if not out.exists() or out.read_bytes() != zf.read(name):
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(zf.read(name))
    return target


def setup_app():
    QQuickStyle.setStyle("Basic")   # vollständig eigenes Aussehen (AOK), unabhängig vom Windows-Design
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("HMV-Viewer")
    app.setFont(QFont("Segoe UI", 10))
    if hasattr(app.styleHints(), "setColorScheme"):   # Windows-Dunkelmodus nicht in Dateidialoge o. Ä. durchreichen
        from PySide6.QtCore import Qt
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    return app


def build(db_path, settings=None, fav_dir=None, user=None, auto_backup=True, start=True):
    core = Core(db_path, settings, fav_dir, user)
    core.theme = Theme(core.settings)
    core.lists_ctl = Lists(core)
    core.tree = Tree(core)
    core.products = Products(core)
    core.detail = Detail(core)
    core.dash = Dashboard(core)
    core.versions = Versions(core)
    core.activity = Activity(core)
    core.maint = Maint(core)
    core.compare = Compare(core)
    core.picker = Picker(core)
    core.quick = Palette(core)

    def restyle():   # Farben der Zeilen, Diagramme und Details kommen aus Python
        if core.store is None or core.names is None:
            return
        core.products.refresh(keep=core.detail.nummer)
        core.versions.load()
        core.activity.refresh()
        core.dash.refresh()

    core.theme.changed.connect(restyle)
    engine = QQmlApplicationEngine()
    engine.addImageProvider("icon", IconProvider())
    ctx = engine.rootContext()
    for name in ("core", "theme", "products", "tree", "detail", "dash", "versions", "activity", "maint", "compare",
                 "picker", "quick"):
        obj = core if name == "core" else getattr(core, name, None)
        ctx.setContextProperty(name, obj)
    ctx.setContextProperty("lists", core.lists_ctl)
    engine.load(QUrl.fromLocalFile(str(qml_dir() / "Main.qml")))
    if not engine.rootObjects():
        raise RuntimeError("Die Oberfläche (QML) konnte nicht geladen werden.")
    win = engine.rootObjects()[0]
    geo = str(core.settings.value("qml_fenster") or "")
    try:
        x, y, w, h, maxi = (int(v) for v in geo.split(","))
        win.setProperty("x", x)
        win.setProperty("y", y)
        win.setProperty("width", w)
        win.setProperty("height", h)
        if maxi:
            win.showMaximized()
    except ValueError:
        pass

    def save_geometry():
        maxi = int(win.property("visibility") == 4)   # QWindow.Maximized
        core.settings.setValue("qml_fenster", ",".join(str(int(win.property(k))) for k in ("x", "y", "width", "height"))
                               + f",{maxi}")
        core.close()

    QApplication.instance().aboutToQuit.connect(save_geometry)
    if start:
        core.start()
        if auto_backup:
            QTimer.singleShot(4000, core.maint.auto_backup)
    return core, engine


def run_qml(db_path, fav_dir=None):
    app = setup_app()
    _core, _engine = build(db_path, fav_dir=fav_dir)
    return app.exec()
