"""Netzlaufwerk-Leistung: Zählungen nur aus dem kleinen Index, zweistufiges Laden der Liste liefert dasselbe wie vorher."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hmv_viewer import db, importer, queries  # noqa: E402
from hmv_viewer.queries import ProductFilter as F  # noqa: E402
from tests.make_sample import write_sample  # noqa: E402


def old_fetch(conn, f, order, desc, limit, offset):
    """Bisherige Abfrage in einem Schritt (Referenz)."""
    join, where, params = queries._build(f)
    shown = "h.change_type" if f.import_id is not None else "NULL"
    direction = "DESC" if desc else "ASC"
    order_by = ", ".join(f"{c.strip()} {direction}" for c in queries.ORDER_COLUMNS[order].split(",")) + ", p.nummer ASC"
    return conn.execute(f"SELECT p.*, {shown} AS shown_type FROM produkt p{join}{where} ORDER BY {order_by} LIMIT ? OFFSET ?",
                        params + [limit, offset]).fetchall()


class NetworkFriendly(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = tempfile.mkdtemp()
        cls.conn = db.connect(os.path.join(tmp, "t.db"))
        importer.import_file(cls.conn, write_sample(os.path.join(tmp, "20260101_HMV.xml"), variant=1))
        importer.import_file(cls.conn, write_sample(os.path.join(tmp, "20260201_HMV.xml"), variant=2))

    def plan(self, sql, params=()):
        return " | ".join(r[3] for r in self.conn.execute("EXPLAIN QUERY PLAN " + sql, params))

    def test_counts_use_small_index_only(self):
        self.assertIn("COVERING INDEX ix_produkt_aktiv", self.plan("SELECT COUNT(*) FROM produkt p WHERE p.active=1"))
        self.assertIn("COVERING INDEX ix_produkt_aktiv", self.plan(
            "SELECT gruppe, ort, untergruppe, art, COUNT(*) FROM produkt WHERE active=1 GROUP BY gruppe, ort, untergruppe, art"))
        self.assertIn("COVERING INDEX ix_stamm_name", self.plan(
            "SELECT entity, gruppe, ort, untergruppe, art, json_extract(data, '$.BEZEICHNUNG') AS name FROM stamm"))

    def test_two_step_fetch_matches_old_query(self):
        filters = [F(status="aktiv"), F(status="alle"), F(status="alle", import_id=2), F(status="alle", import_id=2,
                   change_type="GEAENDERT"), F(status="aktiv", text="Pumpe"), F(status="aktiv", hersteller="Muster")]
        for f in filters:
            for order in queries.ORDER_COLUMNS:
                for desc in (False, True):
                    for limit, offset in ((500, 0), (2, 1)):
                        with self.subTest(f=f, order=order, desc=desc, offset=offset):
                            new = [dict(r) for r in queries.fetch_products(self.conn, f, order, desc, limit, offset)]
                            old = [dict(r) for r in old_fetch(self.conn, f, order, desc, limit, offset)]
                            self.assertEqual(new, old)


if __name__ == "__main__":
    unittest.main()
