import QtQuick
import QtQuick.Controls

// Runder Knopf nur mit Symbol – immer mit Tooltip und Namen für Bildschirmleser
Button {
    id: b
    property string iconName: ""
    property color iconColor: theme.c.green
    property int size: 38
    property string tip: ""
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    implicitWidth: size
    implicitHeight: size
    padding: 0
    Accessible.name: tip
    ToolTip.text: tip
    ToolTip.visible: hovered && tip !== ""
    ToolTip.delay: 500
    contentItem: Item {
        Icon {
            anchors.centerIn: parent
            name: b.iconName
            color: b.enabled ? b.iconColor : theme.c.disabledFg
            size: Math.round(b.size * 0.55)
        }
    }
    background: Rectangle {
        radius: width / 2
        color: b.checked ? theme.c.mint : b.down ? theme.c.mintHover : b.hovered ? theme.c.hover : "transparent"
        border.width: b.checked ? 1 : 0
        border.color: theme.c.green
        Behavior on color { ColorAnimation { duration: 120 } }
        FocusRing { target: b; r: parent.radius - 4 }
    }
}
