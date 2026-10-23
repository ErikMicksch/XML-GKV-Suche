import QtQuick
import QtQuick.Controls

// Menü im Stil der Oberfläche
Menu {
    padding: 6
    implicitWidth: Math.max(280, contentWidth + leftPadding + rightPadding)
    delegate: MItem { }
    background: Rectangle {
        radius: 12
        color: theme.c.surface
        border.color: theme.c.line
        implicitWidth: 280
    }
    onAboutToShow: {
        var w = 280
        for (var i = 0; i < count; i++) if (itemAt(i)) w = Math.max(w, itemAt(i).implicitWidth)
        implicitWidth = w + leftPadding + rightPadding
    }
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 110 } }
}
