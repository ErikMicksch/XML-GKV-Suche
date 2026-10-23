import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// Allgemeiner Dialog aus Python (core.ask): Text (HTML, Links), optionales Eingabefeld, Knöpfe
AppDialog {
    id: dlg
    property var spec: ({})
    property bool answered: false
    title: spec.title || ""
    iconName: spec.icon || ""
    danger: spec.danger === true
    preferredWidth: spec.wide ? 820 : 580
    maxHeight: 760

    function finish(button) {
        if (answered) return
        answered = true
        core.answer(spec.id, button, input.text)
        close()
    }
    onClosed: { if (!answered) { answered = true; core.answer(spec.id, "", "") } Qt.callLater(dlg.destroy) }
    onOpened: if (spec.hasInput) input.forceActiveFocus()

    ScrollView {
        id: scroll
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.preferredHeight: Math.min(textItem.implicitHeight + 8, 520)
        visible: (spec.text || "") !== ""
        clip: true
        contentWidth: availableWidth
        HtmlText {
            id: textItem
            width: scroll.availableWidth
            text: spec.text || ""
            onLinkActivated: (link) => { dlg.answered = true; core.link(dlg.spec.id, link); dlg.close() }
        }
    }
    AppText {
        visible: spec.hasInput === true
        Layout.fillWidth: true
        text: spec.inputLabel || ""
        font.weight: Font.DemiBold
        wrapMode: Text.WordWrap
        elide: Text.ElideNone
    }
    Field {
        id: input
        visible: spec.hasInput === true
        Layout.fillWidth: true
        text: spec.inputText || ""
        placeholderText: spec.placeholder || ""
        Keys.onReturnPressed: {
            var b = (dlg.spec.buttons || []).filter(x => x.primary && !x.danger)
            dlg.finish(b.length ? b[0].id : "ok")
        }
    }

    buttons: Repeater {
        model: dlg.spec.buttons || []
        Btn {
            text: modelData.text
            primary: modelData.primary && !modelData.danger
            danger: modelData.danger === true
            onClicked: dlg.finish(modelData.id)
            Component.onCompleted: if (modelData.primary && !dlg.spec.hasInput) forceActiveFocus()
        }
    }
}
