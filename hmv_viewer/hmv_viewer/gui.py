"""tkinter-GUI: Produkte einsehen, Versionshistorie, Import und Excel-Export."""
from __future__ import annotations

import datetime as dt
import difflib
import queue
import threading
import tkinter as tk
import xml.etree.ElementTree as ET
from dataclasses import replace
from tkinter import filedialog, messagebox, ttk

from . import __version__, db, exporter, importer, queries
from .model import CHANGE_LABELS, ENTITY_LABELS, FIELD_LABELS, GEAENDERT, NEU, ENTFERNT, REAKTIVIERT, format_nummer
from .parser import SourceError
from .queries import ProductFilter

PAGE_SIZE = 500
TAG_COLORS = {
    NEU: "#d9f2d0",
    GEAENDERT: "#fff2b3",
    ENTFERNT: "#f6c9c0",
    REAKTIVIERT: "#cfe3f7",
}
STATUS_CHOICES = {"Nur aktive": "aktiv", "Nur entfernte": "entfernt", "Alle": "alle"}
TYPE_CHOICES = {
    "Alle Änderungstypen": None,
    CHANGE_LABELS[NEU]: NEU,
    CHANGE_LABELS[GEAENDERT]: GEAENDERT,
    CHANGE_LABELS[ENTFERNT]: ENTFERNT,
    CHANGE_LABELS[REAKTIVIERT]: REAKTIVIERT,
}
ALL_VERSIONS = "Alle Versionen"

PRODUCT_COLUMNS = (
    # id, Überschrift, Breite, Sortier-Schlüssel
    ("nummer", "Hilfsmittelnummer", 120, "nummer"),
    ("bezeichnung", "Bezeichnung", 330, "bezeichnung"),
    ("hersteller", "Hersteller", 210, "hersteller"),
    ("art", "Produktart", 250, "art"),
    ("aufnahme", "Aufnahme", 85, "aufnahme"),
    ("aenderung", "Änderung (HMV)", 100, "aenderung"),
    ("version", "Version / Status", 150, "version"),
)


def fmt_date(iso):
    if not iso:
        return ""
    try:
        return dt.date.fromisoformat(iso[:10]).strftime("%d.%m.%Y")
    except ValueError:
        return iso


def _add_scrollbars(parent, widget, horizontal=False):
    vs = ttk.Scrollbar(parent, orient="vertical", command=widget.yview)
    widget.configure(yscrollcommand=vs.set)
    vs.pack(side="right", fill="y")
    if horizontal:
        hs = ttk.Scrollbar(parent, orient="horizontal", command=widget.xview)
        widget.configure(xscrollcommand=hs.set)
        hs.pack(side="bottom", fill="x")


class ProgressDialog(tk.Toplevel):
    def __init__(self, parent, title):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)
        self.label = ttk.Label(frame, text="Starte …", width=60)
        self.label.pack(anchor="w")
        self.bar = ttk.Progressbar(frame, mode="indeterminate", length=420)
        self.bar.pack(pady=(10, 0), fill="x")
        self.bar.start(12)
        self._indeterminate = True
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_reqwidth()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.grab_set()

    def set_progress(self, stage, current, total):
        self.label.configure(text=stage if not total else f"{stage}  {current:,}/{total:,}".replace(",", "."))
        if total:
            if self._indeterminate:
                self.bar.stop()
                self.bar.configure(mode="determinate", maximum=total)
                self._indeterminate = False
            self.bar.configure(maximum=total, value=current)
        elif not self._indeterminate:
            self.bar.configure(mode="indeterminate")
            self.bar.start(12)
            self._indeterminate = True

    def close(self):
        try:
            self.bar.stop()
        except tk.TclError:
            pass
        self.grab_release()
        self.destroy()


class ExportDialog(tk.Toplevel):
    def __init__(self, parent, filtered_count, on_export):
        super().__init__(parent)
        self.title("Excel-Export")
        self.transient(parent)
        self.resizable(False, False)
        self.on_export = on_export
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Welche Produkte sollen exportiert werden?", font=("", 10, "bold")).pack(anchor="w")
        self.scope = tk.StringVar(value="filter")
        for value, text in (
            ("filter", f"Aktuelle Auswahl / Filter ({filtered_count:,} Produkte)".replace(",", ".")),
            ("aktiv", "Alle aktiven Produkte"),
            ("alle", "Alle Produkte inkl. entfernter"),
        ):
            ttk.Radiobutton(frame, text=text, variable=self.scope, value=value).pack(anchor="w", pady=1)

        ttk.Label(frame, text="Zusätzliche Tabellenblätter", font=("", 10, "bold")).pack(anchor="w", pady=(12, 0))
        self.hist = tk.BooleanVar(value=True)
        self.versions = tk.BooleanVar(value=True)
        self.initial = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="Änderungshistorie (Feld, alter Wert, neuer Wert je Version)",
                        variable=self.hist).pack(anchor="w")
        ttk.Checkbutton(frame, text="   Erstimport (alle Produkte als „Neu“) in der Historie mit aufführen",
                        variable=self.initial).pack(anchor="w")
        ttk.Checkbutton(frame, text="Versionen (Übersicht aller Importe)", variable=self.versions).pack(anchor="w")

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(16, 0))
        ttk.Button(buttons, text="Abbrechen", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Exportieren …", command=self._go).pack(side="right", padx=(0, 8))
        self.grab_set()

    def _go(self):
        opts = {
            "scope": self.scope.get(),
            "history": self.hist.get(),
            "versions": self.versions.get(),
            "initial": self.initial.get(),
        }
        self.destroy()
        self.on_export(opts)


class App(tk.Tk):
    def __init__(self, db_path):
        super().__init__()
        self.title(f"HMV-Viewer – Hilfsmittelverzeichnis  (v{__version__})")
        self.geometry("1500x900")
        self.minsize(1000, 650)

        self.db_path = str(db_path)
        self.conn = db.connect(self.db_path)
        self.names = None
        self.first_id = None
        self.latest_id = None
        self.version_by_label = {}
        self.filter = ProductFilter()
        self.page = 0
        self.total = 0
        self.order = "nummer"
        self.desc = False
        self._search_job = None
        self._building = False
        self.tree_keys = {}
        self._hist_rows = {}
        self._current_nummer = None
        self._version_change_rows = {}

        style = ttk.Style(self)
        style.configure("Treeview", rowheight=22)
        style.configure("Heading.TLabel", font=("", 10, "bold"))

        self._build_toolbar()
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.tab_products = ttk.Frame(self.notebook)
        self.tab_versions = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_products, text="  Produkte  ")
        self.notebook.add(self.tab_versions, text="  Versionen & Änderungen  ")
        self._build_products_tab()
        self._build_versions_tab()

        self.status = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w", padding=(6, 2)).pack(fill="x", side="bottom")

        self.bind("<Control-f>", lambda e: (self.notebook.select(self.tab_products), self.search_entry.focus_set()))
        self.reload_all()
        if not queries.list_versions(self.conn):
            self.after(300, self._offer_first_import)

    # ------------------------------------------------------------------ Aufbau
    def _build_toolbar(self):
        bar = ttk.Frame(self, padding=(6, 6))
        bar.pack(fill="x")
        ttk.Button(bar, text="📥  XML / ZIP importieren …", command=self.start_import).pack(side="left")
        ttk.Button(bar, text="📊  Nach Excel exportieren …", command=self.start_export).pack(side="left", padx=6)
        ttk.Label(bar, text=f"Datenbank: {self.db_path}", foreground="#666").pack(side="right")

    def _build_products_tab(self):
        paned = ttk.PanedWindow(self.tab_products, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # --- links: Hierarchie
        left = ttk.Frame(paned)
        ttk.Label(left, text="Hierarchie", style="Heading.TLabel").pack(anchor="w", padx=4, pady=(4, 2))
        holder = ttk.Frame(left)
        holder.pack(fill="both", expand=True)
        self.hier = ttk.Treeview(holder, show="tree", selectmode="browse")
        _add_scrollbars(holder, self.hier, horizontal=True)
        self.hier.pack(side="left", fill="both", expand=True)
        self.hier.column("#0", width=380, stretch=False)
        self.hier.bind("<<TreeviewSelect>>", self._on_hier_select)
        paned.add(left, weight=1)

        # --- rechts
        right = ttk.PanedWindow(paned, orient="vertical")
        paned.add(right, weight=4)

        top = ttk.Frame(right)
        right.add(top, weight=3)
        self._build_filter_bar(top)
        self._build_product_list(top)

        bottom = ttk.Frame(right)
        right.add(bottom, weight=2)
        self._build_detail(bottom)

    def _build_filter_bar(self, parent):
        bar = ttk.Frame(parent, padding=(4, 4))
        bar.pack(fill="x")
        ttk.Label(bar, text="Suche:").pack(side="left")
        self.var_text = tk.StringVar()
        self.search_entry = ttk.Entry(bar, textvariable=self.var_text, width=34)
        self.search_entry.pack(side="left", padx=(4, 4))
        self.var_text.trace_add("write", lambda *a: self._schedule_filter())
        self.search_entry.bind("<Return>", lambda e: self.apply_filter())
        self.var_merk = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="auch in Merkmalen", variable=self.var_merk, command=self.apply_filter).pack(side="left", padx=(0, 10))

        ttk.Label(bar, text="Status:").pack(side="left")
        self.var_status = tk.StringVar(value="Nur aktive")
        cb = ttk.Combobox(bar, textvariable=self.var_status, values=list(STATUS_CHOICES), state="readonly", width=13)
        cb.pack(side="left", padx=(4, 10))
        cb.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())

        ttk.Label(bar, text="Änderung in:").pack(side="left")
        self.var_version = tk.StringVar(value=ALL_VERSIONS)
        self.cb_version = ttk.Combobox(bar, textvariable=self.var_version, values=[ALL_VERSIONS], state="readonly", width=24)
        self.cb_version.pack(side="left", padx=(4, 4))
        self.cb_version.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())
        self.var_type = tk.StringVar(value="Alle Änderungstypen")
        cb = ttk.Combobox(bar, textvariable=self.var_type, values=list(TYPE_CHOICES), state="readonly", width=19)
        cb.pack(side="left", padx=(0, 10))
        cb.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())

        ttk.Button(bar, text="Zurücksetzen", command=self.reset_filter).pack(side="left")

        legend = ttk.Frame(parent, padding=(6, 0))
        legend.pack(fill="x")
        ttk.Label(legend, text="Markierung der letzten Version:").pack(side="left")
        for ctype in (NEU, GEAENDERT, REAKTIVIERT, ENTFERNT):
            tk.Label(legend, text=f" {CHANGE_LABELS[ctype]} ", bg=TAG_COLORS[ctype], padx=4).pack(side="left", padx=3)

    def _build_product_list(self, parent):
        holder = ttk.Frame(parent)
        holder.pack(fill="both", expand=True, padx=4, pady=4)
        self.products = ttk.Treeview(holder, columns=[c[0] for c in PRODUCT_COLUMNS], show="headings", selectmode="browse")
        _add_scrollbars(holder, self.products, horizontal=True)
        self.products.pack(side="left", fill="both", expand=True)
        for cid, title, width, _ in PRODUCT_COLUMNS:
            self.products.heading(cid, text=title, command=lambda c=cid: self._sort_by(c))
            self.products.column(cid, width=width, minwidth=60, stretch=(cid == "bezeichnung"))
        for ctype, color in TAG_COLORS.items():
            self.products.tag_configure(ctype, background=color)
        self.products.bind("<<TreeviewSelect>>", self._on_product_select)
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Hilfsmittelnummer kopieren (01.24.01.0002)", command=lambda: self._copy(True))
        self.menu.add_command(label="Hilfsmittelnummer kopieren (0124010002)", command=lambda: self._copy(False))
        self.products.bind("<Button-3>", self._popup)
        self.products.bind("<Button-2>", self._popup)

        pager = ttk.Frame(parent, padding=(4, 0, 4, 4))
        pager.pack(fill="x")
        self.btn_prev = ttk.Button(pager, text="◀ Zurück", command=lambda: self._goto_page(self.page - 1))
        self.btn_prev.pack(side="left")
        self.btn_next = ttk.Button(pager, text="Weiter ▶", command=lambda: self._goto_page(self.page + 1))
        self.btn_next.pack(side="left", padx=6)
        self.pager_label = ttk.Label(pager, text="")
        self.pager_label.pack(side="left", padx=8)

    def _build_detail(self, parent):
        nb = ttk.Notebook(parent)
        nb.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        self.detail_nb = nb

        f_det = ttk.Frame(nb)
        nb.add(f_det, text=" Details ")
        self.detail_text = tk.Text(f_det, wrap="word", height=10, state="disabled", padx=8, pady=6)
        _add_scrollbars(f_det, self.detail_text)
        self.detail_text.pack(side="left", fill="both", expand=True)
        self.detail_text.tag_configure("title", font=("", 12, "bold"))
        self.detail_text.tag_configure("label", font=("", 9, "bold"), foreground="#444")

        f_hist = ttk.Frame(nb)
        nb.add(f_hist, text=" Historie ")
        hp = ttk.PanedWindow(f_hist, orient="horizontal")
        hp.pack(fill="both", expand=True)
        lf = ttk.Frame(hp)
        hp.add(lf, weight=2)
        self.hist_tree = ttk.Treeview(lf, columns=("version", "datum", "typ", "felder"), show="headings", selectmode="browse")
        for cid, title, w in (("version", "Version", 150), ("datum", "Importiert", 110), ("typ", "Änderung", 110), ("felder", "Felder", 200)):
            self.hist_tree.heading(cid, text=title)
            self.hist_tree.column(cid, width=w, minwidth=50)
        _add_scrollbars(lf, self.hist_tree)
        self.hist_tree.pack(side="left", fill="both", expand=True)
        for ctype, color in TAG_COLORS.items():
            self.hist_tree.tag_configure(ctype, background=color)
        self.hist_tree.bind("<<TreeviewSelect>>", self._on_hist_select)
        rf = ttk.Frame(hp)
        hp.add(rf, weight=3)
        self.hist_text = tk.Text(rf, wrap="word", height=10, state="disabled", padx=8, pady=6)
        _add_scrollbars(rf, self.hist_text)
        self.hist_text.pack(side="left", fill="both", expand=True)
        self._configure_diff_tags(self.hist_text)

    @staticmethod
    def _configure_diff_tags(text):
        text.tag_configure("head", font=("", 10, "bold"))
        text.tag_configure("field", font=("", 10, "bold"), foreground="#1f4e78", spacing1=8)
        text.tag_configure("add", background="#e6ffed")
        text.tag_configure("del", background="#ffeef0")
        text.tag_configure("hunk", foreground="#888")
        text.tag_configure("muted", foreground="#666")

    def _build_versions_tab(self):
        paned = ttk.PanedWindow(self.tab_versions, orient="vertical")
        paned.pack(fill="both", expand=True)

        top = ttk.Frame(paned)
        paned.add(top, weight=1)
        ttk.Label(top, text="Importierte Versionen (jeder Import der XML = eine Version)", style="Heading.TLabel").pack(anchor="w", padx=4, pady=4)
        cols = (("id", "Version", 70), ("imported", "Importiert am", 140), ("stand", "Stand-Datum", 95),
                ("logisch", "logische Vers.", 90), ("total", "Produkte", 80), ("neu", "Neu", 70),
                ("geaendert", "Geändert", 80), ("entfernt", "Entfernt", 80), ("wieder", "Wieder aufgen.", 100),
                ("stamm", "Änd. Stammdaten", 110), ("quelle", "Quelle", 400))
        holder = ttk.Frame(top)
        holder.pack(fill="both", expand=True, padx=4)
        self.ver_tree = ttk.Treeview(holder, columns=[c[0] for c in cols], show="headings", selectmode="browse", height=6)
        for cid, title, w in cols:
            self.ver_tree.heading(cid, text=title)
            self.ver_tree.column(cid, width=w, minwidth=50, stretch=(cid == "quelle"))
        _add_scrollbars(holder, self.ver_tree)
        self.ver_tree.pack(side="left", fill="both", expand=True)
        self.ver_tree.bind("<<TreeviewSelect>>", self._on_version_select)

        bottom = ttk.Frame(paned)
        paned.add(bottom, weight=3)
        bar = ttk.Frame(bottom, padding=(4, 6))
        bar.pack(fill="x")
        self.ver_title = ttk.Label(bar, text="Änderungen der Version", style="Heading.TLabel")
        self.ver_title.pack(side="left")
        self.var_vtype = tk.StringVar(value="Alle Änderungstypen")
        cb = ttk.Combobox(bar, textvariable=self.var_vtype, values=list(TYPE_CHOICES), state="readonly", width=19)
        cb.pack(side="left", padx=10)
        cb.bind("<<ComboboxSelected>>", lambda e: self._load_version_changes())
        ttk.Button(bar, text="In Produktliste anzeigen", command=self._show_version_in_products).pack(side="left")
        self.ver_note = ttk.Label(bar, text="", foreground="#666")
        self.ver_note.pack(side="left", padx=10)

        cols = (("typ", "Änderung", 120), ("ebene", "Ebene", 110), ("nummer", "Nummer", 120),
                ("name", "Bezeichnung", 480), ("felder", "Geänderte Felder", 280))
        holder = ttk.Frame(bottom)
        holder.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        self.chg_tree = ttk.Treeview(holder, columns=[c[0] for c in cols], show="headings", selectmode="browse")
        for cid, title, w in cols:
            self.chg_tree.heading(cid, text=title)
            self.chg_tree.column(cid, width=w, minwidth=60, stretch=(cid == "name"))
        for ctype, color in TAG_COLORS.items():
            self.chg_tree.tag_configure(ctype, background=color)
        _add_scrollbars(holder, self.chg_tree)
        self.chg_tree.pack(side="left", fill="both", expand=True)
        self.chg_tree.bind("<Double-1>", self._on_change_double_click)

    # ------------------------------------------------------------------ Laden
    def reload_all(self):
        self.names = queries.Names(self.conn)
        self.first_id = queries.first_import_id(self.conn)
        self.latest_id = queries.latest_import_id(self.conn)
        versions = queries.list_versions(self.conn)
        labels = [queries.version_label(v) for v in versions]
        self.version_by_label = {queries.version_label(v): v["id"] for v in versions}
        self.cb_version.configure(values=[ALL_VERSIONS] + labels)
        if self.var_version.get() not in self.version_by_label:
            self.var_version.set(ALL_VERSIONS)
        self._load_hierarchy()
        self._read_filter()
        self.page = 0
        self.refresh_list()
        self._load_versions()

    def _load_hierarchy(self):
        self._building = True
        try:
            self.hier.delete(*self.hier.get_children())
            self.tree_keys = {}
            total = queries.count_products(self.conn, ProductFilter(status="aktiv"))
            root = self.hier.insert("", "end", text=f"Alle Produkte ({total:,})".replace(",", "."), open=True)
            self.tree_keys[root] = {}

            def add(parent, nodes, depth):
                for n in nodes:
                    iid = self.hier.insert(parent, "end", text=f"{n['label']}  ({n['count']})")
                    self.tree_keys[iid] = n["key"]
                    add(iid, n["children"], depth + 1)

            add(root, queries.hierarchy_tree(self.conn), 1)
            self.hier.selection_set(root)
        finally:
            self._building = False

    def _read_filter(self):
        key = {}
        sel = self.hier.selection()
        if sel:
            key = self.tree_keys.get(sel[0], {})
        version_id = self.version_by_label.get(self.var_version.get())
        self.filter = ProductFilter(
            text=self.var_text.get().strip(),
            in_merkmale=self.var_merk.get(),
            status=STATUS_CHOICES.get(self.var_status.get(), "aktiv"),
            gruppe=key.get("gruppe"), ort=key.get("ort"),
            untergruppe=key.get("untergruppe"), art=key.get("art"),
            import_id=version_id,
            change_type=TYPE_CHOICES.get(self.var_type.get()),
        )

    def apply_filter(self):
        if self._search_job is not None:
            self.after_cancel(self._search_job)
            self._search_job = None
        self._read_filter()
        self.page = 0
        self.refresh_list()

    def _schedule_filter(self):
        if self._search_job is not None:
            self.after_cancel(self._search_job)
        self._search_job = self.after(300, self.apply_filter)

    def reset_filter(self):
        self.var_text.set("")
        self.var_merk.set(False)
        self.var_status.set("Nur aktive")
        self.var_version.set(ALL_VERSIONS)
        self.var_type.set("Alle Änderungstypen")
        children = self.hier.get_children()
        if children:
            self.hier.selection_set(children[0])
        self.apply_filter()

    def _on_hier_select(self, _event):
        if not self._building:
            self.apply_filter()

    def _sort_by(self, cid):
        key = next(c[3] for c in PRODUCT_COLUMNS if c[0] == cid)
        self.desc = (not self.desc) if self.order == key else False
        self.order = key
        self.page = 0
        self.refresh_list()

    def _goto_page(self, page):
        self.page = max(0, page)
        self.refresh_list()

    def _status_text(self, p):
        if not p["active"]:
            return f"Entfernt in V{p['removed_import']}"
        if p["last_import_change"] == self.first_id and p["last_change_type"] == NEU:
            return "Erstimport"
        return f"{CHANGE_LABELS.get(p['last_change_type'], '')} in V{p['last_import_change']}"

    def _row_tag(self, p):
        if not p["active"]:
            return ENTFERNT
        if self.filter.import_id is not None:
            if self.filter.import_id == self.first_id:
                return None
            return p["shown_type"]
        if p["last_import_change"] == self.latest_id and self.latest_id != self.first_id:
            return p["last_change_type"]
        return None

    def refresh_list(self):
        self.total = queries.count_products(self.conn, self.filter)
        pages = max(1, -(-self.total // PAGE_SIZE))
        if self.page >= pages:
            self.page = pages - 1
        rows = queries.fetch_products(self.conn, self.filter, self.order, self.desc,
                                      limit=PAGE_SIZE, offset=self.page * PAGE_SIZE)
        self.products.delete(*self.products.get_children())
        for p in rows:
            art = self.names.path(p)["art"]
            tag = self._row_tag(p)
            self.products.insert("", "end", iid=p["nummer"], tags=(tag,) if tag else (), values=(
                format_nummer(p["nummer"]), p["bezeichnung"] or "", p["hersteller"] or "", art,
                fmt_date(p["aufnahmedatum"]), fmt_date(p["aenderungsdatum"]), self._status_text(p)))
        for cid, _, _, key in PRODUCT_COLUMNS:
            arrow = (" ▼" if self.desc else " ▲") if key == self.order else ""
            title = next(c[1] for c in PRODUCT_COLUMNS if c[0] == cid)
            self.products.heading(cid, text=title + arrow)
        first = self.page * PAGE_SIZE + 1 if self.total else 0
        last = min(self.total, (self.page + 1) * PAGE_SIZE)
        self.pager_label.configure(
            text=f"{self.total:,} Treffer  ·  Zeilen {first:,}–{last:,}  ·  Seite {self.page + 1}/{pages}".replace(",", "."))
        self.btn_prev.state(["!disabled"] if self.page > 0 else ["disabled"])
        self.btn_next.state(["!disabled"] if self.page + 1 < pages else ["disabled"])
        self.status.set(f"{self.total:,} Produkte in der aktuellen Auswahl".replace(",", "."))
        self._show_detail(None)

    # ------------------------------------------------------------------ Details
    def _on_product_select(self, _event):
        sel = self.products.selection()
        self._show_detail(sel[0] if sel else None)

    def _set_text(self, widget, parts):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        for text, tag in parts:
            widget.insert("end", text, (tag,) if tag else ())
        widget.configure(state="disabled")

    def _show_detail(self, nummer):
        self._current_nummer = nummer
        self.hist_tree.delete(*self.hist_tree.get_children())
        self._hist_rows = {}
        self._set_text(self.hist_text, [])
        if not nummer:
            self._set_text(self.detail_text, [("Produkt in der Liste auswählen, um Details und Historie zu sehen.", "label")])
            return
        p = queries.get_product(self.conn, nummer)
        if p is None:
            return
        path = self.names.path(p)
        status = self._status_text(p)
        parts = [
            (f"{p['bezeichnung'] or '(ohne Bezeichnung)'}\n", "title"),
            ("Hilfsmittelnummer: ", "label"), (f"{format_nummer(p['nummer'])}   (10-stellig: {p['nummer']})\n", None),
            ("Hersteller: ", "label"), (f"{p['hersteller'] or ''}\n", None),
            ("Produktgruppe: ", "label"), (f"{path['gruppe']}\n", None),
            ("Anwendungsort: ", "label"), (f"{path['ort']}\n", None),
            ("Untergruppe: ", "label"), (f"{path['untergruppe']}\n", None),
            ("Produktart: ", "label"), (f"{path['art']}\n", None),
            ("Aufnahme: ", "label"), (f"{fmt_date(p['aufnahmedatum'])}", None),
            ("    Änderung (HMV): ", "label"), (f"{fmt_date(p['aenderungsdatum']) or '–'}\n", None),
            ("Status im Bestand: ", "label"), (f"{'aktiv' if p['active'] else 'entfernt'}  ·  {status}\n\n", None),
            ("Merkmale\n", "label"), (f"{p['merkmale'] or '–'}\n", None),
        ]
        self._set_text(self.detail_text, parts)

        history = queries.product_history(self.conn, nummer)
        vlabels = queries.version_labels(self.conn)
        for h in history:
            iid = str(h["id"])
            self._hist_rows[iid] = h
            felder = ", ".join(FIELD_LABELS.get(f, f) for f in h["changes"])
            self.hist_tree.insert("", "end", iid=iid, tags=(h["change_type"],), values=(
                vlabels.get(h["import_id"], f"V{h['import_id']}"), (h["imported_at"] or "")[:10],
                CHANGE_LABELS.get(h["change_type"], h["change_type"]), felder))
        kids = self.hist_tree.get_children()
        if kids:
            self.hist_tree.selection_set(kids[0])
        else:
            self._set_text(self.hist_text, [("Keine Historie vorhanden.", "muted")])

    def _on_hist_select(self, _event):
        sel = self.hist_tree.selection()
        if not sel:
            return
        h = self._hist_rows.get(sel[0])
        if h is None:
            return
        vlabels = queries.version_labels(self.conn)
        ctype = h["change_type"]
        parts = [(f"{CHANGE_LABELS.get(ctype, ctype)} in {vlabels.get(h['import_id'], 'V' + str(h['import_id']))}\n", "head"),
                 (f"Importiert am {(h['imported_at'] or '').replace('T', ' ')}  ·  Quelle: {h['source_name']}\n", "muted")]
        if not h["changes"]:
            msg = {
                NEU: "Das Produkt ist in dieser Version neu im Verzeichnis.",
                ENTFERNT: "Das Produkt war in dieser XML nicht mehr enthalten und wurde als „entfernt“ markiert.",
                REAKTIVIERT: "Das Produkt war zuvor entfernt und ist in dieser XML wieder enthalten (Felder unverändert).",
            }.get(ctype, "Keine Feldänderungen gespeichert.")
            parts.append(("\n" + msg, None))
        for fld, (old, new) in h["changes"].items():
            parts.append((f"\n{FIELD_LABELS.get(fld, fld)}\n", "field"))
            parts.extend(self._diff_parts(old, new))
        self._set_text(self.hist_text, parts)

    @staticmethod
    def _diff_parts(old, new):
        old_s = "" if old is None else str(old)
        new_s = "" if new is None else str(new)
        if "\n" not in old_s and "\n" not in new_s and len(old_s) <= 160 and len(new_s) <= 160:
            return [(f"alt:  {old_s or '(leer)'}\n", "del"), (f"neu:  {new_s or '(leer)'}\n", "add")]
        parts = []
        lines = list(difflib.unified_diff(old_s.splitlines(), new_s.splitlines(), lineterm="", n=2))
        for line in lines[2:]:   # '---' / '+++' überspringen
            tag = "add" if line.startswith("+") else "del" if line.startswith("-") else "hunk" if line.startswith("@@") else None
            parts.append((line + "\n", tag))
        return parts or [("(nur Leerraum geändert)\n", "muted")]

    def _popup(self, event):
        item = self.products.identify_row(event.y)
        if item:
            self.products.selection_set(item)
            self.menu.tk_popup(event.x_root, event.y_root)

    def _copy(self, formatted):
        sel = self.products.selection()
        if sel:
            self.clipboard_clear()
            self.clipboard_append(format_nummer(sel[0]) if formatted else sel[0])

    # ------------------------------------------------------------------ Versionen-Tab
    def _load_versions(self):
        self.ver_tree.delete(*self.ver_tree.get_children())
        for v in queries.list_versions(self.conn):
            self.ver_tree.insert("", "end", iid=str(v["id"]), values=(
                f"V{v['id']}", (v["imported_at"] or "").replace("T", " "), fmt_date(v["source_date"]),
                v["logische_version"] or "", f"{v['n_total']:,}".replace(",", "."),
                v["n_new"], v["n_changed"], v["n_removed"], v["n_reactivated"], v["n_stamm_changes"], v["source_name"]))
        kids = self.ver_tree.get_children()
        if kids:
            self.ver_tree.selection_set(kids[0])
        else:
            self.chg_tree.delete(*self.chg_tree.get_children())
            self.ver_note.configure(text="Noch keine Version importiert.")

    def _selected_version(self):
        sel = self.ver_tree.selection()
        return int(sel[0]) if sel else None

    def _on_version_select(self, _event):
        self._load_version_changes()

    def _load_version_changes(self):
        vid = self._selected_version()
        self.chg_tree.delete(*self.chg_tree.get_children())
        self._version_change_rows = {}
        if vid is None:
            return
        ctype = TYPE_CHOICES.get(self.var_vtype.get())
        limit = 5000
        total = queries.count_changes(self.conn, vid, ctype)
        rows = queries.version_changes(self.conn, vid, ctype, limit)
        for i, r in enumerate(rows):
            iid = str(i)
            self._version_change_rows[iid] = r
            self.chg_tree.insert("", "end", iid=iid, tags=(r["change_type"],), values=(
                CHANGE_LABELS.get(r["change_type"], r["change_type"]), r["entity_label"], r["display_k"], r["name"], r["fields"]))
        self.ver_title.configure(text=f"Änderungen in V{vid}:")
        note = f"{total:,} Einträge".replace(",", ".")
        if vid == self.first_id:
            note += "  (Erstimport: alle Produkte gelten als „Neu“)"
        if total > limit:
            note += f"  –  angezeigt werden die ersten {limit:,}".replace(",", ".")
        self.ver_note.configure(text=note)

    def _show_version_in_products(self):
        vid = self._selected_version()
        if vid is None:
            return
        label = next((l for l, i in self.version_by_label.items() if i == vid), ALL_VERSIONS)
        self.var_version.set(label)
        self.var_type.set(self.var_vtype.get())
        self.var_status.set("Alle")
        self.var_text.set("")
        self.notebook.select(self.tab_products)
        self.apply_filter()

    def _on_change_double_click(self, _event):
        sel = self.chg_tree.selection()
        r = self._version_change_rows.get(sel[0]) if sel else None
        if not r or r["entity"] != "PRODUKT":
            return
        vid = self._selected_version()
        label = next((l for l, i in self.version_by_label.items() if i == vid), ALL_VERSIONS)
        self.var_version.set(label)
        self.var_type.set("Alle Änderungstypen")
        self.var_status.set("Alle")
        self.var_text.set(r["display_k"])
        self.notebook.select(self.tab_products)
        self.apply_filter()
        if self.products.exists(r["k"]):
            self.products.selection_set(r["k"])
            self.products.see(r["k"])

    # ------------------------------------------------------------------ Import
    def _offer_first_import(self):
        if messagebox.askyesno("Erster Start", "Es ist noch keine HMV-XML importiert.\n\nJetzt eine XML- oder ZIP-Datei auswählen?"):
            self.start_import()

    def start_import(self):
        path = filedialog.askopenfilename(
            title="HMV-XML oder ZIP auswählen",
            filetypes=[("HMV XML / ZIP", "*.xml *.zip"), ("Alle Dateien", "*.*")])
        if path:
            self._run_import(path, force=False)

    def _run_import(self, path, force):
        dlg = ProgressDialog(self, "Import läuft")
        q = queue.Queue()

        def worker():
            try:
                conn = db.connect(self.db_path)
                try:
                    res = importer.import_file(conn, path, force=force,
                                               progress=lambda s, c, t: q.put(("progress", s, c, t)))
                finally:
                    conn.close()
                q.put(("done", res))
            except BaseException as exc:  # noqa: BLE001 - an die GUI weiterreichen
                q.put(("error", exc))

        threading.Thread(target=worker, daemon=True).start()
        self._watch(q, dlg, lambda res: self._import_done(res), lambda exc: self._import_failed(exc, path))

    def _import_done(self, res):
        self.reload_all()
        if res.first_import:
            text = (f"Erstimport abgeschlossen (Version {res.import_id}).\n\n{res.n_total:,} Produkte eingelesen.\n"
                    "Dies ist die Ausgangsbasis – ab dem nächsten Import werden Änderungen markiert.").replace(",", ".")
        else:
            text = (f"Version {res.import_id} importiert – {res.n_total:,} Produkte in der Datei.\n\n"
                    f"Neu:  {res.n_new}\nGeändert:  {res.n_changed}\nEntfernt:  {res.n_removed}\n"
                    f"Wieder aufgenommen:  {res.n_reactivated}\nUnverändert:  {res.n_unchanged:,}\n"
                    f"Änderungen an Gruppen/Orten/Untergruppen/Arten:  {res.n_stamm_changes}").replace(",", ".")
            self.var_version.set(next((l for l, i in self.version_by_label.items() if i == res.import_id), ALL_VERSIONS))
            self.var_status.set("Alle")
            self.apply_filter()
        if res.warnings:
            text += f"\n\n{len(res.warnings)} Warnung(en), z. B.: {res.warnings[0]}"
        messagebox.showinfo("Import abgeschlossen", text)

    def _import_failed(self, exc, path):
        if isinstance(exc, importer.DuplicateImport):
            if messagebox.askyesno("Bereits importiert", f"{exc}\n\nTrotzdem erneut importieren?\n(Es entsteht eine neue Version.)"):
                self._run_import(path, force=True)
        elif isinstance(exc, importer.SuspiciousImport):
            if messagebox.askyesno("Plausibilitätswarnung", f"{exc}\n\nTrotzdem importieren?\n(Fehlende Produkte würden als „entfernt“ markiert.)"):
                self._run_import(path, force=True)
        elif isinstance(exc, ET.ParseError):
            messagebox.showerror("Import fehlgeschlagen", f"Die Datei ist keine gültige XML:\n{exc}")
        elif isinstance(exc, (SourceError, importer.EmptyImport)):
            messagebox.showerror("Import fehlgeschlagen", str(exc))
        else:
            messagebox.showerror("Import fehlgeschlagen", f"{type(exc).__name__}: {exc}")

    # ------------------------------------------------------------------ Export
    def start_export(self):
        if not queries.list_versions(self.conn):
            messagebox.showinfo("Export", "Es sind noch keine Daten vorhanden – bitte zuerst eine XML importieren.")
            return
        ExportDialog(self, self.total, self._export_with_options)

    def _export_with_options(self, opts):
        stamp = dt.date.today().strftime("%Y%m%d")
        path = filedialog.asksaveasfilename(
            title="Excel-Datei speichern", defaultextension=".xlsx",
            initialfile=f"HMV_Export_{stamp}.xlsx", filetypes=[("Excel-Arbeitsmappe", "*.xlsx")])
        if not path:
            return
        if opts["scope"] == "filter":
            f = replace(self.filter)
        else:
            f = ProductFilter(status=opts["scope"])
        dlg = ProgressDialog(self, "Excel-Export läuft")
        q = queue.Queue()

        def worker():
            try:
                conn = db.connect(self.db_path)
                try:
                    res = exporter.export_excel(
                        conn, path, f, include_history=opts["history"], include_versions=opts["versions"],
                        include_initial_in_history=opts["initial"],
                        progress=lambda s, c, t: q.put(("progress", s, c, t)))
                finally:
                    conn.close()
                q.put(("done", res))
            except BaseException as exc:  # noqa: BLE001
                q.put(("error", exc))

        threading.Thread(target=worker, daemon=True).start()

        def done(res):
            msg = f"{res['products']:,} Produkte exportiert".replace(",", ".")
            if opts["history"]:
                msg += f"\n{res['history_rows']:,} Zeilen in der Änderungshistorie".replace(",", ".")
            messagebox.showinfo("Export abgeschlossen", f"{msg}\n\n{path}")

        def failed(exc):
            if isinstance(exc, PermissionError):
                messagebox.showerror("Export fehlgeschlagen",
                                     f"Die Datei konnte nicht geschrieben werden (ist sie in Excel geöffnet?):\n{path}")
            else:
                messagebox.showerror("Export fehlgeschlagen", f"{type(exc).__name__}: {exc}")

        self._watch(q, dlg, done, failed)

    # ------------------------------------------------------------------ Hilfsfunktionen
    def _watch(self, q, dlg, on_done, on_error):
        """Pollt die Worker-Queue im GUI-Thread."""
        try:
            while True:
                msg = q.get_nowait()
                if msg[0] == "progress":
                    dlg.set_progress(msg[1], msg[2], msg[3])
                elif msg[0] == "done":
                    dlg.close()
                    on_done(msg[1])
                    return
                else:
                    dlg.close()
                    on_error(msg[1])
                    return
        except queue.Empty:
            pass
        self.after(100, lambda: self._watch(q, dlg, on_done, on_error))


def run_gui(db_path):
    app = App(db_path)
    app.mainloop()
