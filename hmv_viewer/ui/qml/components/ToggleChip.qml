import QtQuick
import QtQuick.Controls

// Ein-/Aus-Schalter als Pille (z. B. „Suchen in: Merkmale“) – an: grün umrandet mit Häkchen
AbstractButton {
    id: t
    checkable: true
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    property string tip: ""
    implicitHeight: Math.max(36, theme.fontPt * 3)
    implicitWidth: row.implicitWidth + 28
    Accessible.name: text
    Accessible.checkable: true
    ToolTip.text: tip
    ToolTip.visible: hovered && tip !== ""
    ToolTip.delay: 500
    contentItem: Item {
        Row {
            id: row
            anchors.centerIn: parent
            spacing: 6
            Icon { name: "check"; size: 16; color: theme.c.green; visible: t.checked; anchors.verticalCenter: parent.verticalCenter }
            AppText {
                text: t.text
                color: t.checked ? theme.c.green : theme.c.muted
                font.weight: Font.DemiBold
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }
    background: Rectangle {
        radius: height / 2
        color: t.checked ? theme.c.mint : (t.hovered ? theme.c.hover : theme.c.surface)
        border.width: t.checked ? 2 : 1
        border.color: t.checked ? theme.c.green : theme.c.line
        Behavior on color { ColorAnimation { duration: 120 } }
        FocusRing { target: t; r: parent.radius - 4 }
    }
}
