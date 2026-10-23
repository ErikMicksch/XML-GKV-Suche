import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// Details rechts: Angaben, Kommentare, Historie und „Meine Notiz“
Card {
    id: dp
    readonly property var d: detail.data
    property string noteFor: ""
    property int tab: 0
    function focusNote() { if (detail.has) note.forceActiveFocus() }

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Btn {
                iconName: dp.d.isFav ? "starFilled" : "star"
                text: dp.d.isFav ? "Favorit entfernen" : "Merken"
                tip: "Als Favorit merken (Strg+D)"
                enabled: detail.has
                onClicked: detail.toggleFav()
            }
            Btn {
                iconName: "copy"
                text: "Kopieren"
                tip: "Hilfsmittelnummer kopieren"
                enabled: detail.has
                onClicked: detail.copyNumber()
            }
            Item { Layout.fillWidth: true }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            AppText { text: "Farbkategorie:"; color: theme.c.muted }
            Combo {
                Layout.fillWidth: true
                label: "Farbkategorie dieses Produkts"
                enabled: detail.has
                model: [{ value: "", text: "– keine Kategorie –", color: "" }].concat(products.categoryOptions.slice(1))
                value: dp.d.category || ""
                onPicked: (v) => detail.setCategory(v)
            }
        }

        Row {
            Layout.fillWidth: true
            spacing: 4
            TabBtn { idx: 0; label: "Details" }
            TabBtn { idx: 1; label: "Kommentare" + (dp.d.nComments ? " (" + dp.d.nComments + ")" : "") }
            TabBtn { idx: 2; label: "Historie" }
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: theme.c.line }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: detail.has ? dp.tab : 3

            // ---------------------------------------- Details
            ScrollView {
                id: detailScroll
                clip: true
                contentWidth: availableWidth
                Column {
                    width: detailScroll.availableWidth
                    spacing: 8
                    AppText {
                        width: parent.width
                        text: dp.d.title || ""
                        rel: 1.35
                        font.weight: Font.Bold
                        wrapMode: Text.WordWrap
                        elide: Text.ElideNone
                    }
                    Flow {
                        width: parent.width
                        spacing: 6
                        Repeater {
                            model: dp.d.chips || []
                            Chip { text: modelData.text; color: modelData.color; fg: modelData.fg }
                        }
                    }
                    Section { width: parent.width; title: "Einordnung"; html: dp.d.info || ""; onLinkActivated: (l) => detail.link(l) }
                    Section { id: merkSection; width: parent.width; title: "Merkmale"; html: dp.d.merk || ""; onLinkActivated: (l) => detail.link(l) }
                    Row {
                        visible: dp.d.hasMerkLinks === true
                        x: 22
                        spacing: 6
                        AppText { text: "▸"; color: theme.c.green; rel: 0.9 }
                        AppText { text: "Grün unterstrichene Zeilen anklicken = alle Produkte mit genau dieser Angabe suchen"
                                  color: theme.c.muted; rel: 0.85; width: detailScroll.availableWidth - 60; wrapMode: Text.WordWrap
                                  elide: Text.ElideNone }
                    }
                    Section { width: parent.width; title: "Listen"; html: dp.d.lists || ""; onLinkActivated: (l) => detail.link(l) }
                    AppText { width: parent.width; text: dp.d.hint || ""; color: theme.c.muted; rel: 0.85; wrapMode: Text.WordWrap
                              elide: Text.ElideNone }
                }
            }

            // ---------------------------------------- Kommentare
            ColumnLayout {
                spacing: 8
                AppText { Layout.fillWidth: true; text: "Kommentare sind für alle Benutzer sichtbar."; color: theme.c.muted; rel: 0.85 }
                ListView {
                    id: commentList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: 8
                    model: detail.commentModel
                    ScrollBar.vertical: ScrollBar { }
                    delegate: Rectangle {
                        width: commentList.width - 8
                        height: cCol.implicitHeight + 20
                        radius: 12
                        color: model.mine ? theme.c.mint : theme.c.alt
                        border.color: theme.c.line
                        ColumnLayout {
                            id: cCol
                            anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                            anchors.margins: 10
                            spacing: 4
                            RowLayout {
                                Layout.fillWidth: true
                                AppText { text: model.user; font.weight: Font.Bold }
                                AppText { text: model.when; color: theme.c.muted; rel: 0.85; Layout.fillWidth: true }
                                IconBtn { visible: model.mine; iconName: "trash"; iconColor: theme.c.danger; size: 30
                                          tip: "Eigenen Kommentar löschen"; onClicked: detail.deleteComment(model.cid) }
                            }
                            AppText { Layout.fillWidth: true; text: model.text; wrapMode: Text.WordWrap; elide: Text.ElideNone }
                        }
                    }
                    AppText { anchors.centerIn: parent; visible: commentList.count === 0; text: "Noch keine Kommentare."; color: theme.c.muted }
                }
                TextArea {
                    id: commentInput
                    Layout.fillWidth: true
                    Layout.preferredHeight: 80
                    placeholderText: "Kommentar schreiben … (Strg+Enter sendet)"
                    wrapMode: TextEdit.Wrap
                    font.pointSize: theme.fontPt
                    color: theme.c.text
                    placeholderTextColor: theme.c.muted
                    Accessible.name: "Kommentar schreiben"
                    background: Rectangle { radius: 12; color: theme.c.surface; border.width: commentInput.activeFocus ? 2 : 1
                                            border.color: commentInput.activeFocus ? theme.c.focus : theme.c.line }
                    Keys.onPressed: (e) => { if ((e.key === Qt.Key_Return || e.key === Qt.Key_Enter) && (e.modifiers & Qt.ControlModifier)) { sendBtn.clicked(); e.accepted = true } }
                }
                Btn {
                    id: sendBtn
                    Layout.alignment: Qt.AlignRight
                    primary: true
                    iconName: "comment"
                    text: "Kommentar senden"
                    enabled: commentInput.text.trim() !== ""
                    onClicked: if (detail.sendComment(commentInput.text)) commentInput.text = ""
                }
            }

            // ---------------------------------------- Historie
            ColumnLayout {
                spacing: 8
                ListView {
                    id: histList
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(contentHeight, parent.height * 0.4)
                    clip: true
                    model: detail.historyModel
                    ScrollBar.vertical: ScrollBar { }
                    delegate: Rectangle {
                        width: histList.width
                        height: Math.max(36, theme.fontPt * 3)
                        radius: 8
                        color: model.selected ? theme.c.select : (model.bg || theme.c.surface)
                        border.width: model.selected ? 2 : 0
                        border.color: theme.c.green
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            spacing: 10
                            AppText { text: model.version; font.weight: Font.DemiBold; Layout.preferredWidth: 150 }
                            AppText { text: model.type; Layout.preferredWidth: 130 }
                            AppText { text: model.fields; color: theme.c.muted; Layout.fillWidth: true }
                        }
                        MouseArea { anchors.fill: parent; onClicked: detail.selectHistory(model.idx) }
                    }
                }
                ScrollView {
                    id: histScroll
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    contentWidth: availableWidth
                    HtmlText { width: histScroll.availableWidth; text: detail.historyHtml }
                }
            }

            // ---------------------------------------- nichts ausgewählt
            EmptyState {
                iconName: "box"
                title: "Kein Produkt ausgewählt"
                text: dp.d.hint || ""
            }
        }

        AppText { text: "Meine Notiz"; font.weight: Font.Bold }
        TextArea {
            id: note
            Layout.fillWidth: true
            Layout.preferredHeight: 92
            enabled: detail.has
            placeholderText: "z. B. Hinweise, Ansprechpartner … – nur für Sie, wird automatisch gespeichert"
            wrapMode: TextEdit.Wrap
            font.pointSize: theme.fontPt
            color: theme.c.text
            placeholderTextColor: theme.c.muted
            Accessible.name: "Meine Notiz"
            background: Rectangle { radius: 12; color: note.enabled ? theme.c.surface : theme.c.disabledBg
                                    border.width: note.activeFocus ? 2 : 1; border.color: note.activeFocus ? theme.c.focus : theme.c.line }
            onTextChanged: if (activeFocus) { detail.setNote(text); noteTimer.restart() }
            onActiveFocusChanged: if (!activeFocus) { noteTimer.stop(); detail.saveNote() }
            Timer { id: noteTimer; interval: 800; onTriggered: detail.saveNote() }
        }
    }

    component TabBtn: AbstractButton {
        id: tb
        property int idx: 0
        property string label: ""
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        implicitHeight: Math.max(38, theme.fontPt * 3.2)
        implicitWidth: tl.implicitWidth + 28
        Accessible.name: label
        onClicked: dp.tab = idx
        contentItem: AppText { id: tl; text: tb.label; horizontalAlignment: Text.AlignHCenter
                               color: dp.tab === tb.idx ? theme.c.green : theme.c.muted; font.weight: Font.Bold }
        background: Rectangle {
            radius: 8
            color: tb.hovered ? theme.c.hover : "transparent"
            Rectangle { visible: dp.tab === tb.idx; anchors.bottom: parent.bottom; width: parent.width; height: 3; radius: 2
                        color: theme.c.green }
            FocusRing { target: tb; r: 8 }
        }
    }

    Connections {
        target: detail
        function onChanged() {
            if (dp.noteFor !== (dp.d.nummer || "") || !note.activeFocus) {
                note.text = detail.note
                dp.noteFor = dp.d.nummer || ""
            }
            if (dp.d.jumpToMerk)   // Suchtreffer in den Merkmalen: dorthin blättern
                Qt.callLater(function () { detailScroll.contentItem.contentY = Math.max(0, merkSection.y - 8) })
        }
    }
}
