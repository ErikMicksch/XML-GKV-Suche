import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// Schnellzugriff (Strg+K): tippen, mit Pfeiltasten wählen, Enter
AppDialog {
    id: dlg
    property var items: []
    title: "Schnellzugriff"
    iconName: "zap"
    preferredWidth: 720
    maxHeight: 720

    function openFresh() { field.text = ""; refresh(); open(); field.forceActiveFocus() }
    function refresh() { items = quick.items(field.text); lv.currentIndex = items.length ? 0 : -1 }
    function run(i) { if (i < 0 || i >= items.length) return; var aid = items[i].aid; close(); core.run(aid) }

    Field {
        id: field
        Layout.fillWidth: true
        big: true
        iconName: "search"
        placeholderText: "Produkt, Gruppe, Liste oder Funktion …"
        onTextEdited: timer.restart()
        Keys.onDownPressed: lv.incrementCurrentIndex()
        Keys.onUpPressed: lv.decrementCurrentIndex()
        Keys.onReturnPressed: dlg.run(lv.currentIndex)
        Timer { id: timer; interval: 180; onTriggered: dlg.refresh() }
    }
    ListView {
        id: lv
        Layout.fillWidth: true
        Layout.preferredHeight: 440
        clip: true
        model: dlg.items
        highlightMoveDuration: 0
        ScrollBar.vertical: ScrollBar { }
        delegate: ItemDelegate {
            width: lv.width
            highlighted: ListView.isCurrentItem
            hoverEnabled: true
            onClicked: dlg.run(index)
            contentItem: RowLayout {
                spacing: 12
                Icon { name: modelData.icon; size: 20; color: modelData.icon.indexOf("star") === 0 ? theme.c.gold : theme.c.green }
                AppText { text: modelData.text; Layout.fillWidth: true }
                AppText { text: modelData.sub; color: theme.c.muted; rel: 0.85 }
            }
            background: Rectangle { radius: 10; color: parent.highlighted ? theme.c.mint : parent.hovered ? theme.c.hover : "transparent" }
        }
    }
    AppText { text: "↑ ↓ wählen · Enter öffnen · Esc schließen"; color: theme.c.muted; rel: 0.85 }
}
