import QtQuick

// Floating glass sidebar: app identity, navigation with a selection lozenge that glides between items
// (with a review badge on My Words), and the scanning status card with its switch.
Item {
    id: sb
    property string page: "lookup"
    signal navigate(string key)
    signal dragStarted()

    readonly property var pages: [
        { key: "lookup", label: "Lookup", icon: "search", shortcut: "Ctrl+1" },
        { key: "words", label: "My Words", icon: "star", shortcut: "Ctrl+2" },
        { key: "dictionary", label: "Dictionary", icon: "book", shortcut: "Ctrl+3" },
        { key: "settings", label: "Settings", icon: "gear", shortcut: "Ctrl+4" }
    ]
    readonly property int sel: {
        for (let i = 0; i < pages.length; ++i) if (pages[i].key === page) return i
        return 0
    }

    Glass {
        anchors.fill: parent
        anchors.margins: -16
        inset: 16
        radius: 20
        bezel: 14
        refraction: 0
        tint: Theme.reduceTransparency ? (Theme.dark ? "#26262a" : "#ececf0")
                                       : (Theme.dark ? Qt.rgba(0.20, 0.20, 0.23, 0.42) : Qt.rgba(1, 1, 1, 0.55))
        specular: Theme.specular * 0.8
        shadow: Theme.dark ? 0.42 : 0.14
        shadowSize: 16
        edge: Theme.glassEdge
    }

    MouseArea {       // the empty top of the sidebar moves the window
        width: parent.width; height: 74
        onPressed: sb.dragStarted()
    }
    Row {
        x: 16; y: 18
        spacing: 11
        AppIcon { size: 36 }
        Column {
            anchors.verticalCenter: parent.verticalCenter
            Label { text: "Mitsuke"; textStyle: "headline"; font.pointSize: 0.75 * (14.5) }
            Label { text: "German in-game lookup"; textStyle: "footnote"; color: Theme.label3 }
        }
    }

    Item {
        id: nav
        x: 10; y: 78
        width: parent.width - 20
        height: sb.pages.length * 36

        Glass {        // the selection: glides between items with a spring
            id: selGlass
            width: nav.width + 12
            height: 34 + 12
            x: -6
            y: sb.sel * 36 - 6
            inset: 6
            radius: 11
            bezel: 8
            refraction: 0
            tint: Theme.dark ? Qt.rgba(1, 1, 1, 0.13) : Qt.rgba(1, 1, 1, 0.85)
            specular: Theme.specular * 0.9
            shadow: Theme.dark ? 0.25 : 0.08
            shadowSize: 6
            Behavior on y { SpringAnimation { spring: 4.2; damping: 0.42; epsilon: 0.05 } }
        }
        Repeater {
            model: sb.pages
            delegate: Item {
                id: navItem
                y: index * 36
                width: nav.width
                height: 34
                readonly property bool selected: index === sb.sel
                scale: Theme.reduceMotion ? 1 : (tap.pressed ? 0.97 : 1)
                Behavior on scale { SpringAnimation { spring: 6; damping: 0.4; epsilon: 0.0015 } }
                Rectangle {
                    anchors.fill: parent
                    radius: 10
                    color: Theme.controlFill
                    opacity: hov.hovered && !navItem.selected ? 0.8 : 0
                    Behavior on opacity { NumberAnimation { duration: 100 } }
                }
                Icon {
                    x: 11
                    anchors.verticalCenter: parent.verticalCenter
                    name: modelData.icon
                    size: 17
                    weight: 1.7
                    color: navItem.selected ? Theme.accent : Theme.label2
                    Behavior on color { ColorAnimation { duration: Theme.fast } }
                }
                Label {
                    x: 38
                    anchors.verticalCenter: parent.verticalCenter
                    text: modelData.label
                    textStyle: "body"
                    font.weight: navItem.selected ? Font.DemiBold : Font.Normal
                    color: Theme.label
                }
                Rectangle {        // badge: words due for review
                    readonly property int n: modelData.key === "words" ? (App.state.due || 0) : 0
                    visible: n > 0
                    anchors.right: parent.right; anchors.rightMargin: 9
                    anchors.verticalCenter: parent.verticalCenter
                    height: 18; width: Math.max(18, badgeText.implicitWidth + 11)
                    radius: 9
                    color: Theme.accentFill
                    Label {
                        id: badgeText
                        anchors.centerIn: parent
                        text: String(parent.n)
                        textStyle: "caption"
                        font.weight: Font.Bold
                        color: "#ffffff"
                    }
                }
                HoverHandler { id: hov }
                TapHandler { id: tap; onTapped: sb.navigate(modelData.key) }
                ToolTipLite { text: modelData.label + "  (" + modelData.shortcut + ")"; shown: hov.hovered }
            }
        }
    }

    // ---- status card
    Item {
        id: status
        x: 10
        width: parent.width - 20
        height: statusCol.implicitHeight + 24
        anchors.bottom: parent.bottom; anchors.bottomMargin: 10
        readonly property string kind: App.state.statusKind || "ok"
        readonly property color dot: kind === "ok" ? Theme.green : kind === "paused" ? Theme.yellow : Theme.red
        Glass {
            anchors.fill: parent
            anchors.margins: -8
            inset: 8
            radius: 14
            bezel: 9
            refraction: 0
            tint: Theme.dark ? Qt.rgba(1, 1, 1, 0.07) : Qt.rgba(1, 1, 1, 0.6)
            specular: Theme.specular * 0.6
            shadow: Theme.dark ? 0.2 : 0.06
            shadowSize: 6
        }
        Column {
            id: statusCol
            x: 12; y: 12
            width: parent.width - 24
            spacing: 3
            Item {
                width: parent.width; height: 26
                Rectangle {     // status dot with a soft glow
                    id: dot
                    width: 9; height: 9; radius: 4.5
                    anchors.verticalCenter: parent.verticalCenter
                    color: status.dot
                    Rectangle {
                        anchors.centerIn: parent
                        width: 17; height: 17; radius: 8.5
                        color: status.dot
                        opacity: 0.22
                        SequentialAnimation on opacity {
                            running: status.kind === "ok" && !Theme.reduceMotion
                            loops: Animation.Infinite
                            NumberAnimation { to: 0.05; duration: 1400; easing.type: Easing.InOutSine }
                            NumberAnimation { to: 0.28; duration: 1400; easing.type: Easing.InOutSine }
                        }
                    }
                }
                Label {
                    x: 17
                    anchors.verticalCenter: parent.verticalCenter
                    text: App.state.statusTitle || ""
                    textStyle: "headline"
                }
                GlassSwitch {
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    checked: !!App.settings.enabled
                    onToggled: (v) => App.set("enabled", v)
                    ToolTipLite { text: "Turn scanning on or off"; shown: false }
                }
            }
            Label {
                width: parent.width
                text: App.state.statusDetail || ""
                textStyle: "footnote"
                color: Theme.label3
                wrapMode: Text.WordWrap
            }
        }
    }
}
