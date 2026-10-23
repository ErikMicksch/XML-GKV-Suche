import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Dialog-Rahmen: Titel mit Symbol, Inhalt (body), Knopfleiste (buttons). Esc schließt.
Popup {
    id: d
    property string title: ""
    property string iconName: ""
    property bool danger: false
    property int preferredWidth: 560
    property int maxHeight: 0
    default property alias body: bodyCol.data
    property alias buttons: buttonRow.data
    property alias footerLeft: footerLeftRow.data
    modal: true
    focus: true
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(parent ? parent.width - 48 : preferredWidth, preferredWidth)
    height: Math.min(parent ? parent.height - 48 : implicitHeight, implicitHeight, maxHeight > 0 ? maxHeight : implicitHeight)
    padding: 0
    closePolicy: Popup.CloseOnEscape
    Overlay.modal: Rectangle { color: "#73000000" }
    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 140 }
        NumberAnimation { property: "scale"; from: 0.96; to: 1; duration: 160; easing.type: Easing.OutCubic }
    }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 100 } }
    background: Rectangle {
        radius: 20
        color: theme.c.surface
        border.color: d.danger ? theme.c.danger : theme.c.line
        border.width: d.danger ? 2 : 1
    }
    contentItem: ColumnLayout {
        spacing: 0
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: 24
            Layout.bottomMargin: 12
            spacing: 12
            Rectangle {
                visible: d.iconName !== ""
                width: 44; height: 44; radius: 22
                color: d.danger ? Qt.rgba(0.7, 0.15, 0.12, 0.12) : theme.c.mint
                Icon { anchors.centerIn: parent; name: d.iconName; size: 24; color: d.danger ? theme.c.danger : theme.c.green }
            }
            AppText {
                Layout.fillWidth: true
                text: d.title
                rel: 1.45
                font.weight: Font.Bold
                color: d.danger ? theme.c.danger : theme.c.green
                wrapMode: Text.WordWrap
                elide: Text.ElideNone
            }
        }
        ColumnLayout {
            id: bodyCol
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.leftMargin: 24
            Layout.rightMargin: 24
            spacing: 10
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: 24
            Layout.topMargin: 18
            spacing: 10
            Row { id: footerLeftRow; spacing: 10 }
            Item { Layout.fillWidth: true }
            Row { id: buttonRow; spacing: 10; layoutDirection: Qt.LeftToRight }
        }
    }
}
