import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// Produktliste: Suchbereiche, „Mehr Filter“, Tabelle oder Karten, leere Ansicht mit nächstem Schritt
Card {
    id: pl
    property var ui
    property bool showTreeButton: false
    signal treeButtonClicked()
    function focusTable() { if (products.state.viewMode === "karten") cards.forceActiveFocus(); else table.forceActiveFocus() }
    function focusHersteller() { products.set("moreFilters", true); Qt.callLater(herField.forceActiveFocus) }
    readonly property var st: products.state

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Btn {
                visible: pl.showTreeButton
                iconName: "list"
                text: "Produktgruppen"
                tip: "Produktgruppen, Favoriten und Listen einblenden (Strg+G)"
                onClicked: pl.treeButtonClicked()
            }
            AppText {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: products.title
                rel: 1.2
                font.weight: Font.Bold
            }
            IconBtn {
                iconName: "table"; tip: "Tabellenansicht"; checkable: true
                checked: pl.st.viewMode !== "karten"
                onClicked: products.set("viewMode", "tabelle")
            }
            IconBtn {
                iconName: "cards"; tip: "Kartenansicht (größer, übersichtlich)"; checkable: true
                checked: pl.st.viewMode === "karten"
                onClicked: products.set("viewMode", "karten")
            }
        }

        Flow {
            Layout.fillWidth: true
            spacing: 8
            AppText { text: "Suchen in:"; color: theme.c.muted; height: 36 }
            ToggleChip {
                text: "Bezeichnung / Hersteller"; checked: pl.st.inBez
                tip: "In Bezeichnung und Hersteller suchen"
                onToggled: products.set("inBez", checked)
            }
            ToggleChip {
                text: "Merkmale"; checked: pl.st.inMerk
                tip: "In den Merkmalen suchen (Volltext)"
                onToggled: products.set("inMerk", checked)
            }
            ToggleChip {
                text: "Notizen & Kommentare"; checked: pl.st.inNotes
                tip: "In Ihren Notizen und den Kommentaren suchen"
                onToggled: products.set("inNotes", checked)
            }
            Item { width: 12; height: 1 }
            Btn {
                iconName: pl.st.moreFilters ? "chevronUp" : "filter"
                text: "Mehr Filter" + (products.activeMoreFilters ? "  (" + products.activeMoreFilters + " aktiv)" : "")
                tip: "Status, Version, Änderungsart, Hersteller, Farbkategorie"
                primary: products.activeMoreFilters > 0 && !pl.st.moreFilters
                onClicked: products.set("moreFilters", !pl.st.moreFilters)
            }
            Btn {
                iconName: "refresh"
                text: "Filter zurücksetzen"
                flat: true
                onClicked: products.resetFilter()
            }
            Btn {
                id: savedBtn
                iconName: "search"
                text: "Gespeicherte Suchen ▾"
                tip: "Filterkombination merken und wieder aufrufen"
                onClicked: savedMenu.popup(savedBtn, 0, savedBtn.height + 6)
                AppMenu {
                    id: savedMenu
                    Instantiator {
                        model: products.savedSearches
                        delegate: MItem { text: modelData; iconName: "search"; onTriggered: products.applySaved(modelData) }
                        onObjectAdded: (i, o) => savedMenu.insertItem(i, o)
                        onObjectRemoved: (i, o) => savedMenu.removeItem(o)
                    }
                    MSep { visible: products.savedSearches.length > 0 }
                    MItem { text: "Aktuelle Suche speichern …"; iconName: "plus"; onTriggered: products.saveSearch() }
                    AppMenu {
                        id: delMenu
                        title: "Gespeicherte Suche löschen"
                        enabled: products.savedSearches.length > 0
                        Instantiator {
                            model: products.savedSearches
                            delegate: MItem { text: modelData; iconName: "trash"; onTriggered: products.deleteSaved(modelData) }
                            onObjectAdded: (i, o) => delMenu.insertItem(i, o)
                            onObjectRemoved: (i, o) => delMenu.removeItem(o)
                        }
                    }
                }
            }
            Btn {
                iconName: "table"
                text: "Spalten …"
                tip: "Spalten ein-/ausblenden und ordnen"
                onClicked: maint.openColumns()
            }
        }

        // ------------------------------------------------ zusätzliche Filter (aufklappbar)
        Rectangle {
            Layout.fillWidth: true
            visible: pl.st.moreFilters
            implicitHeight: moreFlow.implicitHeight + 24
            radius: 14
            color: theme.c.alt
            border.color: theme.c.line
            Flow {
                id: moreFlow
                anchors.fill: parent
                anchors.margins: 12
                spacing: 12
                Labeled {
                    label: "Status"
                    Combo { width: 170; label: "Status"; model: products.statusOptions; value: pl.st.status
                            onPicked: (v) => products.set("status", v) }
                }
                Labeled {
                    label: "Geändert in Version"
                    Combo { width: 230; label: "Version"; model: products.versionOptions; value: pl.st.version
                            onPicked: (v) => products.set("version", v) }
                }
                Labeled {
                    label: "Art der Änderung"
                    Combo { width: 230; label: "Änderungsart"; model: products.typeOptions; value: pl.st.ctype
                            onPicked: (v) => products.set("ctype", v) }
                }
                Labeled {
                    label: "Hersteller (Teil des Namens)"
                    Field {
                        id: herField
                        width: 260
                        iconName: "search"
                        placeholderText: "Alle Hersteller"
                        onTextEdited: { herTimer.restart(); herPopup.open() }
                        onCleared: { herTimer.stop(); products.set("hersteller", "") }
                        onActiveFocusChanged: if (!activeFocus) herPopup.close()
                        Keys.onDownPressed: { herPopup.open(); herList.forceActiveFocus() }
                        Timer { id: herTimer; interval: 300; onTriggered: products.set("hersteller", herField.text) }
                        Connections {
                            target: products
                            function onChanged() {
                                if (!herTimer.running && !herField.activeFocus && herField.text !== products.state.hersteller)
                                    herField.text = products.state.hersteller
                            }
                        }
                        Popup {
                            id: herPopup
                            y: herField.height + 4
                            width: Math.max(herField.width, 320)
                            height: Math.min(320, herList.contentHeight + 12)
                            padding: 6
                            background: Rectangle { radius: 12; color: theme.c.surface; border.color: theme.c.line }
                            ListView {
                                id: herList
                                anchors.fill: parent
                                clip: true
                                model: herPopup.visible ? products.herstellerMatches(herField.text) : []
                                ScrollBar.vertical: ScrollBar { }
                                keyNavigationEnabled: true
                                Keys.onReturnPressed: pick(currentIndex)
                                function pick(i) {
                                    if (i < 0 || i >= count) return
                                    herField.text = model[i]
                                    herTimer.stop()
                                    products.set("hersteller", model[i])
                                    herPopup.close()
                                }
                                delegate: ItemDelegate {
                                    width: herList.width
                                    highlighted: ListView.isCurrentItem || hovered
                                    contentItem: AppText { text: modelData }
                                    background: Rectangle { radius: 8; color: parent.highlighted ? theme.c.mint : "transparent" }
                                    onClicked: herList.pick(index)
                                }
                            }
                        }
                    }
                }
                Labeled {
                    label: "Farbkategorie"
                    Combo { width: 210; label: "Farbkategorie"; model: products.categoryOptions; value: pl.st.kategorie
                            onPicked: (v) => products.set("kategorie", v) }
                }
                Labeled {
                    label: " "
                    Check { text: "„Nicht besetzt“ ausblenden"; checked: pl.st.ohnePlatzhalter
                            onToggled: products.set("ohnePlatzhalter", checked)
                            ToolTip.text: "Blendet die Platzhalter-Positionen des HMV mit der Bezeichnung „Nicht besetzt“ aus"
                            ToolTip.visible: hovered; ToolTip.delay: 600 }
                }
            }
        }

        AppText {
            Layout.fillWidth: true
            visible: products.selectedCount === 0 && !products.empty.title
            text: "Tipp: Produkt anklicken – rechts erscheinen alle Angaben. Rechte Maustaste = weitere Möglichkeiten. Stern = merken."
            rel: 0.88
            color: theme.c.muted
            wrapMode: Text.WordWrap
            elide: Text.ElideNone
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: products.empty.title ? 2 : (pl.st.viewMode === "karten" ? 1 : 0)
            DataTable {
                id: table
                objectName: "productTable"
                model: products.modelObj
                columns: products.columns
                draggable: true
                dragProxy: pl.ui ? pl.ui.dragItem : null
                dragStart: function (row) { return products.dragStart(row) }
                onRowClicked: (row, ctrl, shift) => products.click(row, ctrl, shift)
                onRowDoubleClicked: (row) => products.doubleClicked(row)
                onRowMenu: (row) => products.openMenu(row)
                onStarClicked: (row) => products.starClicked(row)
                onSortRequested: (key) => products.sortBy(key)
                onWidthRequested: (key, width) => products.setColumnWidth(key, width)
                onAutoWidthRequested: (key) => products.autoWidth(key)
                onMoveRequested: (delta, shift) => products.move(delta, shift)
                onSelectAllRequested: products.selectAll()
                onCopyRequested: products.copy("table")
                onReachedEnd: products.loadMore()
            }
            GridView {
                id: cards
                clip: true
                model: products.modelObj
                readonly property int perRow: Math.max(1, Math.floor(width / 330))
                cellWidth: Math.floor(width / perRow)
                cellHeight: Math.max(170, theme.fontPt * 14)
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar { }
                onAtYEndChanged: if (atYEnd && count > 0) products.loadMore()
                Keys.onDownPressed: products.move(perRow, false)
                Keys.onUpPressed: products.move(-perRow, false)
                Keys.onRightPressed: products.move(1, false)
                Keys.onLeftPressed: products.move(-1, false)
                delegate: Item {
                    width: cards.cellWidth
                    height: cards.cellHeight
                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 6
                        radius: 16
                        color: model.selected ? theme.c.select : (cma.containsMouse ? theme.c.hover : theme.c.surface)
                        border.width: model.selected ? 2 : 1
                        border.color: model.selected ? theme.c.green : theme.c.line
                        Rectangle {
                            visible: model.katColor !== ""
                            width: 6; radius: 3
                            anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom
                            anchors.margins: 8
                            color: model.katColor || "transparent"
                        }
                        MouseArea {
                            id: cma
                            anchors.fill: parent
                            hoverEnabled: true
                            acceptedButtons: Qt.LeftButton | Qt.RightButton
                            onClicked: (m) => {
                                cards.forceActiveFocus()
                                if (m.button === Qt.RightButton) products.openMenu(index)
                                else products.click(index, (m.modifiers & Qt.ControlModifier) !== 0, (m.modifiers & Qt.ShiftModifier) !== 0)
                            }
                            onDoubleClicked: products.doubleClicked(index)
                        }
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 14
                            anchors.leftMargin: 22
                            spacing: 6
                            RowLayout {
                                Layout.fillWidth: true
                                AppText {
                                    Layout.fillWidth: true
                                    text: model.title
                                    font.weight: Font.Bold
                                    wrapMode: Text.WordWrap
                                    maximumLineCount: 2
                                }
                                IconBtn {
                                    iconName: model.star === "★" ? "starFilled" : "star"
                                    iconColor: model.star ? theme.c.gold : theme.c.muted
                                    size: 34
                                    tip: "Favorit an/aus"
                                    onClicked: products.starClicked(index)
                                }
                            }
                            AppText { Layout.fillWidth: true; text: model.subtitle; color: theme.c.muted; rel: 0.9 }
                            Flow {
                                Layout.fillWidth: true
                                spacing: 6
                                Repeater {
                                    model: chips
                                    Chip { text: modelData.text; color: modelData.color }
                                }
                            }
                            AppText {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                text: model.comment
                                color: theme.c.muted
                                font.italic: true
                                rel: 0.9
                                wrapMode: Text.WordWrap
                                verticalAlignment: Text.AlignTop
                            }
                        }
                    }
                }
            }
            EmptyState {
                iconName: products.empty.icon || "search"
                title: products.empty.title || ""
                text: products.empty.text || ""
                actionText: products.empty.actionText || ""
                onAction: products.emptyAction(products.empty.action)
            }
        }

        Flow {   // umbrechen statt über den Kartenrand zu ragen
            Layout.fillWidth: true
            spacing: 8
            AppText { text: products.pager; color: theme.c.muted; rel: 0.9; width: Math.min(implicitWidth, parent.width) }
            Item { width: 12; height: 1 }
            AppText { text: "Farben:"; color: theme.c.muted; rel: 0.85 }
            Chip { text: "Neu"; color: theme.c.tagNeu }
            Chip { text: "Geändert"; color: theme.c.tagGeaendert }
            Chip { text: "Wieder aufgenommen"; color: theme.c.tagReaktiviert }
            Chip { text: "Umgruppiert"; color: theme.c.tagUmgruppiert }
            Chip { text: "Entfernt"; color: theme.c.tagEntfernt }
        }
    }

    component Labeled: Column {
        property string label: ""
        spacing: 4
        AppText { text: parent.label; rel: 0.85; color: theme.c.muted; font.weight: Font.DemiBold }
    }

    Connections {
        target: products
        function onCurrentRowChanged(row) {
            table.ensureVisible(row)
            if (row >= 0) cards.positionViewAtIndex(row, GridView.Contain)
        }
        function onListReset() { table.view.positionViewAtBeginning(); cards.positionViewAtBeginning() }
    }
}
