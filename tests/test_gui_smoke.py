"""Rauchtest der Qt-Oberfläche ohne sichtbares Fenster (QT_QPA_PLATFORM=offscreen).

Prüft Aufbau, Filter, Favoriten-Datei, Notizen, Hersteller-Filter, Kopieren, Versionen und den Import-Ablauf.
Das ersetzt keinen Blick auf die echte Oberfläche.
"""
import json
import os
import sys
import tempfile
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    from PySide6.QtCore import QSettings, QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox
except ImportError:  # PySide6 fehlt -> Test überspringen
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 nicht installiert")
class GuiSmoke(unittest.TestCase):
    def test_flow(self):
        from hmv_viewer import gui, queries
        from hmv_viewer.queries import ProductFilter
        from hmv_viewer.favorites import FILE_NAME
        from tests.make_sample import write_sample

        calls = []
        QMessageBox.information = staticmethod(lambda *a, **k: calls.append(a[2]))
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.No)
        app = gui.setup_app()
        tmp = tempfile.mkdtemp()
        fav_dir = os.path.join(tmp, "favs")
        settings = QSettings(os.path.join(tmp, "s.ini"), QSettings.Format.IniFormat)
        win = gui.MainWindow(os.path.join(tmp, "t.db"), fav_dir=fav_dir, settings=settings, user="Meier")

        def wait_import(path):
            n = len(calls)
            win._run_import(path, False)
            t0 = time.time()
            while len(calls) == n and time.time() - t0 < 30:
                app.processEvents()
                time.sleep(0.02)

        self.assertIs(win.list_stack.currentWidget(), win.empty)   # leerer Start: Hinweis statt leerer Tabelle
        wait_import(write_sample(os.path.join(tmp, "20260101_HMV.xml"), variant=1))
        self.assertEqual(win.table.rowCount(), 4)

        # Favoriten + Notiz landen in der persönlichen Datei
        win.table.selectRow(0)
        fav = win.current_nummer
        win._toggle_selected_fav()
        win._toggle_fav(fav[:2])
        win.note_edit.setPlainText("Hinweis bis 2027")
        win._save_note()
        with open(os.path.join(fav_dir, FILE_NAME), encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(set(data["favoriten"]), {fav, fav[:2]})
        self.assertEqual(data["notizen"], {fav: "Hinweis bis 2027"})
        self.assertEqual(win.table.item(0, gui.COL["notiz"]).text(), "Hinweis bis 2027")

        # Import V2: betroffene Favoriten werden direkt angezeigt
        wait_import(write_sample(os.path.join(tmp, "20260201_HMV.xml"), variant=2))
        self.assertEqual(win.filter.import_id, 2)
        self.assertTrue(win.filter.favoriten)
        self.assertIn("Ihrer Favoriten", calls[-1])
        # Details auch bei gewähltem Versionsfilter (früher Absturz: shown_type fehlte)
        win.table.selectRow(0)
        self.assertTrue(win.sec_info.body.text())
        self.assertTrue(win.detail_chips.count())
        # Merkmal-Suche ist standardmäßig an und bleibt beim Zurücksetzen an
        self.assertTrue(win.chk_merk.isChecked())
        # Fundstellen in den Merkmalen werden markiert (Standard gelb), Farbe je Benutzer
        self.assertEqual(gui.highlight_html("Gewicht: 4,7 kg\nA<b>",["gewicht", "4,7", "<b"], "#FFEB3B"),
                         "<span style='background:#FFEB3B; color:#000000'>Gewicht</span>: "
                         "<span style='background:#FFEB3B; color:#000000'>4,7</span> kg<br>"
                         "A<span style='background:#FFEB3B; color:#000000'>&lt;b</span>&gt;")
        win.search.setText("gewicht")
        win.apply_filter()
        win.table.selectRow(0)
        self.assertIn("background:#FFEB3B", win.sec_merk.body.text())
        self.assertTrue(win.table.item(0, gui.COL["fund"]).text().startswith("Gewicht"))   # Fundstelle in der Liste
        # Merkmal-Zeile anklicken -> genaue Phrase im (einzigen) Suchfeld, Suche in Merkmalen
        self.assertEqual(win._merk_links[0][0], "Gewicht")
        win.chk_merk.setChecked(False)
        win._on_detail_link("merkmal:0")
        self.assertEqual(win.search.text(), '"Gewicht: 4,7 kg"')
        self.assertTrue(win.chk_merk.isChecked())
        self.assertEqual(len(win.row_nummer), 1)
        self.assertFalse(hasattr(win, "cb_prop"))                    # keine Eigenschaft/Wert-Auswahl mehr
        win.search.setText("gewicht")
        win.apply_filter()
        win.table.selectRow(0)
        settings.setValue("markierfarbe", "#00FF00")
        win._show_detail(win.current_nummer)
        self.assertIn("background:#00FF00", win.sec_merk.body.text())
        win.search.clear()
        # Suchbereiche: nur Bezeichnung -> Merkmal-Wort findet nichts
        win.chk_merk.setChecked(False)
        win.search.setText("gewicht")
        win.apply_filter()
        self.assertEqual(win.total, 0)
        win.chk_merk.setChecked(True)
        self.assertGreater(win.total, 0)
        win.search.clear()
        # „Nicht besetzt“ ausblenden (bleibt gemerkt)
        win.reset_filter()
        n_all = win.total
        win.chk_platzhalter.setChecked(True)
        self.assertEqual(win.total, n_all - 1)
        win.chk_platzhalter.setChecked(False)

        # Ganze Gruppe als Favorit: alle Produkte der Gruppe gehören dazu, Gruppe erscheint als Baum
        win.reset_filter()
        win.show_favorites()
        self.assertIn(fav, win.row_nummer)
        self.assertGreater(len(win.row_nummer), 1)
        entries = [it for it in win._walk(win.fav_item) if it.data(0, gui.ENTRY_ROLE)]
        self.assertEqual([tuple(it.data(0, gui.ENTRY_ROLE))[1] for it in entries], [fav[:2]])
        self.assertGreater(entries[0].childCount(), 0)                         # aufklappbarer Unterbaum
        other = next(nr for nr in win.row_nummer if nr != fav)
        self.assertEqual(win.table.item(win.row_nummer.index(other), gui.COL["fav"]).text(), "☆")
        win.table.selectRow(win.row_nummer.index(fav))
        win._copy("table")
        self.assertIn("Hinweis bis 2027", QApplication.clipboard().text())
        win._on_detail_link("hersteller")
        self.assertTrue(win.filter.hersteller)
        self.assertFalse(win.filter.favoriten)

        # Mehrfachauswahl -> Favoriten
        win.reset_filter()
        win.table.selectAll()
        win._toggle_selected_fav()
        self.assertEqual(sum(len(k) == 10 for k in win.store.favs), 4)

        # Gemeinsame Liste mit Unterliste: anlegen, Auswahl hinzufügen, anzeigen, Produkt entfernen
        c = win._new_container(("liste", None), select=False, name="Pumpen Liste")
        lid = c[1]
        win._container_add(c, win._selected_nummern())
        self.assertEqual(win.lists[lid]["n"], 4)
        sub = win._new_container(c, select=False, name="Unterliste A")
        self.assertEqual(win.lists[sub[1]]["parent_id"], lid)
        self.assertIs(win._item_for_key({"liste": sub[1]}).parent(), win._item_for_key({"liste": lid}))
        win._select_tree(win._item_for_key({"liste": lid}))
        self.assertEqual(win.filter.liste_id, lid)
        self.assertEqual(len(win.row_nummer), 4)
        win._remove_selected_from_current(win.row_nummer[:1])
        self.assertEqual(len(win.row_nummer), 3)
        win.table.selectRow(0)
        win._on_detail_link(f"liste:{lid}")
        win._rename_container(c, "Pumpen 2027")
        self.assertEqual(win.lists[lid]["name"], "Pumpen 2027")

        # Private Liste in privater Liste, ganze Gruppe als Eintrag
        group_k = fav[:2]
        f = ProductFilter(status="aktiv", **queries.key_from_prefix(group_k))
        n = queries.count_products(win.conn, f)
        pc = win._new_container(("fav", None), select=False, name="Privat")
        psub = win._new_container(pc, select=False, name="Privat Unter")
        win._container_add(psub, [group_k])
        item = win._item_for_key({"pliste": psub[1]})
        self.assertIs(item.parent(), win._item_for_key({"pliste": pc[1]}))
        self.assertTrue(any(item.child(i).data(0, gui.ENTRY_ROLE) for i in range(item.childCount())))
        win._select_tree(item)
        self.assertEqual(len(win.row_nummer), n)
        with open(os.path.join(fav_dir, FILE_NAME), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["listen"][psub[1]]["items"].keys(), {group_k})

        # Dieselbe Gruppe einzeln (fester Stand) in eine gemeinsame Liste – über den Dialog
        dlg = gui.AddToListDialog(win, "Gruppe", n, True)
        target = next(it for it in [dlg.tree.topLevelItem(1)] + list(win._walk(dlg.tree.topLevelItem(1)))
                      if tuple(it.data(0, gui.UD)) == c)
        dlg.tree.setCurrentItem(target)
        dlg.rb_single.setChecked(True)
        dlg._accept()
        self.assertEqual((dlg.target, dlg.whole_group), (c, False))
        win._container_add(dlg.target, win._nummern_for(f, n))
        self.assertEqual(win.lists[lid]["n"], n)

        # Farbkategorie setzen, filtern, Farbfeld in der Liste
        win.reset_filter()
        win.table.selectRow(0)
        first = win.row_nummer[0]
        cid = next(iter(win.store.categories))
        win._set_mark([first], cid)
        self.assertFalse(win.table.item(0, gui.COL["kat"]).icon().isNull())
        win.cb_kat.setCurrentIndex(win.cb_kat.findData(cid))
        win.apply_filter()
        self.assertEqual(win.row_nummer, [first])

        # Suche findet eigene Notiz
        win.reset_filter()
        win.search.setText("hinweis bis")
        win.apply_filter()
        self.assertEqual(win.row_nummer, [fav])

        # Kommentar für alle: in der DB mit Benutzer, von Suche und Notiz-Suchfeld gefunden
        self.assertEqual(win.store.user_name, "Meier")                       # Name steht in der Favoriten-Datei
        with open(os.path.join(fav_dir, FILE_NAME), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["benutzer"], "Meier")
        self.assertIsNone(win.user_btn.menu())                                # kein Wechsel über den Kopf
        win.table.selectRow(0)
        win._send_comment("Rückruf Hersteller 2027")
        row = queries.comments_for(win.conn, fav)[-1]
        self.assertEqual((row["text"], row["user"]), ("Rückruf Hersteller 2027", "Meier"))
        self.assertEqual(win.detail_tabs.tabText(1), "Kommentare (1)")
        win.reset_filter()
        win.scope_bez.setChecked(False)
        win.chk_merk.setChecked(False)                # nur „Notizen & Kommentare“
        win.search.setText("rückruf")
        win.apply_filter()
        self.assertEqual(win.row_nummer, [fav])
        self.assertIn("Rückruf Hersteller 2027", win.table.item(0, gui.COL["gnotiz"]).text())
        win.search.setText("hinweis bis")             # eigene Notiz
        win.apply_filter()
        self.assertEqual(win.row_nummer, [fav])
        win.scope_bez.setChecked(True)
        win.chk_merk.setChecked(True)
        win.reset_filter()
        self.assertTrue(win.chk_merk.isChecked())
        win.search.setText("rückruf")                 # große Suche findet Kommentare auch
        win.apply_filter()
        self.assertEqual(win.row_nummer, [fav])

        # Benutzer wechseln -> Listenänderung zeigt neuen Namen
        win._set_user("Schulz")
        win._container_add(c, [fav])
        win._container_remove(c, [fav])
        self.assertEqual(win.lists[lid]["changed_by"], "Schulz")
        self.assertEqual(queries.list_users(win.conn), ["Meier", "Schulz"])

        # Design umschalten baut alles neu auf
        for name in gui.THEME_NAMES:
            win.set_theme(name)
            self.assertEqual(settings.value("design"), name)
        self.assertEqual(gui.BG, gui.THEMES["Dunkel"]["BG"])
        win.set_theme("Classic")

        win.reset_filter()
        win.table.selectRow(0)
        win._reveal_level("art")
        self.assertIsNotNone(win.filter.art)
        win.hier_filter.setText("zzz-nichts")
        win._on_hier_filter()
        self.assertEqual(win.all_item.childCount(), 0)
        win.reset_filter()
        self.assertGreater(win.all_item.childCount(), 0)
        win._sort_by(gui.COL["bezeichnung"])
        win._sort_by(gui.COL["notiz"])   # nicht sortierbar -> keine Ausnahme
        win._load_versions()
        win._show_version_in_products()
        self.assertEqual(win.filter.import_id, 2)
        # ---- Verbesserungen v2.3
        from hmv_viewer import ui_extras
        # Zuletzt angesehen: Baum-Eintrag filtert auf die geöffneten Produkte
        win.reset_filter()
        win.table.selectRow(0)
        seen = win.current_nummer
        self.assertEqual(win.recent[0], seen)
        win._select_tree(win.recent_item)
        self.assertIn(seen, win.row_nummer)
        # Schnellzugriff findet Funktionen und Produkte
        titles = [t for _, t, _, _ in win._palette_items("pumpe")]
        self.assertTrue(any("Muster Pumpe" in t for t in titles))
        self.assertTrue(any(t == "Excel-Export" for _, t, _, _ in win._palette_items("export")))
        win._open_product(fav)
        self.assertEqual(win.current_nummer, fav)
        # Gespeicherte Suche
        win.reset_filter()
        win.search.setText("pumpe")
        win.apply_filter()
        win.store.save_search("Pumpen", win._search_state())
        win.reset_filter()
        win._apply_search_state(win.store.searches["Pumpen"])
        self.assertEqual(win.filter.text, "pumpe")
        # Nummernliste erkennen (mit und ohne Punkte, Dubletten, unbekannte)
        self.assertEqual(ui_extras.parse_numbers("x 01.24.01.0001, 0124010003 und 01.24.01.0001 / 9999999999"),
                         ["0124010001", "0124010003", "9999999999"])
        # Vergleich: Dialog lässt sich für 2 Produkte aufbauen
        win.reset_filter()
        dlg = ui_extras.CompareDialog(win, [dict(queries.get_product(win.conn, n), nummer_fmt=n, aufnahme="", status="")
                                            for n in win.row_nummer[:2]], win.names)
        dlg.close()
        # Rückgängig: Favorit setzen und wieder zurücknehmen
        target = next(n for n in win.row_nummer if n not in win.store.favs) if any(
            n not in win.store.favs for n in win.row_nummer) else None
        if target is None:
            target = win.row_nummer[0]
            win._toggle_fav(target, record=False)
        win._toggle_fav(target)
        self.assertIn(target, win.store.favs)
        win.table.setFocus()
        win._undo_last()
        self.assertNotIn(target, win.store.favs)
        # Kartenansicht und Spaltenwahl
        win.set_view_mode("karten")
        self.assertEqual(win.cards.count(), len(win.row_nummer))
        self.assertIs(win.list_stack.currentWidget(), win.cards)
        win.set_view_mode("tabelle")
        hdr = win.table.horizontalHeader()
        hdr.setSectionHidden(gui.COL["hersteller"], True)
        win._reset_columns()
        self.assertFalse(hdr.isSectionHidden(gui.COL["hersteller"]))
        # alle Spalten frei in der Breite ziehbar – auch „Bezeichnung“
        from PySide6.QtWidgets import QHeaderView
        self.assertTrue(all(hdr.sectionResizeMode(i) == QHeaderView.ResizeMode.Interactive
                            for i in range(len(gui.PRODUCT_COLUMNS))))
        win.table.setColumnWidth(gui.COL["bezeichnung"], 555)
        self.assertEqual(win.table.columnWidth(gui.COL["bezeichnung"]), 555)
        # Spalten-Dialog: Häkchen blendet sofort aus/ein, Pflichtspalten sind gesperrt
        dlg = win._columns_dialog()
        dlg.checks["fund"].setChecked(False)
        self.assertTrue(hdr.isSectionHidden(gui.COL["fund"]))
        self.assertFalse(dlg.checks["nummer"].isEnabled())
        dlg.checks["fund"].setChecked(True)
        self.assertFalse(hdr.isSectionHidden(gui.COL["fund"]))
        dlg.close()
        # Startseite, Ansicht, Tagessicherung, Info, Abo, Was ist neu
        win._goto_page_widget(2)
        self.assertIn(win.user, win.greeting.text())
        win.set_view(density="Kompakt", font_pt=11)
        self.assertEqual(gui.ROW_H, gui.DENSITY["Kompakt"])
        win.set_view(density="Groß", font_pt=12)
        # Standard „AOK Modern“: Klartext-Navigation und Hilfe (F1) zu jeder Seite
        win.set_theme(gui.DEFAULT_THEME)
        self.assertIn("qlineargradient", QApplication.instance().styleSheet())
        self.assertEqual([win.nav_group.button(i).text().split(" (")[0] for i, *_ in gui.NAV],
                         ["Startseite", "Produkte suchen", "Versionen", "Änderungen anderer"])
        for page in (0, 1, 2):   # Seite 3 erst unten (Öffnen setzt „gesehen“)
            win._goto_page_widget(page)
            QTimer.singleShot(50, lambda: QApplication.activeModalWidget().accept())
            win.show_help()
        win._goto_page_widget(2)
        backup = win._auto_backup(sync=True)
        self.assertTrue(backup.exists())
        self.assertIsNone(win._auto_backup(sync=True))         # nur einmal pro Tag
        win._toggle_abo(lid)
        self.assertIn(lid, win.store.abos)
        win._last_open = "2000-01-01T00:00:00"
        shown = []
        orig = gui.TextDialog.exec
        gui.TextDialog.exec = lambda self_: shown.append(self_.view.toPlainText()) or 0
        try:
            win._show_whats_new(auto=True)
            win._show_list_log(lid)
            win._show_info()
        finally:
            gui.TextDialog.exec = orig
        self.assertIn("Neue Importe", shown[0])
        self.assertIn("Neue Kommentare", shown[0])
        self.assertIn("hinzugefügt", shown[1])
        self.assertIn("Journal-Modus", shown[2])
        win._goto_page_widget(0)

        # Vergleichen mit …: Popup wählt ein zweites Produkt, Vergleich ist eine Tabelle mit Eigenschaften
        win.reset_filter()
        base, other = win.row_nummer[0], win.row_nummer[1]
        orig_picker, orig_cmp = gui.ProductPicker.exec, gui.CompareDialog.exec
        seen_pick, seen_cmp = [], []

        def fake_pick(dlg):
            seen_pick.append(dlg.list.count())
            dlg.list.item(0).setSelected(True)
            dlg._accept()
            return gui.QDialog.DialogCode.Accepted

        def fake_cmp(dlg):
            seen_cmp.append(dlg)
            return 0

        gui.ProductPicker.exec, gui.CompareDialog.exec = fake_pick, fake_cmp
        try:
            win._compare_with(base)
        finally:
            gui.ProductPicker.exec, gui.CompareDialog.exec = orig_picker, orig_cmp
        self.assertGreater(seen_pick[0], 0)                                  # gleiche Produktart vorgeschlagen
        cmp = seen_cmp[0]
        self.assertEqual(len(cmp.products), 2)
        self.assertEqual(cmp.products[0]["nummer"], base)
        self.assertEqual(cmp.table.horizontalHeaderItem(0).text(), "Eigenschaft")
        self.assertEqual(cmp.table.item(0, 0).text(), "Allgemein")
        all_rows = cmp.table.rowCount()
        cmp.only_diff.setChecked(True)
        self.assertLess(cmp.table.rowCount(), all_rows)
        cmp._copy()
        self.assertIn("Eigenschaft", QApplication.clipboard().text())
        # Merkmale: Name/Wert-Zeilen, Abschnitte und Fließtext mit Silbentrennung
        self.assertEqual(ui_extras.parse_merkmale("Gewicht: 4,7 kg\nFarbe: rot\nBauart-Nr.: DHI 1"),
                         {"Gewicht": "4,7 kg", "Farbe": "rot", "Bauart-Nr.": "DHI 1"})
        self.assertEqual(ui_extras.parse_merkmale("Beschreibung / Aufbau:\nKissen aus\nSchaum."),
                         {"Beschreibung / Aufbau": "Kissen aus Schaum."})
        self.assertEqual(ui_extras.parse_merkmale("Gestell, Handgriffe hö-\nhenverstellbar.\nkleine Ausführung"),
                         {"Beschreibung": "Gestell, Handgriffe höhenverstellbar. kleine Ausführung"})

        # Änderungen anderer: Kollege kommentiert und färbt ein -> erscheint im neuen Reiter mit Zähler
        queries.add_comment(win.conn, other, "Kollegen-Kommentar", "Kollege")
        queries.log_activity(win.conn, "Kollege", "kategorie", [other], "Kritisch", "#D64541")
        win._update_activity_badge()
        self.assertIn("(", win.nav_group.button(3).text())
        win._goto_page_widget(3)
        texts = [win.act_table.item(r, 5).text() for r in range(win.act_table.rowCount())]
        self.assertIn("Kollegen-Kommentar", texts)
        self.assertIn("eingefärbt: Kritisch", texts)
        self.assertEqual(win.nav_group.button(3).text(), "Änderungen anderer")   # gesehen -> Zähler weg
        QTimer.singleShot(50, lambda: QApplication.activeModalWidget().accept())
        win.show_help()
        win.act_kind.setCurrentIndex(win.act_kind.findData("kategorie"))
        win.refresh_activity()
        self.assertTrue(all(win.act_table.item(r, 2).text() == "Farbkategorie" for r in range(win.act_table.rowCount())))
        row = next(r for r in range(win.act_table.rowCount()) if win.act_table.item(r, 3).text())
        win._open_activity(row)
        self.assertEqual(win.stack.currentIndex(), 0)
        # eigene Farbmarkierung wird für die anderen protokolliert
        before = win.conn.execute("SELECT COUNT(*) FROM aktivitaet WHERE user=?", (win.user,)).fetchone()[0]
        win._set_mark([base], next(iter(win.store.categories)), record=False)
        after = win.conn.execute("SELECT COUNT(*) FROM aktivitaet WHERE user=?", (win.user,)).fetchone()[0]
        self.assertEqual(after, before + 1)

        win.close()

        # Neuer Start liest die Favoriten aus der Datei
        win2 = gui.MainWindow(os.path.join(tmp, "t.db"), fav_dir=fav_dir, settings=settings)
        self.assertIn(fav, win2.store.favs)
        self.assertEqual(win2.user, win.user)                               # Name kommt aus der Datei, keine Abfrage
        self.assertTrue(win2.chk_merk.isChecked())
        win2.close()

    def test_activity_only_own_entries(self):
        """Nur eigene Einträge vorhanden: Hinweis statt leerer Tabelle; Schalter zeigt sie; anderer Benutzer sieht sie."""
        from hmv_viewer import gui, queries
        from tests.make_sample import write_sample
        from hmv_viewer import db, importer

        gui.setup_app()
        tmp = tempfile.mkdtemp()
        dbp = os.path.join(tmp, "t.db")
        conn = db.connect(dbp)
        importer.import_file(conn, write_sample(os.path.join(tmp, "20260101_HMV.xml"), variant=1))
        conn.close()
        settings = QSettings(os.path.join(tmp, "s.ini"), QSettings.Format.IniFormat)
        win = gui.MainWindow(dbp, fav_dir=os.path.join(tmp, "f"), settings=settings, user="Erik", auto_backup=False)
        win.table.selectRow(0)
        win._send_comment("Hallo hier ist Erik")
        win._goto_page_widget(3)
        self.assertIs(win.act_stack.currentWidget(), win.act_empty)
        self.assertIn("stammen von Ihnen", win.act_empty.text())
        win.act_mine.setChecked(True)
        self.assertIs(win.act_stack.currentWidget(), win.act_table)
        self.assertEqual(win.act_table.item(0, 5).text(), "Hallo hier ist Erik")
        win.act_mine.setChecked(False)
        win._set_user("Test")
        win._goto_page_widget(3)
        self.assertEqual([win.act_table.item(r, 1).text() for r in range(win.act_table.rowCount())], ["Erik"])
        self.assertEqual(len(queries.list_users(win.conn)), 2)
        win.close()


if __name__ == "__main__":
    unittest.main()
