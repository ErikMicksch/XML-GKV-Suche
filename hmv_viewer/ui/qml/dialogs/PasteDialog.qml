import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// Viele Hilfsmittelnummern auf einmal einfügen (aus Excel, E-Mail …), prüfen und anzeigen oder in eine Liste legen
AppDialog {
    id: dlg
    property var result: ({ html: "", found: [] })
    title: "Nummernliste einfügen"
    iconName: "paste"
    preferredWidth: 680
    maxHeight: 760

    function openWith(text) { area.text = text; check(); open(); area.forceActiveFocus() }
    function check() { result = products.checkNumbers(area.text) }

    AppText {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        elide: Text.ElideNone
        text: "Hilfsmittelnummern hier einfügen (Strg+V) – beliebiger Text, z. B. aus Excel oder einer E-Mail:"
    }
    ScrollView {
        Layout.fillWidth: true
        Layout.preferredHeight: 280
        TextArea {
            id: area
            placeholderText: "01.24.01.0001\n0124010003\n…"
            wrapMode: TextEdit.Wrap
            font.pointSize: theme.fontPt
            color: theme.c.text
            placeholderTextColor: theme.c.muted
            Accessible.name: "Nummernliste"
            onTextChanged: checkTimer.restart()
            background: Rectangle { radius: 12; color: theme.c.surface; border.width: area.activeFocus ? 2 : 1
                                    border.color: area.activeFocus ? theme.c.focus : theme.c.line }
        }
    }
    Timer { id: checkTimer; interval: 250; onTriggered: dlg.check() }
    HtmlText { Layout.fillWidth: true; text: dlg.result.html }

    buttons: [
        Btn { text: "Abbrechen"; onClicked: dlg.close() },
        Btn { iconName: "list"; text: "Zu Liste hinzufügen …"; enabled: dlg.result.found.length > 0
              onClicked: { dlg.close(); products.pasteAdd(dlg.result.found) } },
        Btn { primary: true; iconName: "search"; text: "Gefundene anzeigen"; enabled: dlg.result.found.length > 0
              onClicked: { dlg.close(); products.pasteShow(dlg.result.found) } }
    ]
}
