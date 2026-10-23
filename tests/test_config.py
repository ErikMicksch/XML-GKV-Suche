"""Pfad-Datei hmv_pfade.json: Datenbank und Sicherungsordner aus einer austauschbaren Datei."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hmv_viewer import config  # noqa: E402


class PathsFile(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.file = self.dir / "hmv_pfade.json"
        env = {k: v for k, v in os.environ.items() if k != "HMV_DB"}
        env["HMV_PFADE"] = str(self.file)
        env["HMV_TESTORDNER"] = str(self.dir / "x")
        self.env = mock.patch.dict(os.environ, env, clear=True)
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_without_file_defaults(self):
        self.assertEqual(config.load_paths(), {})
        self.assertEqual(config.backup_dir(self.dir / "db" / "hmv.db"), self.dir / "db" / "sicherungen")

    def test_relative_absolute_and_variables(self):
        self.file.write_text(json.dumps({"datenbank": "daten/hmv.db", "sicherungen": "%HMV_TESTORDNER%\\sich"}),
                             encoding="utf-8")
        self.assertEqual(config.default_db_path(), self.dir / "daten" / "hmv.db")
        self.assertEqual(config.backup_dir("egal.db"), Path(str(self.dir / "x") + "\\sich"))

    def test_only_database_keeps_backup_next_to_it(self):
        self.file.write_text(json.dumps({"datenbank": str(self.dir / "d" / "hmv.db")}), encoding="utf-8")
        self.assertEqual(config.backup_dir(config.default_db_path()), self.dir / "d" / "sicherungen")

    def test_env_db_has_priority(self):
        self.file.write_text(json.dumps({"datenbank": "a.db"}), encoding="utf-8")
        with mock.patch.dict(os.environ, {"HMV_DB": str(self.dir / "b.db")}):
            self.assertEqual(config.default_db_path(), self.dir / "b.db")

    def test_broken_file_stops_with_hint(self):
        self.file.write_text('{"datenbank": "C:\\HMV\\hmv.db"}', encoding="utf-8")   # einfache Backslashes = kein JSON
        with self.assertRaises(ValueError) as ctx:
            config.load_paths()
        self.assertIn("doppelt", str(ctx.exception))

    def test_save_roundtrip(self):
        config.save_paths(self.dir / "n.db", self.dir / "s")
        self.assertEqual(config.load_paths(), {"datenbank": self.dir / "n.db", "sicherungen": self.dir / "s"})


if __name__ == "__main__":
    unittest.main()
