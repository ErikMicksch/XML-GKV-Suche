import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// Vergleich: Eigenschaften links, je Produkt eine Spalte; Unterschiede farbig
AppDialog {
    id: dlg
    title: "Vergleich von " + compare.headers.length + " Produkten"
    iconName: "compare"
    preferredWidth: Math.min(1500, 300 + 300 * compare.headers.length)
    maxHeight: 900
    readonly property int labelW: 220
    readonly property int colW: Math.max(220, Math.floor((width - 48 - labelW - 20) / Math.max(1, compare.headers.length)))

    RowLayout {
        Layout.fillWidth: true
        Check { text: "Nur Unterschiede anzeigen"; checked: compare.onlyDiff; onToggled: compare.setOnlyDiff(checked) }
        Item { Layout.fillWidth: true }
        AppText { text: compare.legend; color: theme.c.muted }
    }
    Rectangle {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.preferredHeight: 560
        radius: 12
        color: theme.c.surface
        border.color: theme.c.line
        clip: true
        ListView {
            id: lv
            anchors.fill: parent
            anchors.margins: 2
            clip: true
            model: compare.rows
            contentWidth: dlg.labelW + dlg.colW * compare.headers.length
            flickableDirection: Flickable.AutoFlickIfNeeded
            headerPositioning: ListView.OverlayHeader
            ScrollBar.vertical: ScrollBar { }
            ScrollBar.horizontal: ScrollBar { }
            header: Rectangle {
                z: 3
                width: lv.contentWidth
                height: 44
                color: theme.c.surface
                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 2; color: theme.c.line }
                Row {
                    height: parent.height
                    AppText { width: dlg.labelW; leftPadding: 12; text: "Eigenschaft"; color: theme.c.muted; font.weight: Font.Bold; height: parent.height }
                    Repeater {
                        model: compare.headers
                        AppText { width: dlg.colW; leftPadding: 12; text: modelData; font.weight: Font.Bold; color: theme.c.green; height: parent.height }
                    }
                }
            }
            delegate: Rectangle {
                width: lv.contentWidth
                height: modelData.section ? 40 : Math.max(36, cells.implicitHeight + 14)
                color: modelData.section ? theme.c.mint : (modelData.differs ? theme.c.tagGeaendert : (index % 2 ? theme.c.alt : theme.c.surface))
                AppText {
                    visible: modelData.section !== ""
                    anchors.verticalCenter: parent.verticalCenter
                    leftPadding: 12
                    text: modelData.section
                    font.weight: Font.Bold
                    color: theme.c.green
                }
                Row {
                    id: cells
                    visible: modelData.section === ""
                    y: 7
                    AppText { width: dlg.labelW; leftPadding: 12; rightPadding: 8; text: modelData.label; font.weight: Font.DemiBold
                              color: theme.c.muted; wrapMode: Text.WordWrap; elide: Text.ElideNone }
                    Repeater {
                        model: modelData.values
                        AppText { width: dlg.colW; leftPadding: 12; rightPadding: 8; text: modelData; wrapMode: Text.WordWrap
                                  elide: Text.ElideNone }
                    }
                }
            }
        }
    }
    footerLeft: [
        Btn { iconName: "plus"; text: "Weiteres Produkt …"; enabled: compare.canAdd; onClicked: compare.add() },
        Btn { iconName: "copy"; text: "Als Tabelle kopieren"; onClicked: compare.copy() }
    ]
    buttons: Btn { primary: true; text: "Schließen"; onClicked: dlg.close() }
}
