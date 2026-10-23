import QtQuick

// Text in der Schriftgröße und Farbe der gewählten Farbwelt
Text {
    property real rel: 1.0
    color: theme.c.text
    font.pointSize: Math.max(7, theme.fontPt * rel)
    font.family: "Segoe UI"
    textFormat: Text.PlainText
    elide: Text.ElideRight
    verticalAlignment: Text.AlignVCenter
}
