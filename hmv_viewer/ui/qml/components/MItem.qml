import QtQuick
import QtQuick.Controls

// Menüeintrag mit Symbol
MenuItem {
    id: mi
    property string iconName: ""
    property bool dangerous: false
    hoverEnabled: true
    font.pointSize: theme.fontPt
    implicitHeight: Math.max(38, theme.fontPt * 3.1)
    implicitWidth: row.implicitWidth + 36 + (subMenu ? 24 : 0)
    contentItem: Item {
        Row {
            id: row
            anchors.verticalCenter: parent.verticalCenter
            spacing: 10
            Item {
                width: 18; height: 18
                anchors.verticalCenter: parent.verticalCenter
                Icon {
                    name: mi.iconName
                    visible: mi.iconName !== ""
                    size: 18
                    color: !mi.enabled ? theme.c.disabledFg : mi.dangerous ? theme.c.danger : theme.c.green
                }
            }
            AppText {
                text: mi.text
                color: !mi.enabled ? theme.c.disabledFg : mi.dangerous ? theme.c.danger
                       : mi.highlighted ? theme.c.green : theme.c.text
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }
    arrow: Icon {
        x: mi.width - width - 8
        y: (mi.height - height) / 2
        visible: mi.subMenu !== null
        name: "chevronRight"
        size: 16
        color: theme.c.muted
    }
    background: Rectangle { radius: 8; color: mi.highlighted ? theme.c.mint : "transparent" }
}
