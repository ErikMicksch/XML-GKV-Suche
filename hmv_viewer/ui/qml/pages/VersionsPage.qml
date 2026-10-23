import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// Versionen: oben die eingelesenen Ausgaben, unten was sich in der gewählten Version geändert hat
Item {
    property var ui
    SplitView {
        anchors.fill: parent
        anchors.margins: 14
        orientation: Qt.Vertical
        handle: Item {
            implicitHeight: 14
            Rectangle { anchors.centerIn: parent; width: 56; height: 4; radius: 2
                        color: SplitHandle.hovered || SplitHandle.pressed ? theme.c.green : theme.c.line }
        }
        Card {
            SplitView.preferredHeight: 300
            SplitView.minimumHeight: 180
            ColumnLayout {
                anchors.fill: parent
                spacing: 8
                AppText { text: "Eingelesene Versionen"; font.weight: Font.Bold; rel: 1.15 }
                AppText { text: "Jede eingelesene HMV-Ausgabe ist eine Version. Version anklicken – unten steht, was sich geändert hat."
                          color: theme.c.muted; rel: 0.9; Layout.fillWidth: true; wrapMode: Text.WordWrap; elide: Text.ElideNone }
                DataTable {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: versions.versionModel
                    columns: versions.versionColumns
                    resizable: false
                    emptyText: "Noch keine Version eingelesen."
                    onRowClicked: (row) => versions.select(row)
                    onMoveRequested: (delta) => versions.select(Math.max(0, versionsIndex() + delta))
                    function versionsIndex() {
                        for (var i = 0; i < model.count; i++) if (model.get(i).selected) return i
                        return 0
                    }
                }
            }
        }
        Card {
            SplitView.fillHeight: true
            ColumnLayout {
                anchors.fill: parent
                spacing: 8
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    AppText { text: versions.title; font.weight: Font.Bold; rel: 1.15 }
                    Combo { Layout.preferredWidth: 260; label: "Art der Änderung"; model: versions.typeOptions
                            value: versions.typeValue; onPicked: (v) => versions.setType(v) }
                    Btn { primary: true; iconName: "box"; text: "In der Produktliste anzeigen"; onClicked: versions.showInProducts() }
                    AppText { text: versions.note; color: theme.c.muted; Layout.fillWidth: true }
                }
                AppText { text: "Doppelklick auf ein Produkt öffnet es."; color: theme.c.muted; rel: 0.85 }
                DataTable {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: versions.changeModel
                    columns: versions.changeColumns
                    resizable: false
                    emptyText: "Keine Änderungen für diese Auswahl."
                    onRowDoubleClicked: (row) => versions.openChange(row)
                }
            }
        }
    }
}
