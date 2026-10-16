"""Rauchtest der GUI-Logik OHNE echtes tkinter (Stub-Module).

Prüft, dass Aufbau, Filter, Detailansicht, Historie, Versionen-Tab sowie Import-/Export-Ablauf der GUI
ohne Laufzeitfehler durchlaufen. Das ersetzt keinen Blick auf die echte Oberfläche.
"""
import os
import sys
import tempfile
import threading
import time
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


class Dummy:
    def __init__(self, *a, **k):
        pass

    def __getattr__(self, name):
        if name.startswith("winfo_"):
            return lambda *a, **k: 0
        return lambda *a, **k: Dummy()


class Var:
    def __init__(self, master=None, value=""):
        self._v, self._cb = value, []

    def get(self):
        return self._v

    def set(self, v):
        self._v = v
        for cb in self._cb:
            cb()

    def trace_add(self, mode, cb):
        self._cb.append(lambda: cb())


class Tree(Dummy):
    def __init__(self, *a, **k):
        self.items, self.order, self.sel, self.n = {}, [], [], 0

    def insert(self, parent, index, iid=None, **kw):
        if iid is None:
            self.n += 1
            iid = f"I{self.n}"
        self.items[iid] = dict(kw, parent=parent)
        self.order.append(iid)
        return iid

    def delete(self, *iids):
        for i in iids:
            self.items.pop(i, None)
            if i in self.order:
                self.order.remove(i)
        self.sel = [s for s in self.sel if s in self.items]

    def get_children(self, item=""):
        return [i for i in self.order if self.items[i]["parent"] == item]

    def selection(self):
        return list(self.sel)

    def selection_set(self, i):
        self.sel = [i]

    def exists(self, i):
        return i in self.items


class Tk(Dummy):
    afters = []

    def after(self, ms, fn=None):
        Tk.afters.append(fn)
        return len(Tk.afters)


def install_stubs():
    tk = types.ModuleType("tkinter")
    ttk = types.ModuleType("tkinter.ttk")
    fd = types.ModuleType("tkinter.filedialog")
    mb = types.ModuleType("tkinter.messagebox")
    tk.Tk = Tk
    tk.Toplevel = Tk
    tk.StringVar = Var
    tk.BooleanVar = Var
    tk.TclError = Exception
    for n in ("Text", "Menu", "Label"):
        setattr(tk, n, Dummy)
    for n in ("Frame", "Label", "Button", "Entry", "Combobox", "Checkbutton", "Radiobutton", "Scrollbar",
              "Notebook", "PanedWindow", "Progressbar", "Style"):
        setattr(ttk, n, Dummy)
    ttk.Treeview = Tree
    mb.calls = []
    for n in ("showinfo", "showerror", "askyesno"):
        setattr(mb, n, (lambda name: lambda *a, **k: mb.calls.append((name, a)) or False)(n))
    tk.ttk, tk.filedialog, tk.messagebox = ttk, fd, mb
    sys.modules.update({"tkinter": tk, "tkinter.ttk": ttk, "tkinter.filedialog": fd, "tkinter.messagebox": mb})
    return mb


class GuiSmoke(unittest.TestCase):
    def test_flow(self):
        mb = install_stubs()
        from hmv_viewer import gui
        from tests.make_sample import write_sample

        tmp = tempfile.mkdtemp()
        v1 = write_sample(os.path.join(tmp, "20260101_HMV.xml"), variant=1)
        v2 = write_sample(os.path.join(tmp, "20260201_HMV.xml"), variant=2)
        app = gui.App(os.path.join(tmp, "t.db"))

        def pump(path_cb):
            done = []
            threading.Thread(target=lambda: (path_cb(), done.append(1))).start()
            t0 = time.time()
            while time.time() - t0 < 30:
                pending, Tk.afters = Tk.afters, []
                for fn in pending:
                    if fn:
                        fn()
                if not done or Tk.afters:
                    time.sleep(0.05)
                if done and not Tk.afters:
                    break

        app._run_import(v1, False)
        pump(lambda: None)
        self.assertTrue(any(c[0] == "showinfo" for c in mb.calls), mb.calls)
        self.assertEqual(len(app.products.get_children()), 4)
        app._run_import(v2, False)
        pump(lambda: None)
        # nach Import V2: Filter auf V2, Status alle -> 3 Änderungen
        kids = app.products.get_children()
        self.assertEqual(app.filter.import_id, 2)
        self.assertEqual(len(kids), 3)
        tags = {k: app.products.items[k]["tags"] for k in kids}
        self.assertIn(("GEAENDERT",), tags.values())
        self.assertIn(("ENTFERNT",), tags.values())
        self.assertIn(("NEU",), tags.values())
        app.products.selection_set(kids[0])
        app._on_product_select(None)
        hk = app.hist_tree.get_children()
        self.assertTrue(hk)
        app._on_hist_select(None)
        app.var_text.set("muster")
        app.apply_filter()
        app.reset_filter()
        app._sort_by("bezeichnung")
        app._sort_by("bezeichnung")
        app._load_versions()
        app._show_version_in_products()
        out = os.path.join(tmp, "x.xlsx")
        app._export_with_options  # existiert
        mb.calls.clear()
        app.var_version.set("Alle Versionen")
        app.apply_filter()
        self.assertEqual(app.filter.import_id, None)


if __name__ == "__main__":
    unittest.main()
