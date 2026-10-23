import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// Einstellungen an einem Ort: Design, Schriftgröße, Zeilenhöhe, Markierfarbe, Speicherort, Kategorien
AppDialog {
    id: dlg
    title: "Einstellungen"
    iconName: "settings"
    preferredWidth: 760
    maxHeight: 1000

    ScrollView {
        id: sv
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.preferredHeight: col.implicitHeight
        clip: true
        contentWidth: availableWidth
        ColumnLayout {
            id: col
            width: sv.availableWidth
            spacing: 12

            AppText { text: "Design"; font.weight: Font.Bold }
            Flow {
                Layout.fillWidth: true
                spacing: 10
                Repeater {
                    model: theme.names
                    ToggleChip {
                        text: modelData
                        checked: theme.name === modelData
                        onClicked: theme.setTheme(modelData)
                    }
                }
            }
            AppText { text: "Schriftgröße"; font.weight: Font.Bold; Layout.topMargin: 6 }
            Flow {
                Layout.fillWidth: true
                spacing: 10
                Repeater {
                    model: theme.fontSizes
                    ToggleChip { text: modelData + " pt"; checked: theme.fontPt === modelData; onClicked: theme.setFont(modelData) }
                }
            }
            AppText { text: "Zeilenhöhe der Tabellen"; font.weight: Font.Bold; Layout.topMargin: 6 }
            Flow {
                Layout.fillWidth: true
                spacing: 10
                Repeater {
                    model: theme.densities
                    ToggleChip { text: modelData; checked: theme.density === modelData; onClicked: theme.setDensity(modelData) }
                }
            }
            AppText { text: "Markierung von Suchtreffern in den Merkmalen"; font.weight: Font.Bold; Layout.topMargin: 6 }
            Row {
                spacing: 8
                Repeater {
                    model: maint.markColors
                    AbstractButton {
                        id: mc
                        implicitWidth: 34; implicitHeight: 34
                        hoverEnabled: true
                        focusPolicy: Qt.StrongFocus
                        Accessible.name: "Markierfarbe " + modelData
                        readonly property bool current: String(detail.markColor).toLowerCase() === modelData.toLowerCase()
                        onClicked: maint.setMarkColor(modelData)
                        background: Rectangle {
                            radius: 8
                            color: modelData
                            border.width: mc.current ? 3 : (mc.hovered ? 2 : 1)
                            border.color: mc.current ? theme.c.text : theme.c.line
                            Icon { anchors.centerIn: parent; visible: mc.current; name: "check"; size: 18; color: "#1B2A23" }
                            FocusRing { target: mc; r: 8 }
                        }
                    }
                }
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: theme.c.line; Layout.topMargin: 6 }
            AppText { text: "Speicherort Ihrer Favoriten & Notizen"; font.weight: Font.Bold }
            AppText { Layout.fillWidth: true; text: core.favPath; color: theme.c.muted; wrapMode: Text.WrapAnywhere; elide: Text.ElideNone }
            Flow {
                Layout.fillWidth: true
                spacing: 10
                Btn { iconName: "folder"; text: "Anderen Ordner wählen …"; onClicked: maint.changeFavFolder() }
                Btn { iconName: "external"; text: "Ordner im Explorer öffnen"; flat: true; onClicked: maint.openFavFolder() }
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: theme.c.line; Layout.topMargin: 6 }
            AppText { text: "Datenbank und Sicherungen (gilt für alle, die dieses Programm starten)"; font.weight: Font.Bold
                      Layout.fillWidth: true; wrapMode: Text.WordWrap; elide: Text.ElideNone }
            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: 12
                AppText { text: "Datenbank:"; color: theme.c.muted }
                AppText { Layout.fillWidth: true; text: core.dbPath; wrapMode: Text.WrapAnywhere; elide: Text.ElideNone }
                AppText { text: "Sicherungen:"; color: theme.c.muted }
                AppText { Layout.fillWidth: true; text: maint.backupPath; wrapMode: Text.WrapAnywhere; elide: Text.ElideNone }
            }
            Flow {
                Layout.fillWidth: true
                spacing: 10
                Btn { iconName: "database"; text: "Datenbank wählen …"; onClicked: maint.chooseDatabase() }
                Btn { iconName: "folder"; text: "Sicherungsordner wählen …"; onClicked: maint.chooseBackupDir() }
            }
            AppText {
                Layout.fillWidth: true
                rel: 0.9
                color: theme.c.muted
                wrapMode: Text.WordWrap
                elide: Text.ElideNone
                text: "Gespeichert in " + maint.pathsFile + " – zieht die Datenbank um, genügt es, diese Datei auszutauschen."
                      + (maint.envOverride ? " Achtung: Die Umgebungsvariable HMV_DB hat Vorrang vor dieser Datei." : "")
            }
            AppText { text: "Weitere"; font.weight: Font.Bold; Layout.topMargin: 6 }
            Flow {
                Layout.fillWidth: true
                spacing: 10
                Btn { iconName: "tag"; text: "Farbkategorien …"; onClicked: { dlg.close(); maint.openCategories() } }
                Btn { iconName: "table"; text: "Spalten der Produktliste …"; onClicked: { dlg.close(); maint.openColumns() } }
                Btn { iconName: "keyboard"; text: "Tastenkürzel …"; onClicked: maint.shortcuts() }
            }
        }
    }
    buttons: Btn { primary: true; text: "Fertig"; onClicked: dlg.close() }
}
