import QtQuick

// macOS-style pop-up button: shows the current choice; the menu opens over it with the current item
// under the pointer, so a click-drag-release picks in one motion.
Item {
    id: pb
    property var options: []          // [{label, value, desc}]
    property var value
    property real minWidth: 90
    signal selected(var value)
    activeFocusOnTab: true
    opacity: enabled ? 1 : 0.42
    implicitHeight: 28
    implicitWidth: Math.max(minWidth, lab.implicitWidth + 44)

    readonly property int index: {
        for (let i = 0; i < options.length; ++i) if (options[i].value === value) return i
        return 0
    }

    Rectangle {
        anchors.fill: parent; anchors.margins: -3.5
        radius: 12; color: "transparent"
        border.width: 2.5; border.color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.55)
        visible: pb.activeFocus && !menu.opened
    }
    Item {
        anchors.fill: parent
        scale: Theme.reduceMotion ? 1 : (ma.pressed ? 0.97 : ma.containsMouse ? 1.02 : 1)
        Behavior on scale { SpringAnimation { spring: 6; damping: 0.4; epsilon: 0.0015 } }
        Glass {
            anchors.fill: parent
            anchors.margins: -5
            inset: 5
            radius: 10
            bezel: 7
            refraction: 0
            tint: Theme.dark ? Qt.rgba(1, 1, 1, ma.containsMouse ? 0.15 : 0.10)
                             : Qt.rgba(1, 1, 1, ma.containsMouse ? 0.95 : 0.82)
            shadow: Theme.dark ? 0.25 : 0.10
            shadowSize: 4
            lift: ma.pressed ? 0.8 : 0
        }
        Label {
            id: lab
            x: 11
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - 40
            text: pb.options.length ? pb.options[pb.index].label : ""
            textStyle: "body"
            elide: Text.ElideRight
        }
        Rectangle {
            width: 18; height: 18; radius: 5
            anchors.right: parent.right; anchors.rightMargin: 5
            anchors.verticalCenter: parent.verticalCenter
            color: Theme.accentFill
            Icon { anchors.centerIn: parent; name: "chevron.updown"; size: 13; weight: 1.8; color: "#ffffff" }
        }
    }
    MouseArea {
        id: ma
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onPressed: { pb.forceActiveFocus(); pb.openMenu() }
    }
    Keys.onSpacePressed: openMenu()
    Keys.onReturnPressed: openMenu()

    function openMenu() {
        menu.items = options.map((o) => ({ label: o.label, value: o.value, desc: o.desc || "", checked: o.value === value }))
        menu.current = index
        menu.y = -menu.rowY(index) - 5 + (height - (options[index] && options[index].desc ? 42 : menu.itemH)) / 2
        menu.x = -8
        menu.open()
    }
    GlassMenu {
        id: menu
        checkable: true
        onTriggered: (item) => { if (item.value !== pb.value) pb.selected(item.value) }
    }
}
