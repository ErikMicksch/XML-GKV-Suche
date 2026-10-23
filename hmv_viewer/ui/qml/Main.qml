import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components"
import "pages"
import "dialogs"

ApplicationWindow {
    id: root
    visible: true
    width: 1600
    height: 940
    minimumWidth: 1024
    minimumHeight: 640
    title: "HMV-Viewer – Hilfsmittelverzeichnis  (v" + maint.version + " · Testoberfläche)"
    color: theme.c.bg
    font.pointSize: theme.fontPt
    font.family: "Segoe UI"

    readonly property bool compactNav: width < 1300       // Navigation nur mit Symbolen
    readonly property bool compactHeader: width < 1500    // Kopf-Knöpfe nur mit Symbolen
    readonly property bool narrow: width < 1700           // Produktgruppen als ausklappbare Leiste

    onActiveChanged: if (active) core.activated()

    // ------------------------------------------------------------------ Kopf
    header: Rectangle {
        id: head
        height: 76
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: theme.c.headerA }
            GradientStop { position: 0.6; color: theme.c.headerB }
            GradientStop { position: 1.0; color: theme.c.headerC }
        }
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: theme.c.line; visible: !theme.dark && theme.c.headerA === "#ffffff" }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 20
            anchors.rightMargin: 16
            spacing: 10
            Column {
                Layout.preferredWidth: root.compactHeader ? 150 : 210
                AppText { text: "HMV-Viewer"; rel: 1.6; font.weight: Font.Bold; color: theme.c.headerFg }
                AppText { text: "Hilfsmittelverzeichnis · v" + maint.version; rel: 0.85; color: theme.c.headerSub; visible: !root.compactHeader }
            }
            Field {
                id: searchField
                Layout.fillWidth: true
                Layout.minimumWidth: 220
                Layout.maximumWidth: 760
                big: true
                iconName: "search"
                placeholderText: "Hier suchen, z. B. Rollator oder 10.46"
                Accessible.name: "Produkte suchen"
                ToolTip.text: "Alle Wörter müssen vorkommen; Wortanfang genügt (batt → Batterie).\n\"Typ 10\" = genau diese Wortfolge · -netzabhängig = ausschließen · 01.24.01 = Nummernbereich"
                ToolTip.visible: hovered && text === ""
                ToolTip.delay: 1200
                onTextEdited: searchTimer.restart()
                onCleared: { searchTimer.stop(); products.set("text", "") }
                Keys.onDownPressed: { products.move(1, false); productsPage.focusTable() }
                Keys.onEscapePressed: { clear(); searchTimer.stop(); products.set("text", "") }
                Keys.onReturnPressed: { searchTimer.stop(); core.goto(0); products.set("text", text) }
                Timer {
                    id: searchTimer
                    interval: 300
                    onTriggered: { if (core.page !== 0) core.goto(0); products.set("text", searchField.text) }
                }
                Connections {
                    target: products
                    function onChanged() {
                        if (!searchTimer.running && searchField.text !== products.state.text)
                            searchField.text = products.state.text
                    }
                }
            }
            Btn {
                onHeader: true; iconName: "zap"
                text: root.compactHeader ? "" : "Schnellzugriff"
                tip: "Produkte, Gruppen, Listen und Funktionen schnell finden (Strg+K)"
                onClicked: maint.openPalette()
            }
            Btn {
                id: dataBtn
                onHeader: true; iconName: "database"
                text: root.compactHeader ? "" : "Daten ▾"
                tip: "Importieren, Excel-Export, Nummernliste, Sicherung"
                onClicked: dataMenu.popup(dataBtn, 0, dataBtn.height + 6)
                AppMenu {
                    id: dataMenu
                    MItem { text: "Importieren …  (Strg+I)"; iconName: "import"; visible: !core.readOnly; height: visible ? implicitHeight : 0; onTriggered: maint.startImport() }
                    MItem { text: "Excel-Export …  (Strg+E)"; iconName: "export"; onTriggered: maint.startExport() }
                    MItem { text: "Nummernliste einfügen …  (Strg+Umschalt+V)"; iconName: "paste"; onTriggered: maint.openPaste() }
                    MSep { }
                    MItem { text: "Datenbank sichern (Backup) …"; iconName: "save"; onTriggered: maint.backup() }
                    MItem { text: "Aus Sicherung wiederherstellen (NUR IM NOTFALL) …"; iconName: "alert"; dangerous: true
                            enabled: !core.readOnly; onTriggered: maint.restore() }
                }
            }
            Btn {
                onHeader: true; iconName: "starFilled"
                text: root.compactHeader ? "" : "Favoriten"
                tip: "Meine Favoriten anzeigen (Strg+B)"
                onClicked: products.showFavorites()
            }
            Btn {
                highlight: true; iconName: "help"; text: "Hilfe"
                tip: "Erklärt die Seite, auf der Sie gerade sind (F1)"
                onClicked: maint.help()
            }
            Btn {
                onHeader: true; iconName: "user"
                text: root.compactHeader ? "" : core.userName
                tip: "Angemeldet als " + core.userName
                onClicked: core.showUser()
            }
            Btn {
                id: menuBtn
                onHeader: true; iconName: "menu"
                text: root.compactHeader ? "" : "Menü"
                tip: "Einstellungen, Listen, Tastenkürzel, Info"
                onClicked: mainMenu.popup(menuBtn, menuBtn.width - mainMenu.width, menuBtn.height + 6)
                AppMenu {
                    id: mainMenu
                    MItem { text: "Einstellungen …"; iconName: "settings"; onTriggered: maint.openSettings() }
                    MItem { text: "Farbkategorien verwalten …"; iconName: "tag"; onTriggered: maint.openCategories() }
                    MItem { text: "Spalten der Produktliste …"; iconName: "table"; onTriggered: maint.openColumns() }
                    MSep { }
                    MItem { text: "Neue private Liste …"; iconName: "plus"; onTriggered: lists.newList(false) }
                    MItem { text: "Neue gemeinsame Liste …"; iconName: "plus"; onTriggered: lists.newList(true) }
                    MItem { text: "Was ist neu?"; iconName: "bell"; onTriggered: maint.whatsNew() }
                    MSep { }
                    MItem { text: "Tastenkürzel …"; iconName: "keyboard"; onTriggered: maint.shortcuts() }
                    MItem { text: "Info & Support …"; iconName: "info"; onTriggered: maint.info() }
                    MItem { text: "Neu laden  (F5)"; iconName: "refresh"; onTriggered: core.reload() }
                }
            }
        }
    }

    // ------------------------------------------------------------------ Inhalt: Navigation links, Seiten rechts
    RowLayout {
        anchors.fill: parent
        spacing: 0
        Rectangle {
            Layout.fillHeight: true
            Layout.preferredWidth: root.compactNav ? 84 : 292
            color: theme.c.surface
            Behavior on Layout.preferredWidth { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: root.compactNav ? 10 : 14
                anchors.topMargin: 18
                spacing: 6
                NavBtn { page: 2; label: "Startseite"; iconName: "home"; tip: "Überblick: Neuigkeiten, Ihre Favoriten, zuletzt angesehen (Strg+0)" }
                NavBtn { page: 0; label: "Produkte suchen"; iconName: "box"; tip: "Alle Hilfsmittel durchsuchen, filtern und ansehen (Strg+1)" }
                NavBtn { page: 1; label: "Versionen"; iconName: "history"; tip: "Welche Produkte sich mit einer neuen Ausgabe geändert haben (Strg+2)" }
                NavBtn { page: 3; label: "Änderungen anderer"; iconName: "comment"; badge: activity.badge
                         tip: "Was Kolleginnen und Kollegen kommentiert oder geändert haben (Strg+3)" }
                Item { Layout.fillHeight: true }
                Btn {
                    Layout.fillWidth: true
                    iconName: "help"
                    text: root.compactNav ? "" : "Hilfe zu dieser Seite"
                    tip: "Hilfe zu dieser Seite (F1)"
                    onClicked: maint.help()
                }
                Btn {
                    Layout.fillWidth: true
                    iconName: "settings"
                    text: root.compactNav ? "" : "Einstellungen"
                    tip: "Design, Schriftgröße, Zeilenhöhe, Speicherort"
                    onClicked: maint.openSettings()
                }
            }
        }
        StackLayout {
            id: stack
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: core.page
            onCurrentIndexChanged: fade.restart()
            NumberAnimation { id: fade; target: stack; property: "opacity"; from: 0.35; to: 1; duration: 180; easing.type: Easing.OutCubic }
            ProductsPage { id: productsPage; ui: root }
            VersionsPage { ui: root }
            StartPage { ui: root }
            ActivityPage { ui: root }
        }
    }

    component NavBtn: AbstractButton {
        id: nb
        property int page: 0
        property string label: ""
        property string iconName: ""
        property string tip: ""
        property int badge: 0
        readonly property bool current: core.page === page
        Layout.fillWidth: true
        implicitHeight: 56
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        Accessible.name: label + (badge ? ", " + badge + " neu" : "")
        ToolTip.text: tip
        ToolTip.visible: hovered
        ToolTip.delay: root.compactNav ? 200 : 900
        onClicked: core.goto(page)
        contentItem: Item {
            Row {
                anchors.verticalCenter: parent.verticalCenter
                anchors.horizontalCenter: root.compactNav ? parent.horizontalCenter : undefined
                x: root.compactNav ? 0 : 14
                spacing: 12
                Icon {
                    name: nb.iconName
                    size: 26
                    color: nb.current ? theme.c.green : theme.c.muted
                    anchors.verticalCenter: parent.verticalCenter
                }
                AppText {
                    visible: !root.compactNav
                    text: nb.label
                    width: Math.min(implicitWidth, nb.width - 66 - (nb.badge > 0 ? 40 : 0))   // nie unter den Zähler
                    color: nb.current ? theme.c.green : theme.c.text
                    font.weight: nb.current ? Font.Bold : Font.DemiBold
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
            Rectangle {   // Zähler „neu“
                visible: nb.badge > 0
                anchors.right: parent.right
                anchors.rightMargin: root.compactNav ? 2 : 10
                y: root.compactNav ? 4 : (parent.height - height) / 2
                height: 24; radius: 12
                width: Math.max(24, badgeText.implicitWidth + 12)
                color: theme.c.gold
                AppText { id: badgeText; anchors.centerIn: parent; text: nb.badge > 99 ? "99+" : String(nb.badge); rel: 0.8
                          font.weight: Font.Bold; color: theme.c.goldText }
            }
        }
        background: Rectangle {
            radius: 14
            color: nb.current ? theme.c.mint : nb.hovered ? theme.c.hover : "transparent"
            Behavior on color { ColorAnimation { duration: 120 } }
            Rectangle { visible: nb.current; width: 5; height: parent.height - 16; radius: 3; color: theme.c.green
                        anchors.verticalCenter: parent.verticalCenter }
            FocusRing { target: nb; r: 14 }
        }
    }

    // ------------------------------------------------------------------ Statuszeile
    footer: Rectangle {
        height: 32
        color: theme.c.surface
        Rectangle { width: parent.width; height: 1; color: theme.c.line }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 14
            anchors.rightMargin: 14
            spacing: 18
            AppText { Layout.fillWidth: true; text: core.status; rel: 0.85; color: theme.c.muted }
            Rectangle {
                visible: core.readOnly
                radius: 10; height: 22; width: roText.implicitWidth + 18
                color: theme.c.danger
                AppText { id: roText; anchors.centerIn: parent; rel: 0.8; font.weight: Font.Bold; color: theme.c.onDanger
                          text: "NUR LESEN – keine Schreibrechte auf die gemeinsame Datenbank" }
            }
            AppText { text: "★ " + core.favPath; rel: 0.8; color: theme.c.muted; Layout.maximumWidth: 420; visible: !root.narrow }
            AppText { text: "Datenbank: " + core.dbPath; rel: 0.8; color: theme.c.muted; Layout.maximumWidth: 420; visible: !root.compactHeader }
        }
    }

    // ------------------------------------------------------------------ Hinweis unten (mit „Rückgängig“)
    Rectangle {
        id: toast
        property int aid: -1
        z: 50
        visible: opacity > 0
        opacity: 0
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 26
        radius: 14
        height: 52
        width: Math.min(root.width - 80, toastRow.implicitWidth + 36)
        color: theme.dark ? theme.c.surface : "#1B2A23"
        border.color: theme.dark ? theme.c.line : "transparent"
        Behavior on opacity { NumberAnimation { duration: 160 } }
        Row {
            id: toastRow
            anchors.centerIn: parent
            spacing: 16
            AppText { id: toastText; color: theme.dark ? theme.c.text : "#FFFFFF"; anchors.verticalCenter: parent.verticalCenter
                      width: Math.min(implicitWidth, root.width - 300) }
            Btn {
                id: toastBtn
                visible: toast.aid >= 0
                highlight: true
                implicitHeight: 36
                anchors.verticalCenter: parent.verticalCenter
                onClicked: { toast.opacity = 0; core.run(toast.aid) }
            }
        }
        Timer { id: toastTimer; interval: 5000; onTriggered: toast.opacity = 0 }
    }

    // ------------------------------------------------------------------ Ziehen von Produkten auf Listen
    Rectangle {
        id: dragProxy
        property alias text: dragText.text
        parent: Overlay.overlay
        z: 100
        visible: false
        radius: 10
        height: 38
        width: dragText.implicitWidth + 50
        color: theme.c.green
        Drag.dragType: Drag.Internal
        Drag.hotSpot.x: -14
        Drag.hotSpot.y: -10
        Row {
            anchors.centerIn: parent
            spacing: 8
            Icon { name: "box"; size: 18; color: theme.c.onAccent; anchors.verticalCenter: parent.verticalCenter }
            AppText { id: dragText; color: theme.c.onAccent; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter }
        }
    }
    property alias dragItem: dragProxy

    // ------------------------------------------------------------------ Dialoge
    Component { id: msgComp; MessageDialog { } }
    Component { id: menuComp; ActionMenu { } }
    AddToListDialog { id: addDialog }
    ExportDialog { id: exportDialog }
    CategoryDialog { id: categoryDialog }
    SettingsDialog { id: settingsDialog }
    PasteDialog { id: pasteDialog }
    ColumnsDialog { id: columnsDialog }
    PaletteDialog { id: paletteDialog }
    CompareDialog { id: compareDialog }
    PickerDialog { id: pickerDialog }
    ProgressDialog { }

    Connections {
        target: core
        function onToastRequested(text, actionText, aid) {
            toastText.text = text
            toastBtn.text = actionText
            toast.aid = actionText ? aid : -1
            toast.opacity = 1
            toastTimer.restart()
        }
        function onDialogRequested(spec) { msgComp.createObject(root, { spec: spec }).open() }
        function onMenuRequested(spec) {
            var m = menuComp.createObject(root, { spec: spec })
            m.closed.connect(function () { Qt.callLater(m.destroy) })
            m.popup()
        }
        function onFocusRequested(what) {
            if (what === "search") { searchField.forceActiveFocus(); searchField.selectAll() }
            else productsPage.focusPart(what)
        }
    }
    Connections { target: lists; function onAddRequested(info) { addDialog.openWith(info) } }
    Connections {
        target: maint
        function onExportRequested(info) { exportDialog.openWith(info) }
        function onCategoriesRequested() { categoryDialog.open() }
        function onSettingsRequested() { settingsDialog.open() }
        function onPasteRequested(text) { pasteDialog.openWith(text) }
        function onColumnsRequested() { columnsDialog.open() }
        function onPaletteRequested() { paletteDialog.openFresh() }
    }
    Connections { target: compare; function onOpened() { compareDialog.open() } }
    Connections { target: picker; function onOpened() { pickerDialog.openFresh() } }

    // ------------------------------------------------------------------ Tastenkürzel
    Shortcut { sequence: "Ctrl+F"; onActivated: core.requestFocus("search") }
    Shortcut { sequence: "Ctrl+G"; onActivated: core.requestFocus("tree") }
    Shortcut { sequence: "Ctrl+H"; onActivated: core.requestFocus("hersteller") }
    Shortcut { sequence: "Ctrl+D"; onActivated: products.toggleSelectedFav() }
    Shortcut { sequence: "Ctrl+B"; onActivated: products.showFavorites() }
    Shortcut { sequence: "Ctrl+N"; onActivated: core.requestFocus("note") }
    Shortcut { sequence: "Ctrl+I"; enabled: !core.readOnly; onActivated: maint.startImport() }
    Shortcut { sequence: "Ctrl+E"; onActivated: maint.startExport() }
    Shortcut { sequence: "Ctrl+K"; onActivated: maint.openPalette() }
    Shortcut { sequence: "Ctrl+Z"; onActivated: core.undo() }
    Shortcut { sequence: "Ctrl+Shift+V"; onActivated: maint.openPaste() }
    Shortcut { sequence: "Ctrl+0"; onActivated: core.goto(2) }
    Shortcut { sequence: "Ctrl+1"; onActivated: core.goto(0) }
    Shortcut { sequence: "Ctrl+2"; onActivated: core.goto(1) }
    Shortcut { sequence: "Ctrl+3"; onActivated: core.goto(3) }
    Shortcut { sequence: "F5"; onActivated: core.reload() }
    Shortcut { sequence: "F1"; onActivated: maint.help() }

    // ------------------------------------------------------------------ Einrichtung beim ersten Start
    SetupPage {
        parent: Overlay.overlay
        anchors.fill: parent
        z: 200
        visible: core.setupNeeded
    }
}
