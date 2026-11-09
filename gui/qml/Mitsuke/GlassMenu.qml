import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic as C

// Menu on thick, blurred Liquid Glass that refracts the window beneath it. Items:
// {label, value, desc, checked, icon, shortcut, destructive, separator: true}. It lives inside the window,
// so it moves with it and closes on outside clicks, Escape, or when the window is deactivated.
C.Popup {
    id: menu
    property var items: []
    property bool checkable: false
    property int current: -1
    signal triggered(var item)
    readonly property var hostWindow: parent ? parent.Window.window : null

    padding: 5
    margins: 8
    focus: true
    closePolicy: C.Popup.CloseOnEscape | C.Popup.CloseOnPressOutside
    // width from the real text (a Column can't size itself from children that take its width)
    width: Math.max(160, Math.min(380, contentW + 10))
    readonly property real contentW: {
        let w = 0
        const lead = checkable || items.some((d) => d.icon) ? 26 : 10
        for (let i = 0; i < items.length; ++i) {
            const d = items[i]
            if (d.separator) continue
            mLabel.text = d.label || ""
            mDesc.text = d.desc || ""
            mShort.text = d.shortcut || ""
            w = Math.max(w, lead + Math.max(mLabel.advanceWidth, mDesc.advanceWidth) + (d.shortcut ? mShort.advanceWidth + 24 : 0) + 20)
        }
        return Math.ceil(w)
    }
    TextMetrics { id: mLabel; font.family: Theme.textFamily; font.pointSize: 0.75 * Theme.body }
    TextMetrics { id: mDesc; font.family: Theme.textFamily; font.pointSize: 0.75 * Theme.footnote }
    TextMetrics { id: mShort; font.family: Theme.textFamily; font.pointSize: 0.75 * Theme.subhead }
    readonly property real itemH: 28

    function rowY(i) {
        let y = 0
        for (let k = 0; k < i && k < items.length; ++k) y += items[k].separator ? 11 : (items[k].desc ? 42 : itemH)
        return y
    }

    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast; easing.type: Easing.OutCubic }
            NumberAnimation { property: "scale"; from: Theme.reduceMotion ? 1 : 0.94; to: 1; duration: Theme.normal; easing.type: Easing.OutBack; easing.overshoot: 1.2 }
        }
    }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.fast } }

    Connections {   // the window lost focus (another app was clicked): close like a native menu
        target: menu.hostWindow
        function onActiveChanged() { if (!menu.hostWindow.active) menu.close() }
    }

    background: Item {
        Glass {
            anchors.fill: parent
            anchors.margins: -14
            inset: 14
            radius: 13
            bezel: 10
            refraction: 9
            blur: Theme.reduceTransparency ? 0 : 20
            dispersion: 0.18
            saturation: 1.6
            backdrop: menu.hostWindow && menu.hostWindow.sceneTex ? menu.hostWindow.sceneTex : null
            backdropItem: menu.hostWindow && menu.hostWindow.sceneItem ? menu.hostWindow.sceneItem : null
            tint: Theme.menuTint
            shadow: Theme.dark ? 0.55 : 0.22
            shadowSize: 18
        }
    }

    contentItem: Column {
        id: col
        Repeater {
            model: menu.items
            delegate: Loader {
                width: col.width
                sourceComponent: modelData.separator ? sepC : itemC
                property var d: modelData
                property int i: index
            }
        }
    }

    Component {
        id: sepC
        Item {
            implicitWidth: 10; height: 11
            Rectangle { x: 10; width: parent.width - 20; height: 1; anchors.verticalCenter: parent.verticalCenter; color: Theme.separator }
        }
    }
    Component {
        id: itemC
        Item {
            id: it
            readonly property bool hot: hov.hovered || menu.current === i
            implicitWidth: lead.width + Math.max(txt.implicitWidth, descText.implicitWidth) + (sc.text ? sc.implicitWidth + 24 : 0) + 34
            height: d.desc ? 42 : menu.itemH
            opacity: d.enabled === false ? 0.4 : 1
            Rectangle {
                anchors.fill: parent
                radius: 7
                color: d.destructive ? Theme.red : Theme.accentFill
                opacity: it.hot && d.enabled !== false ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: 70 } }
            }
            Item {
                id: lead
                width: menu.checkable || d.icon ? 26 : 10
                height: parent.height
                Icon {
                    anchors.centerIn: parent
                    visible: menu.checkable ? !!d.checked : !!d.icon
                    name: menu.checkable ? "checkmark" : (d.icon || "")
                    size: menu.checkable ? 13 : 14
                    weight: menu.checkable ? 2.0 : 1.6
                    color: it.hot ? "#ffffff" : (d.destructive ? Theme.red : Theme.label)
                }
            }
            Column {
                x: lead.width
                anchors.verticalCenter: parent.verticalCenter
                Label {
                    id: txt
                    text: d.label
                    textStyle: "body"
                    color: it.hot ? "#ffffff" : (d.destructive ? Theme.red : Theme.label)
                }
                Label {
                    id: descText
                    width: it.width - lead.width - 10
                    elide: Text.ElideRight
                    visible: !!d.desc
                    text: d.desc || ""
                    textStyle: "footnote"
                    color: it.hot ? Qt.rgba(1, 1, 1, 0.8) : Theme.label3
                }
            }
            Label {
                id: sc
                anchors.right: parent.right; anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                text: d.shortcut || ""
                textStyle: "subhead"
                color: it.hot ? Qt.rgba(1, 1, 1, 0.8) : Theme.label3
            }
            HoverHandler { id: hov; onHoveredChanged: if (hovered) menu.current = i }
            TapHandler {
                enabled: d.enabled !== false
                onTapped: { menu.triggered(d); menu.close() }
            }
        }
    }

    function _step(dir) {
        let i = current
        for (let n = 0; n < items.length; ++n) {
            i = (i + dir + items.length) % items.length
            if (!items[i].separator && items[i].enabled !== false) { current = i; return }
        }
    }
    onOpened: { if (current < 0) current = -1; col.forceActiveFocus() }
    onClosed: current = -1
    Shortcut { sequence: "Down"; enabled: menu.opened; onActivated: menu._step(1) }
    Shortcut { sequence: "Up"; enabled: menu.opened; onActivated: menu._step(-1) }
    Shortcut {
        sequences: ["Return", "Enter", "Space"]
        enabled: menu.opened && menu.current >= 0
        onActivated: { menu.triggered(menu.items[menu.current]); menu.close() }
    }
}
