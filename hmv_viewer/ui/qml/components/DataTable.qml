import QtQuick
import QtQuick.Controls

// Tabelle: Kopf bleibt oben stehen, Spaltenbreite mit der Maus ziehen (Doppelklick = passend), Klick auf den Kopf sortiert.
// Zeilen kommen aus einem Python-Modell mit den Rollen c (Spaltentexte), bg, selected, tips (+ star, katColor, icon …).
FocusScope {
    id: table
    property alias model: lv.model
    property var columns: []              // [{key, title, width, visible, sortable, sorted}]
    property int rowHeight: theme.rowH
    property bool resizable: true
    property bool draggable: false
    property Item dragProxy: null
    property string emptyText: ""
    property string iconColumn: ""      // Spalte mit Symbol vor dem Text
    property alias view: lv
    signal rowClicked(int row, bool ctrl, bool shift)
    signal rowDoubleClicked(int row)
    signal rowMenu(int row)
    signal starClicked(int row)
    signal sortRequested(string key)
    signal widthRequested(string key, int width)
    signal autoWidthRequested(string key)
    signal moveRequested(int delta, bool shift)
    signal selectAllRequested()
    signal copyRequested()
    signal reachedEnd()
    signal dropDone()
    property var dragStart: null          // function(row) -> Text für den Zieh-Hinweis

    // Spaltenreihenfolge nur neu aufbauen, wenn sich die sichtbaren Spalten ändern (nicht bei jeder Breitenänderung)
    readonly property string keySig: columns.filter(c => c.visible !== false).map(c => c.key).join(",")
    property var keyList: []
    onKeySigChanged: keyList = keySig ? keySig.split(",") : []
    Component.onCompleted: keyList = keySig ? keySig.split(",") : []
    readonly property var colOf: {
        var o = {}
        for (var i = 0; i < columns.length; i++) o[columns[i].key] = columns[i]
        return o
    }
    readonly property int totalWidth: {
        var w = 0
        for (var i = 0; i < keyList.length; i++) w += colOf[keyList[i]] ? colOf[keyList[i]].width : 100
        return w + 16
    }

    function ensureVisible(row) { if (row >= 0) lv.positionViewAtIndex(row, ListView.Contain) }

    Keys.onPressed: (event) => {
        var shift = (event.modifiers & Qt.ShiftModifier) !== 0
        var ctrl = (event.modifiers & Qt.ControlModifier) !== 0
        var page = Math.max(1, Math.floor(lv.height / table.rowHeight) - 1)
        if (event.key === Qt.Key_Down) table.moveRequested(1, shift)
        else if (event.key === Qt.Key_Up) table.moveRequested(-1, shift)
        else if (event.key === Qt.Key_PageDown) table.moveRequested(page, shift)
        else if (event.key === Qt.Key_PageUp) table.moveRequested(-page, shift)
        else if (event.key === Qt.Key_Home && ctrl) table.moveRequested(-1000000, shift)
        else if (event.key === Qt.Key_End && ctrl) table.moveRequested(1000000, shift)
        else if (event.key === Qt.Key_A && ctrl) table.selectAllRequested()
        else if (event.key === Qt.Key_C && ctrl) table.copyRequested()
        else if (event.key === Qt.Key_Menu || (event.key === Qt.Key_F10 && shift)) table.rowMenu(-1)
        else return
        event.accepted = true
    }

    Rectangle {
        anchors.fill: parent
        color: theme.c.surface
        radius: 10
        border.width: table.activeFocus ? 2 : 0
        border.color: theme.c.focus
    }

    ListView {
        id: lv
        anchors.fill: parent
        anchors.margins: 2
        clip: true
        focus: true
        contentWidth: Math.max(width, table.totalWidth)
        flickableDirection: Flickable.AutoFlickIfNeeded
        boundsBehavior: Flickable.StopAtBounds
        headerPositioning: ListView.OverlayHeader
        reuseItems: true
        cacheBuffer: 400
        onAtYEndChanged: if (atYEnd && count > 0) table.reachedEnd()
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded; minimumSize: 0.06 }
        ScrollBar.horizontal: ScrollBar { policy: ScrollBar.AsNeeded }

        header: Rectangle {
            z: 3
            width: lv.contentWidth
            height: Math.max(40, theme.fontPt * 3.4)
            color: theme.c.surface
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 2; color: theme.c.line }
            Row {
                height: parent.height
                Repeater {
                    model: table.keyList
                    delegate: Item {
                        id: hcell
                        required property string modelData
                        readonly property var col: table.colOf[modelData] || ({})
                        width: col.width || 100
                        height: parent.height
                        clip: true
                        AbstractButton {
                            id: hbtn
                            anchors.fill: parent
                            anchors.rightMargin: 6
                            enabled: hcell.col.sortable === true
                            hoverEnabled: true
                            focusPolicy: Qt.NoFocus
                            Accessible.name: "Sortieren nach " + hcell.col.title
                            onClicked: table.sortRequested(hcell.modelData)
                            contentItem: Row {
                                spacing: 4
                                leftPadding: 10
                                Icon {
                                    visible: hcell.modelData === "fav" || hcell.modelData === "kat"
                                    name: hcell.modelData === "fav" ? "starFilled" : "tag"
                                    size: 16; color: hcell.modelData === "fav" ? theme.c.gold : theme.c.muted
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                AppText {
                                    visible: hcell.modelData !== "fav" && hcell.modelData !== "kat"
                                    text: hcell.col.title || ""
                                    width: Math.min(implicitWidth, hcell.width - (hcell.col.sortable ? 34 : 16))
                                    color: hbtn.hovered ? theme.c.green : theme.c.muted
                                    font.weight: Font.Bold
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                Icon {
                                    visible: (hcell.col.sorted || "") !== ""
                                    name: hcell.col.sorted === "desc" ? "arrowDown" : "arrowUp"
                                    size: 14; color: theme.c.green
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                            background: Rectangle { color: hbtn.hovered ? theme.c.hover : "transparent"; radius: 6 }
                        }
                        // Spaltenrand: ziehen = Breite ändern, Doppelklick = passende Breite
                        MouseArea {
                            visible: table.resizable
                            width: 10
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            cursorShape: Qt.SplitHCursor
                            hoverEnabled: true
                            property real startX: 0
                            property int startW: 0
                            onPressed: (m) => { startX = mapToItem(lv, m.x, 0).x; startW = hcell.width }
                            onPositionChanged: (m) => { if (pressed) table.widthRequested(hcell.modelData, startW + mapToItem(lv, m.x, 0).x - startX) }
                            onDoubleClicked: table.autoWidthRequested(hcell.modelData)
                            Rectangle { anchors.horizontalCenter: parent.horizontalCenter; width: 2; height: parent.height * 0.5
                                        anchors.verticalCenter: parent.verticalCenter; radius: 1
                                        color: parent.containsMouse || parent.pressed ? theme.c.green : theme.c.line }
                        }
                    }
                }
            }
        }

        delegate: Rectangle {
            id: row
            width: lv.contentWidth
            height: table.rowHeight
            readonly property var cells: model.c || ({})
            readonly property var tips: model.tips || ({})
            readonly property string katColor: model.katColor || ""
            readonly property string iconName: model.icon || ""
            readonly property color iconColor: model.iconColor || theme.c.green
            color: model.selected ? theme.c.select : (model.bg ? model.bg : (index % 2 ? theme.c.alt : theme.c.surface))
            Accessible.role: Accessible.Row
            Accessible.name: (cells.nummer || "") + " " + (cells.bezeichnung || cells.name || "")
            Rectangle {   // Auswahl: grüner Balken links
                visible: model.selected === true
                width: 4; height: parent.height
                color: theme.c.green
            }
            Rectangle {
                anchors.fill: parent
                color: theme.c.hover
                opacity: ma.containsMouse && !model.selected ? 0.7 : 0
                Behavior on opacity { NumberAnimation { duration: 90 } }
            }
            Row {
                height: parent.height
                Repeater {
                    model: table.keyList
                    delegate: Item {
                        id: cell
                        required property string modelData
                        width: table.colOf[modelData] ? table.colOf[modelData].width : 100
                        height: row.height
                        clip: true
                        readonly property string tip: row.tips[modelData] || ""
                        Icon {   // Favoriten-Stern
                            visible: cell.modelData === "fav"
                            anchors.centerIn: parent
                            name: row.cells.fav === "★" ? "starFilled" : "star"
                            size: 20
                            color: row.cells.fav ? theme.c.gold : theme.c.scroll
                            opacity: row.cells.fav || ma.containsMouse ? 1 : 0.55
                        }
                        Rectangle {   // Farbkategorie
                            visible: cell.modelData === "kat" && row.katColor !== ""
                            anchors.centerIn: parent
                            width: 18; height: 18; radius: 5
                            color: visible ? row.katColor : "transparent"
                            border.color: Qt.rgba(0, 0, 0, 0.2)
                        }
                        Icon {   // Symbol in der ersten Spalte (z. B. „Änderungen anderer“)
                            visible: cell.modelData === table.iconColumn && row.iconName !== ""
                            name: row.iconName
                            color: row.iconColor
                            size: 18
                            x: 10
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        AppText {
                            visible: cell.modelData !== "fav" && cell.modelData !== "kat"
                            anchors.fill: parent
                            leftPadding: cell.modelData === table.iconColumn && row.iconName !== "" ? 36 : 10
                            rightPadding: 8
                            text: row.cells[cell.modelData] || ""
                            color: cell.modelData === "notiz" ? theme.c.muted : theme.c.text
                            font.weight: cell.modelData === "nummer" ? Font.DemiBold : Font.Normal
                        }
                        HoverHandler { id: hh; enabled: cell.tip !== "" }
                        ToolTip.visible: hh.hovered && cell.tip !== ""
                        ToolTip.text: cell.tip
                        ToolTip.delay: 700
                    }
                }
            }
            MouseArea {
                id: ma
                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.LeftButton | Qt.RightButton
                onClicked: (m) => {
                    table.forceActiveFocus()
                    if (m.button === Qt.RightButton) { table.rowMenu(index); return }
                    var x = 0
                    for (var i = 0; i < table.keyList.length; i++) {
                        var w = table.colOf[table.keyList[i]].width
                        if (m.x >= x && m.x < x + w && table.keyList[i] === "fav") { table.starClicked(index); return }
                        x += w
                    }
                    table.rowClicked(index, (m.modifiers & Qt.ControlModifier) !== 0, (m.modifiers & Qt.ShiftModifier) !== 0)
                }
                onDoubleClicked: table.rowDoubleClicked(index)
            }
            DragHandler {
                id: dh
                target: null
                enabled: table.draggable && table.dragProxy !== null
                onActiveChanged: {
                    var p = table.dragProxy
                    if (active) {
                        p.text = table.dragStart ? table.dragStart(index) : ""
                        p.Drag.active = true
                    } else {
                        p.Drag.drop()
                        p.Drag.active = false
                        table.dropDone()
                    }
                    p.visible = active
                }
                onCentroidChanged: {
                    if (!active) return
                    var pt = row.mapToItem(table.dragProxy.parent, centroid.position.x, centroid.position.y)
                    table.dragProxy.x = pt.x + 14
                    table.dragProxy.y = pt.y + 10
                }
            }
        }
    }
    AppText {
        visible: lv.count === 0 && table.emptyText !== ""
        anchors.centerIn: parent
        text: table.emptyText
        color: theme.c.muted
    }
}
