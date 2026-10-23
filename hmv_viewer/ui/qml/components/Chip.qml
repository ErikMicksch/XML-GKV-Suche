import QtQuick

// Kleines farbiges Etikett (Status, Änderungsart, Kategorie)
Rectangle {
    property alias text: label.text
    property color fg: theme.c.text
    radius: height / 2
    implicitHeight: label.implicitHeight + 6
    implicitWidth: label.implicitWidth + 20
    color: theme.c.mint
    AppText {
        id: label
        anchors.centerIn: parent
        rel: 0.85
        color: parent.fg
        font.weight: Font.DemiBold
    }
}
