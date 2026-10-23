import QtQuick

// Deutlich sichtbarer Rahmen für die Bedienung mit der Tastatur (Tab) – nicht bei Mausklicks
Rectangle {
    property Item target: parent
    property real r: 12
    anchors.fill: parent
    anchors.margins: -4
    radius: r + 4
    color: "transparent"
    border.width: 2
    border.color: theme.c.focus
    visible: target && target.visualFocus === true
}
