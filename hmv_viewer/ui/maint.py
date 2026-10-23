"""Import, Excel-Export, Sicherung/Wiederherstellung, Tagessicherung, Einstellungen, Kategorien, Hilfe, Info, Neuigkeiten."""
from __future__ import annotations

import datetime as dt
import getpass
import html
import os
import sqlite3
import threading
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QFileDialog

from hmv_viewer import __version__, db, exporter, importer, queries
from hmv_viewer.gui import DEFAULT_MARK_COLOR, HELP, SHORTCUTS, Worker, _dots, _when, _who
from hmv_viewer.model import format_nummer
from hmv_viewer.parser import SourceError
from hmv_viewer.queries import ProductFilter

# Farbfelder statt Farbrad – leicht zu treffen, gut unterscheidbar
SWATCHES = ("#2E9E5B", "#E8A317", "#D64541", "#1E88E5", "#8E44AD", "#00897B", "#F06292", "#6D4C41", "#546E7A",
            "#C0CA33", "#FF7043", "#3949AB")
MARK_COLORS = ("#FFEB3B", "#FFD54F", "#A5D6A7", "#80DEEA", "#F48FB1", "#CE93D8", "#FFAB91", "#B0BEC5")


class Maint(QObject):
    changed = Signal()
    exportRequested = Signal("QVariantMap")
    categoriesRequested = Signal()
    settingsRequested = Signal()
    pasteRequested = Signal(str)
    columnsRequested = Signal()
    paletteRequested = Signal()

    def __init__(self, core):
        super().__init__()
        self.core = core
        self._busy, self._busy_title, self._busy_text, self._value, self._max = False, "", "", 0, 0
        self._worker = self._backup_worker = None

    busy = Property(bool, lambda self: self._busy, notify=changed)
    busyTitle = Property(str, lambda self: self._busy_title, notify=changed)
    busyText = Property(str, lambda self: self._busy_text, notify=changed)
    busyValue = Property(int, lambda self: self._value, notify=changed)
    busyMax = Property(int, lambda self: self._max, notify=changed)
    swatches = Property("QVariantList", lambda self: list(SWATCHES), constant=True)
    markColors = Property("QVariantList", lambda self: list(MARK_COLORS), constant=True)
    version = Property(str, lambda self: __version__, constant=True)

    @Property("QVariantList", notify=changed)
    def categories(self):
        store = self.core.store
        if store is None:
            return []
        return [{"cid": cid, "name": c["name"], "color": c["farbe"], "n": sum(v == cid for v in store.marks.values())}
                for cid, c in store.categories.items()]

    # ------------------------------------------------------------------ Hintergrundarbeit mit Fortschritt
    def run_background(self, title, job, on_done, on_error):
        self._busy, self._busy_title, self._busy_text, self._value, self._max = True, title, "Starte …", 0, 0
        self.changed.emit()
        w = self._worker = Worker()

        def progress(stage, current, total):
            self._max, self._value = total or 0, current if total else 0
            self._busy_text = f"{stage}  {_dots(current)}/{_dots(total)}" if total else stage
            self.changed.emit()

        def finish(fn, arg):
            self._busy = False
            self.changed.emit()
            fn(arg)

        w.progress.connect(progress)
        w.done.connect(lambda res: finish(on_done, res))
        w.failed.connect(lambda exc: finish(on_error, exc))
        db_path = self.core.db_path

        def run():
            try:
                conn = db.connect(db_path)
                try:
                    res = job(conn, lambda s, c, t: w.progress.emit(s, c, t))
                finally:
                    conn.close()
                w.done.emit(res)
            except BaseException as exc:  # noqa: BLE001 - an die Oberfläche weiterreichen
                w.failed.emit(exc)

        threading.Thread(target=run, daemon=True).start()

    # ------------------------------------------------------------------ Import
    def offer_first_import(self):
        self.core.ask("Erster Start", "Es ist noch keine HMV-XML importiert.<br><br>Jetzt eine XML- oder ZIP-Datei "
                      "auswählen?", [("no", "Später"), ("yes", "Datei auswählen …", True)],
                      lambda b, _t: b == "yes" and self.start_import(), icon="import")

    def start_import(self):
        if self.core.read_only:
            self.core.info("Nur lesen", "Sie haben keine Schreibrechte auf die gemeinsame Datenbank – Importieren ist "
                           "daher nicht möglich.", icon="alert")
            return
        path, _ = QFileDialog.getOpenFileName(None, "HMV-XML oder ZIP auswählen", "",
                                              "HMV XML / ZIP (*.xml *.zip);;Alle Dateien (*.*)")
        if path:
            self.run_import(path, False)

    @Slot()
    def startImport(self):
        self.start_import()

    def run_import(self, path, force):
        self.run_background("Import läuft",
                            lambda conn, progress: importer.import_file(conn, path, force=force, progress=progress),
                            self._import_done, lambda exc: self._import_failed(exc, path))

    def _import_done(self, res):
        core, prods = self.core, self.core.products
        core.reload_all()
        if res.first_import:
            core.info("Import abgeschlossen", f"Erstimport abgeschlossen (Version {res.import_id}).<br><br>"
                      f"{_dots(res.n_total)} Produkte eingelesen.<br>Dies ist die Ausgangsbasis – ab dem nächsten Import "
                      "werden Änderungen markiert.", icon="check")
            return
        text = (f"Version {res.import_id} importiert – {_dots(res.n_total)} Produkte in der Datei.<br><br>"
                f"Neu: <b>{res.n_new}</b><br>Geändert: <b>{res.n_changed}</b><br>Entfernt: <b>{res.n_removed}</b><br>"
                f"Wieder aufgenommen: <b>{res.n_reactivated}</b><br>Umgruppiert (neue Nummer): <b>{res.n_regrouped}</b><br>"
                f"Unverändert: {_dots(res.n_unchanged)}<br>"
                f"Änderungen an Gruppen/Orten/Untergruppen/Arten: {res.n_stamm_changes}")
        if res.warnings:
            text += f"<br><br>{len(res.warnings)} Warnung(en), z. B.: {html.escape(res.warnings[0])}"
        prods.st.update(version=res.import_id, status="alle")
        n_fav = queries.count_products(core.conn, ProductFilter(status="alle", favoriten=True, import_id=res.import_id))
        if n_fav:   # betroffene eigene Produkte sofort zeigen
            text += f"<br><br>★ <b>{n_fav} Ihrer Favoriten</b> sind betroffen – sie werden jetzt angezeigt."
            core.goto(0)
            core.tree.select("fav")
        else:
            prods.refresh()
        core.info("Import abgeschlossen", text, icon="check")

    def _import_failed(self, exc, path):
        core = self.core
        if isinstance(exc, importer.DuplicateImport):
            core.ask("Bereits importiert", f"{html.escape(str(exc))}<br><br>Trotzdem erneut importieren?<br>"
                     "(Es entsteht eine neue Version.)", [("no", "Nein"), ("yes", "Trotzdem importieren", True)],
                     lambda b, _t: b == "yes" and self.run_import(path, True), icon="alert")
        elif isinstance(exc, importer.SuspiciousImport):
            core.ask("Plausibilitätswarnung", f"{html.escape(str(exc))}<br><br>Trotzdem importieren?<br>"
                     "(Fehlende Produkte würden als „entfernt“ markiert.)",
                     [("no", "Nein"), ("yes", "Trotzdem importieren", True, True)],
                     lambda b, _t: b == "yes" and self.run_import(path, True), icon="alert", danger=True)
        elif isinstance(exc, ET.ParseError):
            core.info("Import fehlgeschlagen", f"Die Datei ist keine gültige XML:<br>{html.escape(str(exc))}", icon="alert")
        elif isinstance(exc, sqlite3.OperationalError) and "locked" in str(exc):
            core.info("Datenbank gerade belegt", "Ein anderer Benutzer ändert gerade die gemeinsame Datenbank (z. B. ein "
                      "Import).<br>Bitte in ein paar Minuten erneut versuchen.", icon="alert")
        elif isinstance(exc, (SourceError, importer.EmptyImport)):
            core.info("Import fehlgeschlagen", html.escape(str(exc)), icon="alert")
        else:
            core.info("Import fehlgeschlagen", html.escape(f"{type(exc).__name__}: {exc}"), icon="alert")

    # ------------------------------------------------------------------ Excel-Export
    @Slot()
    def startExport(self):
        core = self.core
        if not queries.list_versions(core.conn):
            core.info("Export", "Es sind noch keine Daten vorhanden – bitte zuerst eine XML importieren.")
            return
        core.detail.save_note()
        n_favs = queries.count_products(core.conn, ProductFilter(status="alle", favoriten=True))
        self.exportRequested.emit({"filtered": _dots(core.products.total), "favs": _dots(n_favs)})

    @Slot(str, bool, bool, bool, bool)
    def doExport(self, scope, personal, history, initial, versions):
        core, lists = self.core, self.core.lists_ctl
        stamp = dt.date.today().strftime("%Y%m%d")
        name = "HMV_Favoriten" if scope == "favoriten" else "HMV_Export"
        c = lists.current_container()
        if scope == "filter" and c not in (None, ("fav", None)):
            name = "HMV_Liste_" + "".join(ch if ch.isalnum() else "_" for ch in lists.name(c))
        path, _ = QFileDialog.getSaveFileName(None, "Excel-Datei speichern", f"{name}_{stamp}.xlsx",
                                              "Excel-Arbeitsmappe (*.xlsx)")
        if not path:
            return
        f = {"filter": replace(core.products.filter), "favoriten": ProductFilter(status="alle", favoriten=True)}.get(
            scope) or ProductFilter(status=scope)
        store = core.store

        def job(conn, progress):
            store.attach(conn)   # Favoriten-Filter braucht die TEMP-Tabelle auch in dieser Verbindung
            return exporter.export_excel(conn, path, f, include_history=history, include_versions=versions,
                                         include_initial_in_history=initial, progress=progress,
                                         favorites=store if personal else None)

        def done(res):
            msg = f"{_dots(res['products'])} Produkte exportiert"
            if history:
                msg += f"<br>{_dots(res['history_rows'])} Zeilen in der Änderungshistorie"
            core.ask("Export abgeschlossen", f"{msg}<br><br>{html.escape(path)}",
                     [("close", "Schließen"), ("open", "Datei öffnen", True)],
                     lambda b, _t: b == "open" and QDesktopServices.openUrl(QUrl.fromLocalFile(path)), icon="check")

        def failed(exc):
            if isinstance(exc, PermissionError):
                core.info("Export fehlgeschlagen", "Die Datei konnte nicht geschrieben werden (ist sie in Excel geöffnet?):"
                          f"<br>{html.escape(path)}", icon="alert")
            else:
                core.info("Export fehlgeschlagen", html.escape(f"{type(exc).__name__}: {exc}"), icon="alert")

        self.run_background("Excel-Export läuft", job, done, failed)

    # ------------------------------------------------------------------ Sicherung und Notfall-Wiederherstellung
    @Slot()
    def backup(self):
        core = self.core
        core.detail.save_note()
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M")
        path, _ = QFileDialog.getSaveFileName(None, "Datenbank sichern",
                                              str(Path(core.db_path).parent / f"HMV_Sicherung_{stamp}.db"),
                                              "SQLite-Datenbank (*.db)")
        if not path:
            return
        if Path(path).resolve() == Path(core.db_path).resolve():
            core.info("Sicherung", "Bitte eine andere Datei als die laufende Datenbank wählen.", icon="alert")
            return
        try:
            Path(path).unlink(missing_ok=True)   # Überschreiben wurde im Dialog bestätigt
            queries.backup_db(core.conn, path)
        except (sqlite3.Error, OSError) as exc:
            core.info("Sicherung fehlgeschlagen", html.escape(f"{type(exc).__name__}: {exc}"), icon="alert")
            return
        core.info("Sicherung erstellt", f"Die gemeinsame Datenbank wurde gesichert:<br><b>{html.escape(path)}</b><br><br>"
                  "Enthalten: Verzeichnis, Versionen, gemeinsame Listen, Kommentare, Benutzer.<br>"
                  "Nicht enthalten: Ihre persönlichen Favoriten, privaten Listen, Notizen und Kategorien "
                  f"(Datei {html.escape(str(core.store.path))}).", icon="check")

    @Slot()
    def restore(self):
        core = self.core
        core.ask("ACHTUNG – Datenbank wiederherstellen",
                 "<p style='font-size:large'><b>ACHTUNG: DER IMPORT EINER SICHERUNG ÜBERSCHREIBT ALLE INFORMATIONEN DER "
                 "GEMEINSAMEN DATENBANK.</b></p><p>Verzeichnis, Versionen und Historie, gemeinsame Listen, Kommentare und "
                 "Benutzer werden durch den Stand der Sicherung ersetzt – <b>für ALLE Benutzer</b>.</p>"
                 "<p><b>Dies soll NUR IM NOTFALL geschehen</b> (z. B. wenn die Datenbank beschädigt ist). Andere Benutzer "
                 "sollten das Programm vorher schließen.</p><p>Der aktuelle Stand wird vorher automatisch gesichert.</p>",
                 [("cancel", "Abbrechen", True), ("go", "Weiter – Sicherung auswählen …", False, True)],
                 lambda b, _t: b == "go" and self._restore_pick(), icon="alert", danger=True)

    def _restore_pick(self):
        core = self.core
        path, _ = QFileDialog.getOpenFileName(None, "Sicherung auswählen (NUR IM NOTFALL)", str(Path(core.db_path).parent),
                                              "SQLite-Datenbank (*.db);;Alle Dateien (*.*)")
        if not path:
            return
        if Path(path).resolve() == Path(core.db_path).resolve():
            core.info("Wiederherstellen", "Das ist die laufende Datenbank selbst.", icon="alert")
            return
        try:
            info = queries.check_backup(path)
        except ValueError as exc:
            core.info("Ungültige Sicherung", html.escape(str(exc)), icon="alert")
            return

        def confirmed(button, word):
            if button != "ok" or word.strip() != "ÜBERSCHREIBEN":
                core.info("Abgebrochen", "Es wurde nichts verändert.")
                return
            self._restore_now(path)

        core.ask("Letzte Bestätigung", f"Sicherung: <b>{html.escape(path)}</b><br>({info['versionen']} Versionen, "
                 f"{_dots(info['produkte'])} Produkte, {info['listen']} gemeinsame Listen)<br><br>"
                 "<b>ALLE INFORMATIONEN der gemeinsamen Datenbank werden überschrieben.</b>",
                 [("cancel", "Abbrechen", True), ("ok", "Endgültig überschreiben", False, True)], confirmed,
                 input={"label": "Zur Bestätigung bitte ÜBERSCHREIBEN eintippen:", "placeholder": "ÜBERSCHREIBEN"},
                 icon="alert", danger=True)

    def _restore_now(self, path):
        core = self.core
        core.detail.save_note()
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        safety = Path(core.db_path).parent / "sicherungen" / f"vor_wiederherstellung_{stamp}.db"
        try:
            safety.parent.mkdir(parents=True, exist_ok=True)
            queries.backup_db(core.conn, safety)   # ohne diese Sicherung wird nichts überschrieben
            queries.restore_db(core.conn, path)
            db.ensure_schema(core.conn)            # ältere Sicherungen auf den aktuellen Stand bringen
        except (sqlite3.Error, OSError, ValueError) as exc:
            core.info("Wiederherstellung fehlgeschlagen", html.escape(f"{type(exc).__name__}: {exc}") +
                      f"<br><br>Sicherung des vorherigen Stands: {html.escape(str(safety))}", icon="alert")
            return
        core.set_user(core.user)
        core.reload_all()
        core.info("Wiederhergestellt", "Die Datenbank wurde aus der Sicherung wiederhergestellt.<br><br>"
                  f"Der vorherige Stand wurde gesichert unter:<br>{html.escape(str(safety))}", icon="check")

    def auto_backup(self, sync=False):
        """Täglich eine Sicherung der gemeinsamen DB in data/sicherungen (die letzten 14 bleiben)."""
        core = self.core
        if core.read_only:
            return None
        folder = Path(core.db_path).parent / "sicherungen"
        target = folder / f"auto_{dt.date.today():%Y%m%d}.db"
        if target.exists():
            return None
        db_path = core.db_path

        def job():
            folder.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(f".tmp{os.getpid()}")
            src = sqlite3.connect(db_path, timeout=60)
            try:
                queries.backup_db(src, tmp)
            finally:
                src.close()
            if target.exists():          # ein Kollege war schneller
                tmp.unlink(missing_ok=True)
            else:
                os.replace(tmp, target)
            for old in sorted(folder.glob("auto_*.db"))[:-14]:
                old.unlink(missing_ok=True)
            return target

        if sync:
            return job()
        w = self._backup_worker = Worker()
        w.done.connect(lambda t: t and core.show_status(f"Automatische Tagessicherung erstellt: {t}", 6000))
        w.failed.connect(lambda exc: core.show_status(f"Automatische Sicherung nicht möglich: {exc}", 8000))

        def run():
            try:
                w.done.emit(job())
            except Exception as exc:  # noqa: BLE001 - nur Hinweis, nie ein Absturz
                w.failed.emit(exc)

        threading.Thread(target=run, daemon=True).start()
        return None

    # ------------------------------------------------------------------ Dialoge öffnen
    @Slot()
    def openSettings(self):
        self.settingsRequested.emit()

    @Slot()
    def openCategories(self):
        self.categoriesRequested.emit()

    @Slot()
    def openPaste(self):
        self.pasteRequested.emit(self.core.products.clipboardNumbers())

    @Slot()
    def openColumns(self):
        self.columnsRequested.emit()

    @Slot()
    def openPalette(self):
        self.paletteRequested.emit()

    # ------------------------------------------------------------------ Einstellungen
    @Slot(str)
    def setMarkColor(self, color):
        self.core.settings.setValue("markierfarbe", color)
        self.core.detail.reload()
        self.core.detail.changed.emit()
        self.core.toast("Markierungsfarbe gespeichert (nur auf diesem PC)")

    @Slot()
    def changeFavFolder(self):
        self.core.change_fav_folder()

    @Slot()
    def openFavFolder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.core.store.path.parent)))

    # ------------------------------------------------------------------ Farbkategorien
    def _after_categories(self):
        core = self.core
        core.store.attach(core.conn)
        core.products.reload_options()
        core.products.refresh(keep=core.detail.nummer)
        self.changed.emit()

    @Slot(str, str)
    def newCategory(self, name, color):
        if name.strip() and self.core.persist(self.core.store.add_category, name, color) is not None:
            self._after_categories()

    @Slot(str, str)
    def renameCategory(self, cid, name):
        if name.strip() and self.core.persist(self.core.store.update_category, cid, name) is not None:
            self._after_categories()

    @Slot(str, str)
    def recolorCategory(self, cid, color):
        if self.core.persist(self.core.store.update_category, cid, None, color) is not None:
            self._after_categories()

    @Slot(str)
    def deleteCategory(self, cid):
        store = self.core.store
        n = sum(v == cid for v in store.marks.values())

        def delete():
            if self.core.persist(store.delete_category, cid) is not None:
                self._after_categories()

        self.core.confirm("Farbkategorie löschen", f"Kategorie „{html.escape(store.categories[cid]['name'])}“ löschen?"
                          + (f"<br>{n} Produkt(e) verlieren damit ihre Markierung." if n else ""), delete,
                          yes="Löschen", danger=True)

    # ------------------------------------------------------------------ Hilfe, Tastenkürzel, Info, Neuigkeiten
    @Slot()
    def help(self):
        title, body = HELP.get(self.core.page, HELP[0])
        if self.core.page == 0:
            body += ("<p><b>Mehr Filter:</b> Über „Mehr Filter“ über der Liste finden Sie Status, Version, Änderungsart, "
                     "Hersteller und Farbkategorie. Die Zahl daneben zeigt, wie viele davon gerade wirken.</p>"
                     "<p><b>Schmaler Bildschirm?</b> Dann klappen die Produktgruppen weg – über den Knopf "
                     "„Produktgruppen“ links über der Liste holen Sie sie wieder hervor.</p>")
        self.core.ask(f"Hilfe – {title}", body, [("ok", "Verstanden", True)], wide=True, icon="help")

    @Slot()
    def shortcuts(self):
        rows = "".join(f"<tr><td style='padding:3px 16px 3px 0'><b>{k}</b></td><td>{v}</td></tr>" for k, v in SHORTCUTS)
        self.core.info("Tastenkürzel", f"<table>{rows}</table><p>Klick auf den Stern: Favorit an/aus · Doppelklick auf eine "
                       "Zeile: Notiz.<br>Gruppe, Art oder Hersteller in den Details anklicken: danach filtern.</p>",
                       wide=True, icon="keyboard")

    @Slot()
    def info(self):
        import platform
        import PySide6
        from PySide6.QtCore import qVersion
        core = self.core
        mode = core.conn.execute("PRAGMA journal_mode").fetchone()[0]
        rows = [("Version", f"HMV-Viewer {__version__} (QML-Test)"), ("Benutzer", f"{core.user} (Windows: {getpass.getuser()})"),
                ("Datenbank", core.db_path), ("Schreibrecht", "nein – nur lesen" if core.read_only else "ja"),
                ("Journal-Modus", mode), ("Favoriten-Datei", str(core.store.path)),
                ("Sicherungen", str(Path(core.db_path).parent / "sicherungen")),
                ("Python", f"{platform.python_version()} ({platform.system()} {platform.release()})"),
                ("Qt / PySide6", f"{qVersion()} / {PySide6.__version__}"), ("SQLite", sqlite3.sqlite_version)]
        log = Path(core.db_path).parent / f"fehler_{getpass.getuser()}.log"
        muted = core.theme.get("muted")
        table = "<table cellpadding='4'>" + "".join(
            f"<tr><td style='color:{muted}; padding-right:16px'>{k}</td><td>{html.escape(str(v))}</td></tr>"
            for k, v in rows) + "</table>"

        def answer(button, _t):
            if button != "copy":
                return
            text = "\n".join(f"{k}: {v}" for k, v in rows)
            if log.exists():
                text += "\n\nLetzter Fehler:\n" + "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-40:])
            QGuiApplication.clipboard().setText(text)
            core.toast("Fehlerbericht kopiert – z. B. in eine E-Mail an den Support einfügen")

        core.ask("Info & Support", table, [("close", "Schließen"), ("copy", "Fehlerbericht kopieren", True)], answer,
                 wide=True, icon="info")

    def whats_new(self, auto):
        core = self.core
        since = core.last_open or "0000"
        parts = []
        imports = queries.imports_since(core.conn, since)
        if imports:
            items = []
            for imp in imports:
                n_fav = queries.count_products(core.conn, ProductFilter(status="alle", favoriten=True, import_id=imp["id"]))
                items.append(f"V{imp['id']} vom {_when(imp['imported_at'])}: {imp['n_new']} neu, {imp['n_changed']} geändert, "
                             f"{imp['n_removed']} entfernt" + (f" – <a href='favoriten'>{n_fav} Ihrer Favoriten betroffen</a>"
                                                               if n_fav else ""))
            parts.append(("Neue Importe", items))
        changed = [r for lid, r in core.lists.items() if lid in core.store.abos and (r["changed_at"] or "") > since
                   and (r["changed_by"] or "") != (core.user or "")]
        if changed:
            parts.append(("Abonnierte Listen geändert", [
                f"<a href='liste:{r['id']}'>{html.escape(r['name'])}</a> – {html.escape(_who(r))}" for r in changed]))
        marks = queries.others_activity(core.conn, core.user, since, "kategorie", limit=25)
        if marks:
            parts.append(("Neue Farbmarkierungen anderer", [
                f"<a href='produkt:{a['nummer']}'>{format_nummer(a['nummer'])}</a> – <b>{html.escape(a['user'] or '?')}</b> "
                f"({_when(a['at'])}): {html.escape(a['detail'] or 'Markierung entfernt')}" for a in marks]))
        comments = queries.comments_since(core.conn, since, core.user)[:25]
        if comments:
            parts.append(("Neue Kommentare", [
                f"<a href='produkt:{c['nummer']}'>{format_nummer(c['nummer'])}</a> – <b>{html.escape(c['user'] or '?')}</b> "
                f"({_when(c['at'])}): {html.escape(c['text'][:160])}" for c in comments]))
        if not parts:
            if not auto:
                core.info("Was ist neu?", f"Seit {_when(since) or 'dem letzten Start'} gibt es nichts Neues.", icon="bell")
            return
        green = core.theme.get("green")
        text = "".join(f"<h3 style='color:{green}'>{title}</h3><ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"
                       for title, items in parts)

        def link(target):
            if target == "favoriten":
                core.products.showFavorites()
            elif target.startswith("produkt:"):
                core.products.open_product(target.split(":", 1)[1])
            else:
                core.detail.link(target)

        core.ask(f"Was ist neu seit {_when(since)}?", text, [("ok", "Schließen", True)], on_link=link, wide=True, icon="bell")

    @Slot()
    def whatsNew(self):
        self.whats_new(auto=False)
