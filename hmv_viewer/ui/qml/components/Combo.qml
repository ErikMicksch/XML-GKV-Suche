import QtQuick
import QtQuick.Controls

// Auswahlliste. model: [{value, text, color?}], value: gewählter Wert; picked(value) bei Auswahl durch den Benutzer
ComboBox {
    id: cb
    property var value
    property string label: ""
    signal picked(var value)
    textRole: "text"
    valueRole: "value"
    hoverEnabled: true
    font.pointSize: theme.fontPt
    implicitHeight: Math.max(42, theme.fontPt * 3.4)
    implicitWidth: 200
    Accessible.name: label || displayText

    function sync() {
        var i = indexOfValue(value)
        currentIndex = i < 0 ? 0 : i
    }
    onValueChanged: sync()
    onModelChanged: sync()
    onCountChanged: sync()
    Component.onCompleted: sync()
    onActivated: picked(currentValue)

    readonly property var current: model && currentIndex >= 0 && model[currentIndex] !== undefined ? model[currentIndex] : null

    contentItem: Item {
        Row {
            anchors.left: parent.left
            anchors.leftMargin: 14
            anchors.right: parent.right
            anchors.rightMargin: 36
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8
            Rectangle {
                visible: cb.current !== null && cb.current.color !== undefined && cb.current.color !== ""
                width: 16; height: 16; radius: 4
                color: visible ? cb.current.color : "transparent"
                anchors.verticalCenter: parent.verticalCenter
            }
            AppText {
                text: cb.displayText
                width: parent.width - 24
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }
    indicator: Icon {
        name: "chevronDown"
        color: theme.c.muted
        size: 18
        x: cb.width - width - 12
        anchors.verticalCenter: parent.verticalCenter
    }
    background: Rectangle {
        radius: 12
        color: cb.hovered ? theme.c.hover : theme.c.surface
        border.width: cb.activeFocus ? 2 : 1
        border.color: cb.activeFocus ? theme.c.focus : theme.c.line
    }
    delegate: ItemDelegate {
        id: d
        width: ListView.view ? ListView.view.width : cb.width
        highlighted: cb.highlightedIndex === index
        hoverEnabled: true
        contentItem: Row {
            spacing: 8
            Rectangle {
                visible: modelData.color !== undefined && modelData.color !== ""
                width: 16; height: 16; radius: 4
                color: visible ? modelData.color : "transparent"
                anchors.verticalCenter: parent.verticalCenter
            }
            AppText {
                text: modelData.text
                color: d.highlighted ? theme.c.green : theme.c.text
                font.weight: cb.currentIndex === index ? Font.Bold : Font.Normal
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        background: Rectangle { radius: 8; color: d.highlighted ? theme.c.mint : "transparent" }
    }
    popup: Popup {
        y: cb.height + 4
        width: Math.max(cb.width, 240)
        implicitHeight: Math.min(contentItem.implicitHeight + 12, 440)
        padding: 6
        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: cb.popup.visible ? cb.delegateModel : null
            currentIndex: cb.highlightedIndex
            ScrollBar.vertical: ScrollBar { }
        }
        background: Rectangle { radius: 12; color: theme.c.surface; border.color: theme.c.line }
    }
}
