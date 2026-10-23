import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// Fortschritt bei Import und Export (läuft im Hintergrund, Fenster bleibt bedienbar gesperrt)
AppDialog {
    id: dlg
    title: maint.busyTitle
    iconName: "refresh"
    preferredWidth: 560
    closePolicy: Popup.NoAutoClose
    visible: maint.busy

    AppText { Layout.fillWidth: true; text: maint.busyText; wrapMode: Text.WordWrap; elide: Text.ElideNone }
    ProgressBar {
        id: bar
        Layout.fillWidth: true
        from: 0
        to: Math.max(1, maint.busyMax)
        value: maint.busyValue
        indeterminate: maint.busyMax === 0
        background: Rectangle { implicitHeight: 12; radius: 6; color: theme.c.mint }
        contentItem: Item {
            implicitHeight: 12
            Rectangle {
                width: bar.indeterminate ? parent.width * 0.3 : bar.visualPosition * parent.width
                height: parent.height
                radius: 6
                color: theme.c.green
                x: bar.indeterminate ? slide.x : 0
            }
            Item {
                id: slide
                SequentialAnimation on x {
                    running: bar.indeterminate && dlg.visible
                    loops: Animation.Infinite
                    NumberAnimation { from: 0; to: bar.width * 0.7; duration: 900; easing.type: Easing.InOutQuad }
                    NumberAnimation { from: bar.width * 0.7; to: 0; duration: 900; easing.type: Easing.InOutQuad }
                }
            }
        }
    }
    AppText { text: "Bitte warten – das kann einen Moment dauern."; color: theme.c.muted; rel: 0.9 }
}
