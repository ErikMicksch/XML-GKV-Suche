import QtQuick

// SVG-Symbol aus hmv_qml/icons.py in beliebiger Farbe (scharf auch bei 150 % / 200 % Skalierung)
Image {
    property string name: ""
    property color color: theme.c.text
    property int size: 20
    width: size
    height: size
    sourceSize: Qt.size(size * 2, size * 2)
    source: name ? "image://icon/" + name + "/" + String(color).replace("#", "") : ""
    fillMode: Image.PreserveAspectFit
    smooth: true
    mipmap: true
}
