import QtQuick
import QtQuick.Controls

// Eingabefeld mit optionalem Symbol links und „x“ zum Leeren
TextField {
    id: f
    property string iconName: ""
    property bool clearable: true
    property bool big: false
    signal cleared()
    font.pointSize: big ? theme.fontPt + 2 : theme.fontPt
    color: theme.c.text
    placeholderTextColor: theme.c.muted
    selectionColor: theme.c.select
    selectedTextColor: theme.c.text
    selectByMouse: true
    leftPadding: iconName ? (big ? 46 : 40) : 14
    rightPadding: clearBtn.visible ? 42 : 14
    implicitHeight: big ? Math.max(48, theme.fontPt * 4) : Math.max(42, theme.fontPt * 3.4)
    Accessible.name: placeholderText
    background: Rectangle {
        radius: f.big ? height / 2 : 12
        color: theme.c.surface
        border.width: f.activeFocus ? 2 : 1
        border.color: f.activeFocus ? theme.c.focus : theme.c.line
        Behavior on border.color { ColorAnimation { duration: 120 } }
    }
    Icon {
        visible: f.iconName !== ""
        name: f.iconName
        color: theme.c.muted
        size: f.big ? 22 : 18
        anchors.left: parent.left
        anchors.leftMargin: f.big ? 16 : 13
        anchors.verticalCenter: parent.verticalCenter
    }
    IconBtn {
        id: clearBtn
        visible: f.clearable && f.text.length > 0
        iconName: "close"
        iconColor: theme.c.muted
        size: 30
        tip: "Eingabe löschen"
        focusPolicy: Qt.NoFocus
        anchors.right: parent.right
        anchors.rightMargin: 6
        anchors.verticalCenter: parent.verticalCenter
        onClicked: { f.clear(); f.forceActiveFocus(); f.cleared() }
    }
}
