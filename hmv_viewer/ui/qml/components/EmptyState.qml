import QtQuick
import QtQuick.Layouts

// Freundlicher Hinweis statt einer leeren Liste – mit Knopf für den nächsten Schritt
Item {
    id: e
    property string iconName: "search"
    property string title: ""
    property string text: ""
    property string actionText: ""
    signal action()
    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(parent.width - 40, 520)
        spacing: 12
        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            width: 96; height: 96; radius: 48
            color: theme.c.mint
            Icon { anchors.centerIn: parent; name: e.iconName; size: 48; color: theme.c.green }
        }
        AppText {
            Layout.fillWidth: true
            text: e.title
            rel: 1.3
            font.weight: Font.Bold
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            elide: Text.ElideNone
        }
        AppText {
            Layout.fillWidth: true
            visible: e.text !== ""
            text: e.text
            color: theme.c.muted
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            elide: Text.ElideNone
        }
        Btn {
            Layout.alignment: Qt.AlignHCenter
            visible: e.actionText !== ""
            text: e.actionText
            primary: true
            onClicked: e.action()
        }
    }
}
