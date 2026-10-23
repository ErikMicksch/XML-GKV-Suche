"""Listenmodell für QML: Zeilen sind dicts, Rollen = Schlüssel."""
from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Property, Signal, Slot


class DictModel(QAbstractListModel):
    countChanged = Signal()

    def __init__(self, roles, parent=None):
        super().__init__(parent)
        self._roles = list(roles)
        self._rows: list[dict] = []

    def roleNames(self):
        return {int(Qt.ItemDataRole.UserRole) + 1 + i: r.encode() for i, r in enumerate(self._roles)}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        i = role - int(Qt.ItemDataRole.UserRole) - 1
        return self._rows[index.row()].get(self._roles[i]) if 0 <= i < len(self._roles) else None

    count = Property(int, lambda self: len(self._rows), notify=countChanged)

    @property
    def rows(self):
        return self._rows

    def set_rows(self, rows):
        self.beginResetModel()
        self._rows = [dict(r) for r in rows]
        self.endResetModel()
        self.countChanged.emit()

    def append_rows(self, rows):
        if not rows:
            return
        self.beginInsertRows(QModelIndex(), len(self._rows), len(self._rows) + len(rows) - 1)
        self._rows += [dict(r) for r in rows]
        self.endInsertRows()
        self.countChanged.emit()

    def update_row(self, i, **changes):
        if 0 <= i < len(self._rows):
            self._rows[i].update(changes)
            idx = self.index(i)
            self.dataChanged.emit(idx, idx)

    def sync(self, rows, key):
        """Neue Zeilen übernehmen, ohne die Ansicht zurückzusetzen (Bildlaufposition bleibt beim Auf-/Zuklappen)."""
        old = self._rows
        new = [dict(r) for r in rows]
        start = 0
        while start < len(old) and start < len(new) and old[start][key] == new[start][key]:
            start += 1
        end_old, end_new = len(old), len(new)
        while end_old > start and end_new > start and old[end_old - 1][key] == new[end_new - 1][key]:
            end_old -= 1
            end_new -= 1
        if end_old > start:
            self.beginRemoveRows(QModelIndex(), start, end_old - 1)
            del self._rows[start:end_old]
            self.endRemoveRows()
        if end_new > start:
            self.beginInsertRows(QModelIndex(), start, end_new - 1)
            self._rows[start:start] = new[start:end_new]
            self.endInsertRows()
        for i, row in enumerate(new):   # gleiche Schlüssel, evtl. geänderte Werte (Auswahl, Anzahl …)
            if self._rows[i] != row:
                self._rows[i] = row
                idx = self.index(i)
                self.dataChanged.emit(idx, idx)
        if len(old) != len(new):
            self.countChanged.emit()

    @Slot(int, result="QVariantMap")
    def get(self, i):
        return dict(self._rows[i]) if 0 <= i < len(self._rows) else {}
