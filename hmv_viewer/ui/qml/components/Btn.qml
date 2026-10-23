import QtQuick
import QtQuick.Controls

// Schaltfläche mit Symbol und Text. primary = grün gefüllt, danger = rot, flat = ohne Fläche, onHeader = im grünen Kopf
Button {
    id: b
    property string iconName: ""
    property bool primary: false
    property bool danger: false
    property bool onHeader: false
    property bool highlight: false        // gelb (Hilfe)
    property string tip: ""
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    font.pointSize: theme.fontPt
    implicitHeight: Math.max(40, theme.fontPt * 3.3)
    leftPadding: text ? 16 : 10
    rightPadding: text ? 18 : 10
    Accessible.name: text || tip
    ToolTip.text: tip
    ToolTip.visible: hovered && tip !== ""
    ToolTip.delay: 500

    readonly property color bgColor: !enabled ? theme.c.disabledBg
                                     : highlight ? theme.c.gold
                                     : danger ? theme.c.danger
                                     : primary ? (onHeader ? theme.c.surface : theme.c.green)
                                     : onHeader ? theme.c.headerBtn
                                     : flat ? "transparent" : theme.c.mint
    readonly property color fgColor: !enabled ? theme.c.disabledFg
                                     : highlight ? theme.c.goldText
                                     : danger ? theme.c.onDanger
                                     : primary ? (onHeader ? theme.c.green : theme.c.onAccent)
                                     : onHeader ? theme.c.headerFg : theme.c.green

    contentItem: Item {
        implicitWidth: row.implicitWidth
        implicitHeight: row.implicitHeight
        Row {
            id: row
            anchors.centerIn: parent
            spacing: 8
            Icon {
                visible: b.iconName !== ""
                name: b.iconName
                color: b.fgColor
                size: Math.round(theme.fontPt * 1.6)
                anchors.verticalCenter: parent.verticalCenter
            }
            AppText {
                visible: b.text !== ""
                text: b.text
                color: b.fgColor
                font.weight: Font.DemiBold
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }
    background: Rectangle {
        radius: b.onHeader ? height / 2 : 12
        color: b.down ? Qt.darker(b.bgColor, 1.12) : b.hovered ? (b.flat && !b.onHeader ? theme.c.hover
                                                                   : b.onHeader && !b.primary && !b.highlight ? theme.c.headerBtnHover
                                                                   : Qt.darker(b.bgColor, 1.06)) : b.bgColor
        border.width: b.onHeader && !b.primary && !b.highlight ? 1 : 0
        border.color: theme.c.headerBtnBorder
        Behavior on color { ColorAnimation { duration: 120 } }
        FocusRing { target: b; r: parent.radius - 4 }
    }
}
