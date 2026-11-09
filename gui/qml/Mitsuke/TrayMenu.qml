import QtQuick
import QtQuick.Window

// The tray icon's menu on Liquid Glass: it refracts a live picture of the desktop under it (like the word
// card), springs open from the tray corner, and closes when it loses focus, on Escape or after a choice.
Window {
    id: tm
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint
    color: "transparent"
    property int frame: 0
    property real minTint: 0
    property point pointer: hh.hovered ? hh.point.position : Qt.point(width, height + 200)
    property bool shown: false
    property int current: -1
    readonly property real margin: 22
    signal chosen(string action)
    width: 280 + 2 * margin
    height: col.implicitHeight + 12 + 2 * margin

    readonly property var st: App.state
    readonly property var items: [
        { action: "open", label: "Open Mitsuke", icon: "search", bold: true },
        { separator: true },
        { action: "toggle", label: App.settings.enabled ? "Pause Scanning" : "Resume Scanning",
          icon: App.settings.enabled ? "pause" : "play" },
        { action: "keys" },
        { action: "settings", label: "Settings…", icon: "gear" },
        { separator: true },
        { action: "quit", label: "Quit Mitsuke", icon: "xmark" }
    ]

    function close_() { shown = false; hideTimer.restart() }
    Timer { id: hideTimer; interval: Theme.dur(140); onTriggered: tm.hide() }
    onActiveChanged: if (!active && shown) close_()

    Image {
        id: bg
        anchors.fill: parent
        source: tm.frame > 0 ? "image://backdrop/tray/" + tm.frame : ""
        cache: false; asynchronous: false; mipmap: true; visible: false
    }
    HoverHandler { id: hh }

    Item {
        id: body
        x: tm.margin; y: tm.margin
        width: parent.width - 2 * tm.margin
        height: parent.height - 2 * tm.margin
        opacity: tm.shown ? 1 : 0
        scale: tm.shown ? 1 : (Theme.reduceMotion ? 1 : 0.94)
        transformOrigin: Item.BottomRight
        Behavior on opacity { NumberAnimation { duration: Theme.fast; easing.type: Easing.OutCubic } }
        Behavior on scale { SpringAnimation { spring: 5; damping: 0.42; epsilon: 0.001 } }

        Glass {
            anchors.fill: parent
            anchors.margins: -tm.margin
            inset: tm.margin
            radius: 14
            bezel: 12
            refraction: Theme.reduceTransparency ? 0 : 10
            blur: Theme.reduceTransparency ? 0 : 18
            dispersion: 0.2
            saturation: 1.6
            backdrop: tm.frame > 0 && !Theme.reduceTransparency ? bg : null
            backdropItem: bg
            tint: Qt.rgba(Theme.menuTint.r, Theme.menuTint.g, Theme.menuTint.b,
                          Theme.reduceTransparency ? 0.99 : Math.max(Theme.menuTint.a, tm.minTint))
            shadow: Theme.dark ? 0.55 : 0.25
            shadowSize: 18
        }

        Column {
            id: col
            x: 6; y: 6
            width: parent.width - 12

            // status header
            Row {
                x: 8
                height: 40
                spacing: 9
                AppIcon { size: 26; anchors.verticalCenter: parent.verticalCenter }
                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    Label { text: "Mitsuke " + App.version; textStyle: "headline" }
                    Row {
                        spacing: 5
                        Rectangle {
                            width: 7; height: 7; radius: 3.5
                            anchors.verticalCenter: parent.verticalCenter
                            color: tm.st.statusKind === "ok" ? Theme.green : tm.st.statusKind === "paused" ? Theme.yellow : Theme.red
                        }
                        Label {
                            text: (tm.st.statusTitle || "") + (tm.st.statusKind === "ok" ? " · hold " + (tm.st.keyName || "") : "")
                            textStyle: "footnote"; color: Theme.label3
                        }
                    }
                }
            }
            Item { width: 1; height: 4 }

            Repeater {
                model: tm.items
                delegate: Loader {
                    width: col.width
                    property var d: modelData
                    property int i: index
                    sourceComponent: d.separator ? sepC : d.action === "keys" ? keysC : itemC
                }
            }
        }
    }

    Component {
        id: sepC
        Item {
            height: 11
            Rectangle { x: 10; width: parent.width - 20; height: 1; anchors.verticalCenter: parent.verticalCenter; color: Theme.separator }
        }
    }
    Component {
        id: itemC
        Item {
            id: it
            height: 30
            readonly property bool hot: ih.hovered || tm.current === i
            Rectangle {
                anchors.fill: parent
                radius: 8
                color: d.action === "quit" ? Theme.red : Theme.accentFill
                opacity: it.hot ? 1 : 0
                scale: ita.pressed ? 0.98 : 1
                Behavior on opacity { NumberAnimation { duration: 70 } }
                Behavior on scale { SpringAnimation { spring: 6; damping: 0.45 } }
            }
            Icon {
                x: 10
                anchors.verticalCenter: parent.verticalCenter
                name: d.icon || ""
                size: 15
                color: it.hot ? "#ffffff" : (d.action === "quit" ? Theme.red : Theme.label2)
            }
            Label {
                x: 34
                anchors.verticalCenter: parent.verticalCenter
                text: d.label
                textStyle: "body"
                font.weight: d.bold ? Font.DemiBold : Font.Normal
                color: it.hot ? "#ffffff" : Theme.label
            }
            HoverHandler { id: ih; onHoveredChanged: if (hovered) tm.current = i }
            TapHandler { id: ita; onTapped: { tm.chosen(d.action); tm.close_() } }
        }
    }
    Component {
        id: keysC
        Item {
            height: 40
            Icon { x: 10; anchors.verticalCenter: parent.verticalCenter; name: "keyboard"; size: 15; color: Theme.label2 }
            Label { x: 34; anchors.verticalCenter: parent.verticalCenter; text: "Scan key"; textStyle: "body" }
            GlassSegmented {
                anchors.right: parent.right; anchors.rightMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                width: 150; height: 26
                options: [{ label: "Shift", value: "shift" }, { label: "Ctrl", value: "ctrl" }, { label: "Alt", value: "alt" }]
                value: App.settings.key
                onSelected: (v) => App.set("key", v)
            }
        }
    }

    Shortcut { sequence: "Escape"; onActivated: tm.close_() }
    Shortcut { sequence: "Down"; onActivated: tm.step(1) }
    Shortcut { sequence: "Up"; onActivated: tm.step(-1) }
    Shortcut {
        sequences: ["Return", "Enter"]
        onActivated: { if (tm.current >= 0) { tm.chosen(tm.items[tm.current].action); tm.close_() } }
    }
    function step(dir) {
        let k = current
        for (let n = 0; n < items.length; ++n) {
            k = (k + dir + items.length) % items.length
            if (!items[k].separator && items[k].action !== "keys") { current = k; return }
        }
    }
}
