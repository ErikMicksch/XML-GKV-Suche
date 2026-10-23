import QtQuick
import QtQuick.Controls

// Großes Häkchen-Feld (leicht zu treffen)
CheckBox {
    id: c
    hoverEnabled: true
    font.pointSize: theme.fontPt
    spacing: 10
    Accessible.name: text
    indicator: Rectangle {
        implicitWidth: 24
        implicitHeight: 24
        x: c.leftPadding
        y: (c.height - height) / 2
        radius: 6
        color: c.checked ? theme.c.green : theme.c.surface
        border.width: 2
        border.color: c.checked ? theme.c.green : (c.hovered ? theme.c.green : theme.c.scroll)
        Icon { anchors.centerIn: parent; name: "check"; color: theme.c.onAccent; size: 16; visible: c.checked }
        FocusRing { target: c; r: 6 }
    }
    contentItem: AppText {
        text: c.text
        leftPadding: c.indicator.width + c.spacing
        wrapMode: Text.WordWrap
        elide: Text.ElideNone
    }
}
