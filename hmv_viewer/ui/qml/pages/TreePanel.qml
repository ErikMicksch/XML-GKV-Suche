import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// Produktgruppen, Favoriten und Listen als Baum
Card {
    id: tp
    signal picked()
    function focusFilter() { filter.forceActiveFocus() }

    ColumnLayout {
        anchors.fill: parent
        spacing: 10
        AppText { text: "Produktgruppen & Listen"; rel: 1.15; font.weight: Font.Bold }
        Field {
            id: filter
            Layout.fillWidth: true
            iconName: "filter"
            placeholderText: "Gruppe suchen, z. B. Gehhilfen oder 10.50"
            onTextEdited: filterTimer.restart()
            onCleared: tree.setFilter("")
            Keys.onDownPressed: lv.forceActiveFocus()
            Timer { id: filterTimer; interval: 250; onTriggered: tree.setFilter(filter.text) }
        }
        ListView {
            id: lv
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: tree.modelObj
            boundsBehavior: Flickable.StopAtBounds
            reuseItems: true
            Accessible.role: Accessible.Tree
            Accessible.name: "Produktgruppen und Listen"
            ScrollBar.vertical: ScrollBar { }
            Keys.onUpPressed: tree.move(-1)
            Keys.onDownPressed: tree.move(1)
            Keys.onLeftPressed: tree.expandCurrent(false)
            Keys.onRightPressed: tree.expandCurrent(true)
            Keys.onReturnPressed: tp.picked()
            Keys.onMenuPressed: tree.openMenu(tree.currentId)

            delegate: Rectangle {
                id: r
                width: lv.width - 10
                height: Math.max(36, theme.fontPt * 3)
                radius: 10
                color: model.selected ? theme.c.mint : (ma.containsMouse ? theme.c.hover : "transparent")
                border.width: drop.containsDrag ? 2 : (model.selected && lv.activeFocus ? 2 : 0)
                border.color: drop.containsDrag ? theme.c.green : theme.c.focus
                Accessible.role: Accessible.TreeItem
                Accessible.name: model.label + " " + model.countText
                Rectangle {
                    visible: model.selected
                    width: 4; height: parent.height - 12; radius: 2
                    color: theme.c.green
                    anchors.verticalCenter: parent.verticalCenter
                }
                MouseArea {
                    id: ma
                    anchors.fill: parent
                    hoverEnabled: true
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    onClicked: (m) => {
                        lv.forceActiveFocus()
                        if (m.button === Qt.RightButton) { tree.openMenu(model.nid); return }
                        tree.select(model.nid)
                        tp.picked()
                    }
                    onDoubleClicked: tree.toggle(model.nid)
                }
                RowLayout {
                    anchors.left: parent.left
                    anchors.leftMargin: 6 + model.depth * 18
                    anchors.right: parent.right
                    anchors.rightMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 6
                    AbstractButton {
                        implicitWidth: 26; implicitHeight: 26
                        enabled: model.hasChildren
                        focusPolicy: Qt.NoFocus
                        Accessible.name: model.expanded ? "Zuklappen" : "Aufklappen"
                        onClicked: tree.toggle(model.nid)
                        contentItem: Icon {
                            visible: model.hasChildren
                            name: model.expanded ? "chevronDown" : "chevronRight"
                            size: 16
                            color: theme.c.muted
                        }
                        background: Rectangle { radius: 13; color: parent.hovered ? theme.c.mintHover : "transparent" }
                    }
                    Icon {
                        visible: model.icon !== ""
                        name: model.icon
                        size: 18
                        color: theme.c[model.iconColor] || theme.c.muted
                    }
                    AppText {
                        Layout.fillWidth: true
                        text: model.label
                        font.weight: model.bold || model.selected ? Font.Bold : Font.Normal
                        color: model.labelColor === "green" ? theme.c.green : theme.c.text
                    }
                    AppText {
                        Layout.maximumWidth: r.width * 0.32
                        text: model.countText
                        rel: 0.88
                        color: theme.c.muted
                    }
                }
                DropArea {
                    id: drop
                    anchors.fill: parent
                    enabled: model.droppable
                    onDropped: tree.drop(model.nid)
                }
                HoverHandler { id: hov }
                ToolTip.visible: hov.hovered && model.tip !== ""
                ToolTip.text: model.tip
                ToolTip.delay: 900
            }
        }
        AppText {
            Layout.fillWidth: true
            text: "Rechte Maustaste: Gruppe merken, Listen anlegen · Produkte mit der Maus auf eine Liste ziehen"
            rel: 0.85
            color: theme.c.muted
            wrapMode: Text.WordWrap
            elide: Text.ElideNone
        }
    }
    Connections {
        target: tree
        function onScrollTo(i) { lv.positionViewAtIndex(i, ListView.Contain) }
    }
}
