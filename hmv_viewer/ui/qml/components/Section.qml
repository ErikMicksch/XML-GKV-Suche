import QtQuick
import QtQuick.Controls

// Aufklappbarer Abschnitt in den Details (Einordnung, Merkmale, Listen)
Column {
    id: s
    property string title: ""
    property string html: ""
    property bool open: true
    signal linkActivated(string link)
    spacing: 4
    visible: html !== ""
    AbstractButton {
        id: head
        width: s.width
        height: Math.max(34, theme.fontPt * 2.8)
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        Accessible.name: s.title + (s.open ? " – aufgeklappt" : " – zugeklappt")
        onClicked: s.open = !s.open
        contentItem: Row {
            spacing: 6
            Icon {
                name: s.open ? "chevronDown" : "chevronRight"
                size: 18
                color: theme.c.green
                anchors.verticalCenter: parent.verticalCenter
            }
            AppText {
                text: s.title
                color: theme.c.green
                font.weight: Font.Bold
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        background: Rectangle {
            radius: 8
            color: head.hovered ? theme.c.hover : "transparent"
            FocusRing { target: head; r: 8 }
        }
    }
    HtmlText {
        visible: s.open
        width: s.width - 22
        x: 22
        text: s.html
        onLinkActivated: (link) => s.linkActivated(link)
    }
}
