import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// Ziel-Liste wählen (Meine Favoriten, private oder gemeinsame Listen) – bei Produktgruppen auch, wie übernommen wird
AppDialog {
    id: dlg
    property var info: ({})
    property string selected: lists.lastTarget
    title: "Zu Liste hinzufügen"
    iconName: "list"
    preferredWidth: 640
    maxHeight: 760

    function openWith(i) { info = i; selected = lists.lastTarget; wholeGroup.checked = true; open() }

    AppText {
        Layout.fillWidth: true
        text: "„" + (dlg.info.what || "") + "“ hinzufügen zu …"
        font.weight: Font.DemiBold
        wrapMode: Text.WordWrap
        elide: Text.ElideNone
    }
    Rectangle {
        Layout.fillWidth: true
        Layout.preferredHeight: 300
        radius: 12
        color: theme.c.surface
        border.color: theme.c.line
        ListView {
            id: lv
            anchors.fill: parent
            anchors.margins: 6
            clip: true
            model: lists.targetModel
            ScrollBar.vertical: ScrollBar { }
            delegate: ItemDelegate {
                width: lv.width
                enabled: model.selectable
                hoverEnabled: true
                highlighted: dlg.selected === model.cid
                onClicked: dlg.selected = model.cid
                onDoubleClicked: { dlg.selected = model.cid; addBtn.clicked() }
                contentItem: RowLayout {
                    spacing: 8
                    Item { Layout.preferredWidth: model.depth * 20 }
                    Icon { name: model.icon; size: 18; color: theme.c[model.iconColor] || theme.c.green }
                    AppText { text: model.label; Layout.fillWidth: true; font.weight: model.depth === 0 ? Font.Bold : Font.Normal
                              color: model.selectable ? theme.c.text : theme.c.muted }
                    Icon { visible: dlg.selected === model.cid; name: "check"; size: 18; color: theme.c.green }
                }
                background: Rectangle { radius: 8; color: parent.highlighted ? theme.c.mint : parent.hovered ? theme.c.hover : "transparent" }
            }
        }
    }
    ColumnLayout {
        visible: dlg.info.isGroup === true
        Layout.fillWidth: true
        spacing: 6
        AppText { text: "Wie soll die Produktgruppe übernommen werden?"; font.weight: Font.DemiBold }
        RadioButton {
            id: wholeGroup
            Layout.fillWidth: true
            checked: true
            font.pointSize: theme.fontPt
            contentItem: AppText { text: "Ganze Produktgruppe – neue Produkte der Gruppe gehören automatisch dazu"; leftPadding: 32
                                   wrapMode: Text.WordWrap; elide: Text.ElideNone }
        }
        RadioButton {
            Layout.fillWidth: true
            font.pointSize: theme.fontPt
            contentItem: AppText { text: "Alle " + (dlg.info.nText || "") + " aktiven Produkte einzeln – fester Stand von heute"
                                   leftPadding: 32; wrapMode: Text.WordWrap; elide: Text.ElideNone }
        }
    }
    footerLeft: Btn { text: "Neue Liste hier …"; iconName: "plus"; onClicked: lists.newTargetHere(dlg.selected) }
    buttons: [
        Btn { text: "Abbrechen"; onClicked: dlg.close() },
        Btn {
            id: addBtn
            primary: true
            iconName: "plus"
            text: "Hinzufügen"
            enabled: dlg.selected !== "liste:"
            onClicked: { lists.acceptAdd(dlg.selected, wholeGroup.checked || dlg.info.isGroup !== true); dlg.close() }
        }
    ]
}
