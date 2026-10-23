import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// Eigene Farbkategorien: anlegen, umbenennen, Farbe wählen (Farbfelder), löschen
AppDialog {
    id: dlg
    title: "Farbkategorien"
    iconName: "tag"
    preferredWidth: 640
    maxHeight: 760
    property string newColor: maint.swatches[3]

    AppText {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        elide: Text.ElideNone
        color: theme.c.muted
        text: "Ihre eigenen Kategorien (in Ihrer Favoriten-Datei). Wenn Sie ein Produkt einfärben, sehen Kollegen das unter „Änderungen anderer“."
    }
    ListView {
        id: lv
        Layout.fillWidth: true
        Layout.preferredHeight: Math.min(contentHeight, 320)
        clip: true
        spacing: 6
        model: maint.categories
        ScrollBar.vertical: ScrollBar { }
        delegate: Rectangle {
            id: catDel
            required property var modelData
            readonly property string catColor: String(modelData.color).toLowerCase()
            width: lv.width
            height: catCol.implicitHeight + 16
            radius: 12
            color: theme.c.alt
            border.color: theme.c.line
            ColumnLayout {
                id: catCol
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                anchors.margins: 8
                spacing: 6
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Rectangle { width: 22; height: 22; radius: 6; color: catDel.modelData.color }
                    Field {
                        Layout.fillWidth: true
                        text: catDel.modelData.name
                        clearable: false
                        Accessible.name: "Name der Kategorie"
                        onEditingFinished: if (text.trim() && text !== catDel.modelData.name) maint.renameCategory(catDel.modelData.cid, text)
                    }
                    AppText { text: catDel.modelData.n + " Produkte"; color: theme.c.muted }
                    IconBtn { iconName: "trash"; iconColor: theme.c.danger; tip: "Kategorie löschen"
                              onClicked: maint.deleteCategory(catDel.modelData.cid) }
                }
                Row {
                    spacing: 6
                    Repeater {
                        model: maint.swatches
                        Swatch { required property string modelData
                                 color: modelData; current: modelData.toLowerCase() === catDel.catColor
                                 onPicked: maint.recolorCategory(catDel.modelData.cid, modelData) }
                    }
                }
            }
        }
    }
    Rectangle { Layout.fillWidth: true; height: 1; color: theme.c.line }
    AppText { text: "Neue Kategorie"; font.weight: Font.Bold }
    RowLayout {
        Layout.fillWidth: true
        spacing: 8
        Rectangle { width: 22; height: 22; radius: 6; color: dlg.newColor }
        Field { id: newName; Layout.fillWidth: true; placeholderText: "Name, z. B. Rückfrage Hersteller"
                Keys.onReturnPressed: addBtn.clicked() }
        Btn { id: addBtn; primary: true; iconName: "plus"; text: "Anlegen"; enabled: newName.text.trim() !== ""
              onClicked: { maint.newCategory(newName.text, dlg.newColor); newName.text = "" } }
    }
    Row {
        spacing: 6
        Repeater {
            model: maint.swatches
            Swatch { color: modelData; current: dlg.newColor === modelData; onPicked: dlg.newColor = modelData }
        }
    }
    buttons: Btn { primary: true; text: "Fertig"; onClicked: dlg.close() }

    component Swatch: AbstractButton {
        id: sw
        property color color
        property bool current: false
        signal picked()
        implicitWidth: 30
        implicitHeight: 30
        focusPolicy: Qt.StrongFocus
        hoverEnabled: true
        Accessible.name: "Farbe " + sw.color
        onClicked: picked()
        background: Rectangle {
            radius: 8
            color: sw.color
            border.width: sw.current ? 3 : (sw.hovered ? 2 : 0)
            border.color: theme.c.text
            Icon { anchors.centerIn: parent; visible: sw.current; name: "check"; size: 16; color: "#FFFFFF" }
            FocusRing { target: sw; r: 8 }
        }
    }
}
