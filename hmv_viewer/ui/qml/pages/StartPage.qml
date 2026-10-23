import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// Startseite: Begrüßung, Kacheln (anklickbar), Änderungen je Version, zuletzt angesehen, geänderte Listen
Item {
    id: page
    property var ui
    readonly property var d: dash.data

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 22
        spacing: 16

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            AppText { text: page.d.greeting || ""; rel: 1.75; font.weight: Font.Bold; elide: Text.ElideNone }
            Flow {
                Layout.fillWidth: true
                layoutDirection: Qt.RightToLeft
                spacing: 10
                Btn { iconName: "bell"; text: "Was ist neu?"; onClicked: maint.whatsNew() }
                Btn { iconName: "starFilled"; text: "Meine Favoriten"; onClicked: products.showFavorites() }
                Btn { iconName: "paste"; text: "Nummernliste einfügen"; onClicked: maint.openPaste() }
                Btn { iconName: "zap"; text: "Schnellzugriff"; tip: "Strg+K"; onClicked: maint.openPalette() }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 16
            Repeater {
                model: page.d.tiles || []
                delegate: Card {
                    id: tile
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.max(170, theme.fontPt * 15)
                    padding: 18
                    fill: tma.containsMouse ? theme.c.hover : theme.c.surface
                    Accessible.role: Accessible.Button
                    Accessible.name: modelData.title + ": " + modelData.value
                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 4
                        RowLayout {
                            spacing: 8
                            Icon { name: modelData.icon; size: 22; color: modelData.icon === "starFilled" ? theme.c.gold : theme.c.green }
                            AppText { text: modelData.title; color: theme.c.muted; Layout.fillWidth: true; wrapMode: Text.WordWrap; maximumLineCount: 2 }
                            Icon { name: "chevronRight"; size: 18; color: theme.c.muted; opacity: tma.containsMouse ? 1 : 0.4 }
                        }
                        AppText { text: modelData.value; rel: 2.0; font.weight: Font.Bold; color: theme.c.green }
                        AppText { Layout.fillWidth: true; text: modelData.sub; color: theme.c.muted; rel: 0.9
                                  wrapMode: Text.WordWrap; maximumLineCount: 2 }
                    }
                    MouseArea { id: tma; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: core.run(modelData.aid) }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 16
            Card {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 3
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 10
                    AppText { text: "Änderungen je Version"; font.weight: Font.Bold; rel: 1.1 }
                    AppText { text: "Balken anklicken = Änderungen dieser Version ansehen"; color: theme.c.muted; rel: 0.85 }
                    Item {
                        id: chart
                        objectName: "chart"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        readonly property var bars: page.d.bars || []
                        AppText {
                            anchors.centerIn: parent
                            visible: chart.bars.length === 0
                            text: "Noch keine Änderungen – ab dem zweiten Import sichtbar."
                            color: theme.c.muted
                        }
                        Row {
                            id: barRow
                            objectName: "barRow"
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.bottom: labels.top
                            anchors.bottomMargin: 6
                            spacing: 0
                            Repeater {
                                model: chart.bars
                                delegate: Item {
                                    id: bar
                                    width: barRow.width / Math.max(1, chart.bars.length)
                                    height: barRow.height
                                    readonly property real scaleY: (height - 26) / Math.max(1, page.d.maxBar || 1)
                                    AppText { anchors.horizontalCenter: parent.horizontalCenter; y: parent.height - stack.height - 24
                                              text: modelData.total; rel: 0.85; color: theme.c.muted }
                                    Column {
                                        id: stack
                                        anchors.bottom: parent.bottom
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        width: Math.min(56, bar.width * 0.55)
                                        Repeater {
                                            model: modelData.segments.slice().reverse()
                                            delegate: Rectangle {
                                                width: stack.width
                                                height: modelData.value * bar.scaleY
                                                color: Qt.darker(modelData.color, bma.containsMouse ? 1.3 : 1.15)
                                                radius: 3
                                                Behavior on height { NumberAnimation { duration: 400; easing.type: Easing.OutCubic } }
                                            }
                                        }
                                    }
                                    MouseArea {
                                        id: bma
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: core.run(modelData.aid)
                                    }
                                    ToolTip.visible: bma.containsMouse
                                    ToolTip.text: modelData.label + ": " + modelData.segments.map(s => s.label + " " + s.value).join(" · ")
                                }
                            }
                        }
                        Row {
                            id: labels
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: legendRow.top
                            anchors.bottomMargin: 8
                            Repeater {
                                model: chart.bars
                                AppText { width: barRow.width / Math.max(1, chart.bars.length); horizontalAlignment: Text.AlignHCenter
                                          text: modelData.label; color: theme.c.muted }
                            }
                        }
                        Flow {
                            id: legendRow
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            spacing: 14
                            visible: chart.bars.length > 0
                            Repeater {
                                model: page.d.legend || []
                                Row {
                                    spacing: 6
                                    Rectangle { width: 14; height: 14; radius: 3; color: Qt.darker(modelData.color, 1.15)
                                                anchors.verticalCenter: parent.verticalCenter }
                                    AppText { text: modelData.label; rel: 0.9; color: theme.c.muted }
                                }
                            }
                        }
                    }
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 2
                spacing: 16
                ClickCard { title: "Zuletzt angesehen"; model: dash.recentModel; emptyText: "Noch keine Produkte angesehen." }
                ClickCard { title: "Zuletzt geänderte gemeinsame Listen"; model: dash.listsModel; emptyText: "Noch keine gemeinsamen Listen." }
            }
        }
    }

    component ClickCard: Card {
        id: cc
        property string title: ""
        property alias model: cl.model
        property string emptyText: ""
        Layout.fillWidth: true
        Layout.fillHeight: true
        ColumnLayout {
            anchors.fill: parent
            spacing: 8
            AppText { text: cc.title; font.weight: Font.Bold; rel: 1.1 }
            ListView {
                id: cl
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 2
                ScrollBar.vertical: ScrollBar { }
                delegate: ItemDelegate {
                    width: cl.width
                    hoverEnabled: true
                    Accessible.name: model.text
                    onClicked: core.run(model.aid)
                    contentItem: RowLayout {
                        spacing: 10
                        Icon { name: model.icon; size: 18; color: model.icon === "bell" ? theme.c.gold : theme.c.green }
                        AppText { text: model.text; Layout.fillWidth: true }
                        Icon { name: "chevronRight"; size: 16; color: theme.c.muted }
                    }
                    background: Rectangle { radius: 10; color: parent.hovered ? theme.c.hover : "transparent" }
                }
                AppText { anchors.centerIn: parent; visible: cl.count === 0; text: cc.emptyText; color: theme.c.muted }
            }
        }
    }
}
