import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// Spalten der Produktliste: ein-/ausblenden und mit Pfeilen ordnen (Breite: am Spaltenkopf ziehen)
AppDialog {
    id: dlg
    title: "Spalten der Produktliste"
    iconName: "table"
    preferredWidth: 560
    maxHeight: 820

    AppText {
        Layout.fillWidth: true
        color: theme.c.muted
        wrapMode: Text.WordWrap
        elide: Text.ElideNone
        text: "Häkchen = Spalte anzeigen. Mit den Pfeilen ändern Sie die Reihenfolge. Breite: Rand im Spaltenkopf ziehen, Doppelklick auf den Rand = passende Breite."
    }
    ListView {
        id: lv
        Layout.fillWidth: true
        Layout.preferredHeight: Math.min(contentHeight, 520)
        clip: true
        model: products.columns
        ScrollBar.vertical: ScrollBar { }
        delegate: RowLayout {
            width: lv.width
            spacing: 6
            Check {
                Layout.fillWidth: true
                text: modelData.label + (modelData.locked ? "  (immer sichtbar)" : "")
                checked: modelData.visible
                enabled: !modelData.locked
                onToggled: products.toggleColumn(modelData.key, checked)
            }
            IconBtn { iconName: "arrowUp"; tip: "Nach oben (weiter links)"; enabled: index > 0; onClicked: products.moveColumn(modelData.key, -1) }
            IconBtn { iconName: "arrowDown"; tip: "Nach unten (weiter rechts)"; enabled: index < lv.count - 1
                      onClicked: products.moveColumn(modelData.key, 1) }
        }
    }
    footerLeft: Btn { text: "Standard wiederherstellen"; iconName: "undo"; flat: true; onClicked: products.resetColumns() }
    buttons: Btn { primary: true; text: "Fertig"; onClicked: dlg.close() }
}
