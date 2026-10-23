import QtQuick
import QtQuick.Controls

// Kontextmenü aus einer Liste von Python: [{text, icon, aid, enabled, separator, children}]
AppMenu {
    id: m
    property var spec: []

    Component { id: itemComp; MItem { property int aid: -1; onTriggered: if (aid >= 0) Qt.callLater(core.run, aid) } }
    Component { id: sepComp; MSep { } }

    Component.onCompleted: {
        for (var i = 0; i < spec.length; i++) {
            var e = spec[i]
            if (e.separator)
                m.addItem(sepComp.createObject(m.contentItem))
            else if (e.children && e.children.length)
                m.addMenu(Qt.createComponent("ActionMenu.qml").createObject(m.contentItem, { title: e.text, spec: e.children }))
            else
                m.addItem(itemComp.createObject(m.contentItem, { text: e.text, aid: e.aid, iconName: e.icon || "", enabled: e.enabled }))
        }
    }
}
