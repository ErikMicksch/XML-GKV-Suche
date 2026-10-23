import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// Einrichtung beim ersten Start: Speicherort der persönlichen Favoriten und Name – in zwei einfachen Schritten
Rectangle {
    id: setup
    gradient: Gradient {
        GradientStop { position: 0.0; color: theme.c.headerA }
        GradientStop { position: 1.0; color: theme.c.headerC }
    }
    MouseArea { anchors.fill: parent }   // nichts dahinter anklickbar

    Card {
        anchors.centerIn: parent
        width: Math.min(parent.width - 48, 680)
        height: col.implicitHeight + 56
        padding: 28
        ColumnLayout {
            id: col
            anchors.left: parent.left
            anchors.right: parent.right
            spacing: 14
            AppText { text: "Willkommen beim HMV-Viewer"; rel: 1.8; font.weight: Font.Bold; color: theme.c.green }
            AppText { Layout.fillWidth: true; wrapMode: Text.WordWrap; elide: Text.ElideNone; color: theme.c.muted
                      text: "Zwei kurze Angaben, dann geht es los. Beides lässt sich später unter „Einstellungen“ ändern." }

            AppText { text: "1.  Wo sollen Ihre Favoriten und Notizen gespeichert werden?"; font.weight: Font.Bold; Layout.topMargin: 8 }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Field { id: folder; Layout.fillWidth: true; text: core.defaultFolder; iconName: "folder"; clearable: false
                        placeholderText: "Ordner" }
                Btn { text: "Ordner wählen …"; iconName: "folder"; onClicked: { var f = core.chooseFolder(); if (f) folder.text = f } }
            }
            AppText { Layout.fillWidth: true; wrapMode: Text.WordWrap; elide: Text.ElideNone; rel: 0.9; color: theme.c.muted
                      text: "Tipp: Ein Ordner auf dem Netzlaufwerk bleibt auch beim PC-Wechsel erhalten. Jeder Benutzer hat eine eigene Datei." }

            AppText { text: "2.  Ihr Nachname"; font.weight: Font.Bold; Layout.topMargin: 8 }
            Field { id: name; Layout.fillWidth: true; text: core.defaultName; iconName: "user"; placeholderText: "z. B. Müller"
                    Keys.onReturnPressed: go.clicked() }
            AppText { Layout.fillWidth: true; wrapMode: Text.WordWrap; elide: Text.ElideNone; rel: 0.9; color: theme.c.muted
                      text: "Kein Passwort nötig. Der Name erscheint bei gemeinsamen Listen und Kommentaren." }

            Btn {
                id: go
                Layout.alignment: Qt.AlignRight
                Layout.topMargin: 10
                primary: true
                iconName: "check"
                text: "Los geht's"
                implicitHeight: 52
                onClicked: core.finishSetup(folder.text, name.text)
            }
        }
    }
}
