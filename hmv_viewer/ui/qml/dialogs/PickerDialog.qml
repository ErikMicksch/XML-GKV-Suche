import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// Produkt(e) zum Vergleichen wählen: leer = gleiche Produktart, sonst Suche; anklicken = an/aus
AppDialog {
    id: dlg
    title: "Vergleichen mit …"
    iconName: "compare"
    preferredWidth: 760
    maxHeight: 820

    function openFresh() { field.text = ""; open(); field.forceActiveFocus() }

    AppText { Layout.fillWidth: true; text: picker.label; font.weight: Font.DemiBold; wrapMode: Text.WordWrap; elide: Text.ElideNone }
    Field {
        id: field
        Layout.fillWidth: true
        iconName: "search"
        placeholderText: "Bezeichnung, Hersteller oder Nummer suchen … (leer = gleiche Produktart)"
        onTextEdited: timer.restart()
        onCleared: picker.search("")
        Timer { id: timer; interval: 220; onTriggered: picker.search(field.text) }
    }
    AppText { text: picker.info + " · bis zu " + picker.maxSel + " Produkt(e) anklicken"; color: theme.c.muted }
    ListView {
        id: lv
        Layout.fillWidth: true
        Layout.preferredHeight: 420
        clip: true
        model: picker.modelObj
        ScrollBar.vertical: ScrollBar { }
        delegate: ItemDelegate {
            width: lv.width
            hoverEnabled: true
            onClicked: picker.toggle(index)
            onDoubleClicked: { if (!model.selected) picker.toggle(index); okBtn.clicked() }
            contentItem: RowLayout {
                spacing: 10
                Rectangle {
                    width: 24; height: 24; radius: 6
                    color: model.selected ? theme.c.green : theme.c.surface
                    border.width: 2
                    border.color: model.selected ? theme.c.green : theme.c.scroll
                    Icon { anchors.centerIn: parent; visible: model.selected; name: "check"; size: 16; color: theme.c.onAccent }
                }
                AppText { text: model.text; Layout.fillWidth: true }
            }
            background: Rectangle { radius: 8; color: model.selected ? theme.c.mint : parent.hovered ? theme.c.hover : "transparent" }
        }
    }
    buttons: [
        Btn { text: "Abbrechen"; onClicked: dlg.close() },
        Btn { id: okBtn; primary: true; iconName: "compare"
              text: picker.selectedCount ? "Vergleichen (" + picker.selectedCount + ")" : "Vergleichen"
              enabled: picker.selectedCount > 0
              onClicked: { dlg.close(); picker.accept() } }
    ]
}
