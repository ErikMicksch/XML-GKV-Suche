import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// Produkte: Baum | Liste | Details. Auf schmalen Bildschirmen klappt der Baum als Leiste von links heraus.
Item {
    id: page
    property var ui
    readonly property bool narrow: ui ? ui.narrow : false

    function focusTable() { list.focusTable() }
    function focusPart(what) {
        if (what === "note") detailPanel.focusNote()
        else if (what === "tree") { if (narrow) { drawer.open(); drawerTree.focusFilter() } else treePanel.focusFilter() }
        else if (what === "hersteller") list.focusHersteller()
        else list.focusTable()
    }

    SplitView {
        anchors.fill: parent
        anchors.margins: 14
        orientation: Qt.Horizontal
        handle: Item {
            implicitWidth: 14
            Rectangle {
                anchors.centerIn: parent
                width: 4; height: 56; radius: 2
                color: SplitHandle.hovered || SplitHandle.pressed ? theme.c.green : theme.c.line
            }
        }
        TreePanel {
            id: treePanel
            visible: !page.narrow
            SplitView.preferredWidth: 300
            SplitView.minimumWidth: 240
        }
        ProductList {
            id: list
            objectName: "productList"
            ui: page.ui
            showTreeButton: page.narrow
            SplitView.fillWidth: true
            SplitView.minimumWidth: 480
            onTreeButtonClicked: drawer.open()
        }
        DetailPanel {
            id: detailPanel
            objectName: "detailPanel"
            SplitView.preferredWidth: page.narrow ? 400 : 420
            SplitView.minimumWidth: 340
        }
    }

    Drawer {
        id: drawer
        edge: Qt.LeftEdge
        width: Math.min(400, page.width * 0.8)
        height: page.ui ? page.ui.height : page.height
        background: Rectangle { color: theme.c.bg }
        TreePanel {
            id: drawerTree
            anchors.fill: parent
            anchors.margins: 12
            onPicked: drawer.close()
        }
    }
}
