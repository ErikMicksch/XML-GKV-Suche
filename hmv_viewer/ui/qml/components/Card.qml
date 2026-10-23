import QtQuick
import QtQuick.Effects

// Weiße Karte mit runden Ecken und weichem Schatten
Item {
    id: card
    default property alias content: inner.data
    property int padding: 16
    property bool shadow: GraphicsInfo.api !== GraphicsInfo.Software
    property color fill: theme.c.surface

    Rectangle {
        id: shape
        anchors.fill: parent
        radius: 18
        color: "black"
        visible: false
        layer.enabled: card.shadow
    }
    MultiEffect {
        visible: card.shadow
        anchors.fill: shape
        source: shape
        autoPaddingEnabled: true
        shadowEnabled: true
        shadowColor: theme.c.shadow
        shadowBlur: 0.7
        shadowVerticalOffset: 4
        shadowHorizontalOffset: 0
        opacity: 1.0
    }
    Rectangle {
        anchors.fill: parent
        radius: 18
        color: card.fill
        border.width: 1
        border.color: theme.c.line
    }
    Item {
        id: inner
        anchors.fill: parent
        clip: true
        anchors.margins: card.padding
    }
}
