"""Tests der Oberfläche (Qt Quick/QML, ohne sichtbares Fenster):  python -m unittest tests.test_qml

1. Lesbarkeit: Kontrast aller Farbwelten (WCAG: Text ≥ 4,5 : 1, Fokusrahmen ≥ 3 : 1).
2. Ablauf: Import, Suche, Auswahl, Favorit, Liste, Kategorie, Notiz, Kommentar, Vergleich, Schnellzugriff,
   Nummernliste, Versionen, Designwechsel, schmales Fenster – jede QML-Warnung lässt den Test scheitern.
3. Bildvergleich: Seiten werden gerendert und mit den Referenzbildern in tests/baseline verglichen
   (fehlt ein Referenzbild, wird es angelegt; neu anlegen = Ordner tests/baseline_qml löschen).
"""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from PySide6.QtCore import QSettings, qInstallMessageHandler  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402

from hmv_viewer.ui.theme import THEMES, contrast  # noqa: E402

MESSAGES = []
qInstallMessageHandler(lambda mode, ctx, msg: MESSAGES.append(msg))
BASELINE = HERE / "baseline_qml"


class Contrast(unittest.TestCase):
    def test_themes_readable(self):
        pairs = [("text", "bg", 4.5), ("text", "surface", 4.5), ("text", "alt", 4.5), ("text", "select", 4.5),
                 ("muted", "surface", 4.5), ("muted", "bg", 4.5), ("green", "surface", 4.5), ("green", "mint", 4.5),
                 ("onAccent", "green", 4.5), ("goldText", "gold", 4.5), ("onDanger", "danger", 4.5),
                 ("headerFg", "headerB", 4.5), ("focus", "bg", 3.0), ("focus", "surface", 3.0)]
        for name, t in THEMES.items():
            for fg, bg, minimum in pairs:
                with self.subTest(theme=name, pair=f"{fg}/{bg}"):
                    self.assertGreaterEqual(contrast(t[fg], t[bg]), minimum)
            for tag in ("tagNeu", "tagGeaendert", "tagEntfernt", "tagReaktiviert", "tagUmgruppiert"):
                with self.subTest(theme=name, pair=f"text/{tag}"):
                    self.assertGreaterEqual(contrast(t["text"], t[tag]), 4.5)


class Flow(unittest.TestCase):
    def setUp(self):
        MESSAGES.clear()

    def wait(self, app, seconds=0.5):
        t0 = time.time()
        while time.time() - t0 < seconds:
            app.processEvents()
            time.sleep(0.02)

    def compare_image(self, win, name):
        img = win.grabWindow()
        BASELINE.mkdir(exist_ok=True)
        ref_path = BASELINE / f"{name}.png"
        if not ref_path.exists():
            img.save(str(ref_path))
            return
        ref = QImage(str(ref_path)).convertToFormat(img.format())
        self.assertEqual((ref.width(), ref.height()), (img.width(), img.height()), name)
        step, diff, total = 3, 0, 0   # jeder 3. Bildpunkt reicht für Layout-Fehler
        for y in range(0, img.height(), step):
            for x in range(0, img.width(), step):
                a, b = img.pixelColor(x, y), ref.pixelColor(x, y)
                total += 1
                diff += max(abs(a.red() - b.red()), abs(a.green() - b.green()), abs(a.blue() - b.blue())) > 40
        img.save(str(BASELINE / f"{name}.neu.png"))
        self.assertLess(diff / total, 0.03, f"{name}: {diff / total:.1%} der Bildpunkte anders – siehe {name}.neu.png")
        (BASELINE / f"{name}.neu.png").unlink()

    def test_flow(self):
        from tests.make_sample import write_sample
        from hmv_viewer.ui.app import build, setup_app

        app = setup_app()
        tmp = tempfile.mkdtemp()
        settings = QSettings(os.path.join(tmp, "s.ini"), QSettings.Format.IniFormat)
        settings.setValue("zuletzt_geoeffnet", "2026-01-01T00:00:00")
        dialogs = []

        def answer(spec):
            dialogs.append(spec["title"])
            if spec["title"] == "Erster Start":   # kein Dateidialog im Test
                return "no", ""
            if spec["hasInput"]:
                return "ok", "Testliste"
            return ("yes" if any(b["id"] == "yes" for b in spec["buttons"]) else spec["buttons"][0]["id"]), ""

        core, engine = build(os.path.join(tmp, "t.db"), settings=settings, fav_dir=os.path.join(tmp, "f"), user="Meier",
                             auto_backup=False, start=False)
        core.auto_answer = answer
        core.start()
        win = engine.rootObjects()[0]
        win.setProperty("width", 1600)
        win.setProperty("height", 940)
        self.wait(app)
        self.assertIn("Erster Start", dialogs)

        core.maint.run_import(write_sample(os.path.join(tmp, "20260101_HMV.xml"), variant=1), False)
        t0 = time.time()
        while core.maint.busy and time.time() - t0 < 30:
            self.wait(app, 0.1)
        self.wait(app)
        prods = core.products
        self.assertEqual(prods.total, 4)

        # Suche, Auswahl, Details
        prods.set("text", "Pumpe")
        self.assertEqual(prods.total, 3)
        prods.set("text", "")
        prods.click(0, False, False)
        nr = prods.current_nummer()
        self.assertEqual(core.detail.nummer, nr)
        self.assertTrue(core.detail.data["info"])

        # Favorit, Liste (mit Rückgängig), Kategorie, Notiz, Kommentar
        core.lists_ctl.toggle_fav(nr)
        self.assertIn(nr, core.store.favs)
        core.lists_ctl.newList(False)
        self.assertEqual([v["name"] for v in core.store.plists.values()], ["Testliste"])
        lid = next(iter(core.store.plists))
        core.lists_ctl.add(("pliste", lid), [nr])
        self.assertIn(nr, core.store.plists[lid]["items"])
        core.undo()
        self.assertNotIn(nr, core.store.plists[lid]["items"])
        prods.set_mark([nr], "1")
        self.assertEqual(core.store.marks.get(nr), "1")
        core.tree.select("all")   # neue Liste wurde ausgewählt -> zurück zu allen Produkten
        prods.click([r["nummer"] for r in prods.loaded].index(nr), False, False)
        core.detail.setNote("Hinweis bis 2027")
        core.detail.saveNote()
        self.assertEqual(core.store.notes.get(nr), "Hinweis bis 2027")
        self.assertTrue(core.detail.sendComment("Testkommentar"))
        self.assertEqual(core.detail.data["nComments"], 1)

        core.goto(2)
        self.wait(app)
        self.compare_image(win, "start_1600")
        # Design und schmales Fenster
        for name in THEMES:
            core.theme.setTheme(name)
        core.theme.setTheme("AOK Modern")
        core.goto(0)
        prods.click(0, False, False)
        self.wait(app)
        self.compare_image(win, "produkte_1600")
        win.setProperty("width", 1150)
        self.wait(app)
        self.assertTrue(win.property("narrow"))
        self.compare_image(win, "produkte_1150")

        # Vergleich, Schnellzugriff, Nummernliste, Spalten, Kopieren
        core.compare.open([r["nummer"] for r in prods.loaded[:2]])
        self.assertTrue(any(r["differs"] for r in core.compare.rows))
        self.assertTrue(core.quick.items("Pumpe"))
        self.assertEqual(prods.checkNumbers(nr)["found"], [nr])
        prods.toggleColumn("hersteller", False)
        self.assertFalse(next(c for c in prods.columns if c["key"] == "hersteller")["visible"])
        prods.resetColumns()
        prods.copy("table")

        # Versionen, Änderungen anderer, Startseite, Hilfe, Info
        core.goto(1)
        self.assertEqual(core.versions.versions.count, 1)
        core.goto(3)
        core.goto(2)
        self.assertIn("Meier", core.dash.data["greeting"])
        core.maint.help()
        core.maint.info()

        self.assertEqual([m for m in MESSAGES if "qml" in m.lower() or "warning" in m.lower()], [])


class ChoosePaths(unittest.TestCase):
    """Einstellungen → Datenbank / Sicherungsordner wählen schreibt die Pfad-Datei (aktuelle DB kopieren)."""

    def test_choose_database_and_backups(self):
        import json
        from unittest import mock
        from PySide6.QtWidgets import QFileDialog
        from tests.make_sample import write_sample
        from hmv_viewer import db, importer
        from hmv_viewer.config import default_db_path
        from hmv_viewer.ui.app import build, setup_app

        tmp = Path(tempfile.mkdtemp())
        paths = tmp / "hmv_pfade.json"
        src = tmp / "alt" / "hmv.db"
        src.parent.mkdir()
        importer.import_file(db.connect(str(src)), write_sample(str(tmp / "20260101_HMV.xml")))
        new_db, backups = tmp / "lokal" / "hmv.db", tmp / "backups"
        setup_app()
        with mock.patch.dict(os.environ, {"HMV_PFADE": str(paths)}),                 mock.patch.object(QFileDialog, "getSaveFileName", lambda *a, **k: (str(new_db), "")),                 mock.patch.object(QFileDialog, "getExistingDirectory", lambda *a, **k: str(backups)):
            env_db = os.environ.pop("HMV_DB", None)
            core, _engine = build(str(src), settings=QSettings(str(tmp / "s.ini"), QSettings.Format.IniFormat),
                                  fav_dir=str(tmp), user="T", auto_backup=False)
            core.auto_answer = lambda spec: ("copy" if spec["title"] == "Neue Datenbank" else "later", "")
            core.maint.chooseDatabase()
            self.assertTrue(new_db.exists())                      # aktuelle Datenbank dorthin kopiert
            core.maint.chooseBackupDir()
            self.assertEqual(json.loads(paths.read_text(encoding="utf-8")),
                             {"datenbank": str(new_db), "sicherungen": str(backups)})
            self.assertEqual(default_db_path(), new_db)           # gilt beim nächsten Start
            self.assertEqual(core.maint.backupPath, str(backups))  # Sicherungsordner gilt sofort
            if env_db:
                os.environ["HMV_DB"] = env_db


if __name__ == "__main__":
    unittest.main()
