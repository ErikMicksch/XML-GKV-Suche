import QtQuick

// Formatierter Text (HTML aus Python) mit anklickbaren Links und Hand-Zeiger über Links
Text {
    id: t
    property real rel: 1.0
    color: theme.c.text
    linkColor: theme.c.green
    font.pointSize: theme.fontPt * rel
    font.family: "Segoe UI"
    textFormat: Text.RichText
    wrapMode: Text.WordWrap
    HoverHandler { cursorShape: t.hoveredLink ? Qt.PointingHandCursor : Qt.ArrowCursor }
}
