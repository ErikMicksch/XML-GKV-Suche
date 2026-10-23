import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// Was andere Benutzer kommentiert, eingefärbt oder an gemeinsamen Listen geändert haben
Item {
    property var ui
    readonly property var st: activity.state
    Card {
        anchors.fill: parent
        anchors.margins: 14
        ColumnLayout {
            anchors.fill: parent
            spacing: 10
            AppText { text: "Änderungen anderer Benutzer"; font.weight: Font.Bold; rel: 1.2 }
            AppText { Layout.fillWidth: true; color: theme.c.muted; wrapMode: Text.WordWrap; elide: Text.ElideNone
                      text: "Kommentare, Farbmarkierungen und Änderungen an gemeinsamen Listen von Kolleginnen und Kollegen. Doppelklick öffnet das Produkt bzw. die Liste." }
            Flow {
                Layout.fillWidth: true
                spacing: 10
                Combo { width: 220; label: "Zeitraum"; model: activity.periodOptions; value: st.days; onPicked: (v) => activity.set("days", v) }
                Combo { width: 200; label: "Art"; model: activity.kindOptions; value: st.kind; onPicked: (v) => activity.set("kind", v) }
                Combo { width: 200; label: "Benutzer"; model: activity.userOptions; value: st.user; onPicked: (v) => activity.set("user", v) }
                Check { text: "Eigene Änderungen auch anzeigen"; checked: st.mine; onToggled: activity.set("mine", checked) }
                Btn { iconName: "refresh"; text: "Aktualisieren"; onClicked: activity.set("days", st.days) }
                AppText { text: activity.info; color: theme.c.muted; height: 42 }
            }
            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: activity.empty.title ? 1 : 0
                DataTable {
                    model: activity.modelObj
                    columns: activity.columns
                    iconColumn: "art"
                    resizable: false
                    onRowDoubleClicked: (row) => activity.open(row)
                }
                EmptyState {
                    iconName: activity.empty.icon || "comment"
                    title: activity.empty.title || ""
                    text: activity.empty.text || ""
                    actionText: activity.empty.actionText || ""
                    onAction: activity.showMine()
                }
            }
        }
    }
}
