import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// Excel-Export: was und welche Blätter
AppDialog {
    id: dlg
    property var info: ({})
    property string scope: "filter"
    title: "Excel-Export"
    iconName: "export"
    preferredWidth: 620

    function openWith(i) { info = i; scope = "filter"; open() }

    AppText { text: "Welche Produkte sollen exportiert werden?"; font.weight: Font.Bold }
    Repeater {
        model: [{ v: "filter", t: "Aktuelle Auswahl / Filter (" + (dlg.info.filtered || "0") + " Produkte)" },
                { v: "favoriten", t: "Meine Favoriten (" + (dlg.info.favs || "0") + " Produkte)" },
                { v: "aktiv", t: "Alle aktiven Produkte" },
                { v: "alle", t: "Alle Produkte inkl. entfernter" }]
        RadioButton {
            Layout.fillWidth: true
            checked: dlg.scope === modelData.v
            onClicked: dlg.scope = modelData.v
            font.pointSize: theme.fontPt
            contentItem: AppText { text: modelData.t; leftPadding: 32 }
        }
    }
    AppText { text: "Inhalt"; font.weight: Font.Bold; Layout.topMargin: 8 }
    Check { id: personal; Layout.fillWidth: true; checked: true; text: "Spalten „Favorit“, „Kategorie“ und „Meine Notiz“ anhängen" }
    Check { id: hist; Layout.fillWidth: true; checked: true; text: "Blatt Änderungshistorie (Feld, alter Wert, neuer Wert je Version)" }
    Check { id: initial; Layout.fillWidth: true; text: "Erstimport (alle Produkte als „Neu“) in der Historie mit aufführen" }
    Check { id: vers; Layout.fillWidth: true; checked: true; text: "Blatt Versionen (Übersicht aller Importe)" }

    buttons: [
        Btn { text: "Abbrechen"; onClicked: dlg.close() },
        Btn { primary: true; iconName: "export"; text: "Exportieren …"
              onClicked: { dlg.close(); maint.doExport(dlg.scope, personal.checked, hist.checked, initial.checked, vers.checked) } }
    ]
}
