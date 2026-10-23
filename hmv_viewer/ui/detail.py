"""Details rechts: Einordnung, Merkmale (anklickbar, Treffer markiert), Listen, Kommentare, Historie, Meine Notiz."""
from __future__ import annotations

import html

from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtGui import QGuiApplication

from hmv_viewer import merkmale, queries
from hmv_viewer.gui import DEFAULT_MARK_COLOR, _when, diff_parts, fmt_date, highlight_html
from hmv_viewer.model import CHANGE_LABELS, ENTFERNT, FIELD_LABELS, NEU, REAKTIVIERT, format_nummer

from .models import DictModel


def grid(rows, muted):
    return "<table cellpadding='4'>" + "".join(
        f"<tr><td style='color:{muted}; padding-right:16px'>{html.escape(k)}</td><td>{v}</td></tr>" for k, v in rows) + "</table>"


class Detail(QObject):
    changed = Signal()

    def __init__(self, core):
        super().__init__()
        self.core = core
        self.nummer = None
        self.keys = {}
        self.merk_links = []
        self.comments = DictModel(("cid", "user", "when", "text", "mine"), self)
        self.history = DictModel(("idx", "version", "date", "type", "fields", "bg", "selected"), self)
        self.hist_rows = []
        self._d = {}
        self._hist_html = ""
        self._note = ""

    commentModel = Property(QObject, lambda self: self.comments, constant=True)
    historyModel = Property(QObject, lambda self: self.history, constant=True)
    has = Property(bool, lambda self: self.nummer is not None, notify=changed)
    data = Property("QVariantMap", lambda self: dict(self._d), notify=changed)
    historyHtml = Property(str, lambda self: self._hist_html, notify=changed)
    note = Property(str, lambda self: self._note, notify=changed)
    markColor = Property(str, lambda self: self.core.settings.value("markierfarbe", DEFAULT_MARK_COLOR), notify=changed)

    # ------------------------------------------------------------------ Anzeigen
    def reload(self):
        self.show(self.nummer, keep_note=True)

    def show(self, nummer, keep_note=False):
        if not keep_note:
            self.save_note()
        core = self.core
        c = core.theme.colors
        self.nummer, self.keys = nummer, {}
        self._note = core.store.notes.get(nummer, "") if nummer else ""
        p = queries.get_product(core.conn, nummer) if nummer else None
        if p is None:
            self.nummer = None
            self._d = {"hint": "Produkt in der Liste anklicken, um Details, Kommentare, Historie und Ihre Notiz zu sehen."}
            self.comments.set_rows([])
            self.history.set_rows([])
            self._hist_html = ""
            self.changed.emit()
            return
        core.remember_recent(nummer)
        path = core.names.path(p)
        g, o, u, a = p["gruppe"], p["ort"], p["untergruppe"], p["art"]
        self.keys = {"gruppe": {"gruppe": g}, "ort": {"gruppe": g, "ort": o},
                     "untergruppe": {"gruppe": g, "ort": o, "untergruppe": u},
                     "art": {"gruppe": g, "ort": o, "untergruppe": u, "art": a}}
        esc = html.escape

        def link(target, text):
            return f"<a href='goto:{target}' style='color:{c['green']}'>{esc(text)}</a>"

        prods = core.products
        listed = next((r for r in prods.loaded if r["nummer"] == nummer), None)
        tag = prods.row_tag(listed) if listed is not None else None
        chips = [{"text": "aktiv" if p["active"] else "entfernt", "color": c["mint"] if p["active"] else c["tagEntfernt"],
                  "fg": c["text"]}]
        if tag:
            chips.append({"text": CHANGE_LABELS[tag], "color": core.theme.tag(tag), "fg": c["text"]})
        cat_id = core.store.marks.get(nummer)
        cat = core.store.categories.get(cat_id)
        if cat:
            chips.append({"text": cat["name"], "color": cat["farbe"], "fg": "#FFFFFF"})
        star = core.lists_ctl.star_for(nummer)
        is_fav = nummer in core.store.favs
        if star:
            chips.append({"text": "Favorit" if is_fav else "Favorit (Gruppe)", "color": c["mint"], "fg": c["text"]})
        info = grid([
            ("Hilfsmittelnummer", f"<b>{format_nummer(p['nummer'])}</b> <span style='color:{c['muted']}'>({p['nummer']})</span>"),
            ("Hersteller", link("hersteller", p["hersteller"]) if p["hersteller"] else ""),
            ("Produktgruppe", link("gruppe", path["gruppe"])), ("Anwendungsort", link("ort", path["ort"])),
            ("Untergruppe", link("untergruppe", path["untergruppe"])), ("Produktart", link("art", path["art"])),
            ("Aufnahme", fmt_date(p["aufnahmedatum"])), ("Änderung (HMV)", fmt_date(p["aenderungsdatum"]) or "–"),
            ("Status", esc(prods.status_text(p)))], c["muted"])
        in_lists = queries.lists_for_product(core.conn, nummer)
        mine = [(lid, v["name"]) for lid, v in core.store.plists.items()
                if nummer in v["items"] or any(len(k) < 10 and nummer.startswith(k) for k in v["items"])]
        rows = []
        if in_lists:
            rows.append(("Gemeinsam", ", ".join(link(f"liste:{r['id']}", r["name"]) for r in in_lists)))
        if mine:
            rows.append(("Meine", ", ".join(link(f"pliste:{lid}", name) for lid, name in mine)))
        comments = queries.comments_for(core.conn, nummer)
        self.comments.set_rows([{"cid": r["id"], "user": r["user"] or "?", "when": _when(r["at"]), "text": r["text"],
                                 "mine": (r["user"] or "") == (core.user or "")} for r in comments])
        self._d = {"title": p["bezeichnung"] or "(ohne Bezeichnung)", "nummer": format_nummer(nummer), "chips": chips,
                   "info": info, "merk": self._merkmale_html(p["merkmale"]), "lists": grid(rows, c["muted"]) if rows else "",
                   "hasMerkLinks": bool(self.merk_links), "isFav": is_fav, "category": cat_id or "",
                   "nComments": len(comments), "jumpToMerk": bool(prods.query_words),
                   "hint": "Grün unterstrichene Angaben anklicken = Liste danach filtern"}
        self._load_history()
        self.changed.emit()

    def _merkmale_html(self, text):
        """„Eigenschaft: Wert“-Zeilen anklickbar (grün, unterstrichen, ▸); Fließtext bleibt schwarz; Treffer markiert."""
        self.merk_links = []
        if not text:
            return "–"
        c = self.core.theme.colors
        terms = [t for t in self.core.products.query_words if len(t) > 1]
        color = self.core.settings.value("markierfarbe", DEFAULT_MARK_COLOR)
        lines = []
        for key, value in merkmale.parse_merkmale(text).items():
            line = value if key == merkmale.FREE_TEXT else f"{key}: {value}"
            body = highlight_html(line, terms, color)
            if key != merkmale.FREE_TEXT and len(value) <= merkmale.MAX_VALUE:
                self.merk_links.append((key, value))
                body = (f"<span style='color:{c['green']}'>▸&nbsp;</span><a href='goto:merkmal:{len(self.merk_links) - 1}'"
                        f" style='color:{c['green']}; text-decoration:underline'>{body}</a>")
            lines.append(body)
        return "<br>".join(lines)

    def _load_history(self):
        core = self.core
        vlabels = queries.version_labels(core.conn)
        self.hist_rows = queries.product_history(core.conn, self.nummer)
        self.history.set_rows([{"idx": i, "version": vlabels.get(h["import_id"], f"V{h['import_id']}"),
                                "date": fmt_date(h["imported_at"]), "type": CHANGE_LABELS.get(h["change_type"], h["change_type"]),
                                "fields": ", ".join(FIELD_LABELS.get(f, f) for f in h["changes"]),
                                "bg": core.theme.tag(h["change_type"]), "selected": i == 0}
                               for i, h in enumerate(self.hist_rows)])
        if self.hist_rows:
            self.selectHistory(0)
        else:
            self._hist_html = f"<p style='color:{core.theme.get('muted')}'>Keine Historie vorhanden.</p>"

    @Slot(int)
    def selectHistory(self, i):
        if not 0 <= i < len(self.hist_rows):
            return
        for k, r in enumerate(self.history.rows):
            if r["selected"] != (k == i):
                self.history.update_row(k, selected=k == i)
        c = self.core.theme.colors
        h = self.hist_rows[i]
        vlabels = queries.version_labels(self.core.conn)
        ctype = h["change_type"]
        out = [f"<h3 style='margin:4px 0'>{CHANGE_LABELS.get(ctype, ctype)} in {vlabels.get(h['import_id'], 'V' + str(h['import_id']))}</h3>",
               f"<p style='color:{c['muted']}'>Importiert am {(h['imported_at'] or '').replace('T', ' ')}"
               f" · Quelle: {html.escape(h['source_name'] or '')}</p>"]
        if not h["changes"]:
            out.append("<p>" + {
                NEU: "Das Produkt ist in dieser Version neu im Verzeichnis.",
                ENTFERNT: "Das Produkt war in dieser XML nicht mehr enthalten und wurde als „entfernt“ markiert.",
                REAKTIVIERT: "Das Produkt war zuvor entfernt und ist in dieser XML wieder enthalten (Felder unverändert).",
            }.get(ctype, "Keine Feldänderungen gespeichert.") + "</p>")
        styles = {"add": f"background-color:{c['diffAdd']}", "del": f"background-color:{c['diffDel']}",
                  "hunk": f"color:{c['muted']}", "muted": f"color:{c['muted']}"}
        for fld, (old, new) in h["changes"].items():
            out.append(f"<p style='color:{c['green']}'><b>{FIELD_LABELS.get(fld, fld)}</b></p><table width='100%' cellspacing='0'>")
            for text, tag in diff_parts(old, new):
                out.append(f"<tr><td style='{styles.get(tag, '')}; padding:2px 6px'>"
                           f"{html.escape(text).replace(chr(10), '<br>')}</td></tr>")
            out.append("</table>")
        self._hist_html = "".join(out)
        self.changed.emit()

    # ------------------------------------------------------------------ Links und Knöpfe
    @Slot(str)
    def link(self, href):
        target = href.split(":", 1)[1] if href.startswith("goto:") else href
        core, prods = self.core, self.core.products
        if target.startswith("merkmal:"):
            i = int(target.split(":", 1)[1])
            if i < len(self.merk_links):
                prods.search_line(*self.merk_links[i])
        elif target.startswith("produkt:"):
            prods.open_product(target.split(":", 1)[1])
        elif target.startswith(("liste:", "pliste:")):
            kind, lid = target.split(":", 1)
            core.goto(0)
            prods.st["text"] = ""
            core.tree.select_key({kind: int(lid) if kind == "liste" else lid})
        elif target == "hersteller":
            p = queries.get_product(core.conn, self.nummer) if self.nummer else None
            if p and p["hersteller"]:
                core.goto(0)
                prods.filter_hersteller(p["hersteller"])
        elif target in self.keys:
            core.goto(0)
            prods.st["text"] = ""
            core.tree.select_key(self.keys[target])

    @Slot()
    def toggleFav(self):
        if self.nummer:
            self.core.lists_ctl.toggle_fav(self.nummer)

    @Slot()
    def copyNumber(self):
        if self.nummer:
            QGuiApplication.clipboard().setText(format_nummer(self.nummer))
            self.core.toast(f"Kopiert: {format_nummer(self.nummer)}")

    @Slot(str)
    def setCategory(self, cid):
        if self.nummer:
            self.core.products.set_mark([self.nummer], cid or None)

    # ------------------------------------------------------------------ Notiz (automatisch gespeichert)
    @Slot(str)
    def setNote(self, text):
        self._note = text

    @Slot()
    def saveNote(self):
        core, k = self.core, self.nummer
        if k is None or core.store is None:
            return
        text = self._note.strip()
        if text == core.store.notes.get(k, ""):
            return
        if core.persist(core.store.set_note, k, text) is None:
            return
        core.products.update_rows({k})
        core.show_status(f"Notiz zu {format_nummer(k)} gespeichert", 3000)

    save_note = saveNote

    # ------------------------------------------------------------------ Kommentare (für alle sichtbar)
    @Slot(str, result=bool)
    def sendComment(self, text):
        if not self.nummer or not text.strip():
            return False
        if self.core.list_db(queries.add_comment, self.nummer, text, self.core.user) is None:
            return False
        self._after_comment()
        self.core.toast("Kommentar gespeichert – für alle sichtbar")
        return True

    @Slot(int)
    def deleteComment(self, cid):
        def delete():
            if self.core.list_db(queries.delete_comment, cid, self.core.user):
                self._after_comment()

        self.core.confirm("Kommentar löschen", "Eigenen Kommentar löschen?", delete, yes="Löschen", danger=True)

    def _after_comment(self):
        self.core.products.update_rows({self.nummer})
        self.reload()
