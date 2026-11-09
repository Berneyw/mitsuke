import QtQuick

// Segmented control. The selection is a glass lozenge that glides between segments; while you drag it, it
// lifts into a lens over the labels (they magnify inside it) and the value changes as it passes each one.
Item {
    id: seg
    property var options: []          // [{label, value}]
    property var value
    signal selected(var value)
    activeFocusOnTab: true
    implicitHeight: 30
    implicitWidth: Math.max(180, options.length * 76)
    opacity: enabled ? 1 : 0.42

    readonly property int count: Math.max(1, options.length)
    readonly property real segW: (width - 4) / count
    readonly property int index: {
        for (let i = 0; i < options.length; ++i) if (options[i].value === value) return i
        return 0
    }
    property real dragX: -1
    property real lift: ma.pressed ? 1 : 0
    Behavior on lift { SpringAnimation { spring: 4; damping: 0.4; epsilon: 0.004 } }
    readonly property real thumbX: dragX >= 0 ? Math.max(2, Math.min(width - 2 - segW, dragX - segW / 2)) : 2 + index * segW

    function pick(i) {
        i = Math.max(0, Math.min(options.length - 1, i))
        if (options[i] && options[i].value !== value) selected(options[i].value)
    }

    Rectangle {
        anchors.fill: parent; anchors.margins: -3.5
        radius: height / 2; color: "transparent"
        border.width: 2.5; border.color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.55)
        visible: seg.activeFocus
    }

    Item {
        id: layer
        anchors.fill: parent
        Rectangle {
            anchors.fill: parent
            radius: height / 2
            color: Theme.controlFill
            border.width: Theme.highContrast ? 1 : 0
            border.color: Theme.edge
        }
        Repeater {                          // dividers between unselected neighbours
            model: seg.count - 1
            Rectangle {
                x: 2 + (index + 1) * seg.segW - 0.5
                width: 1; height: parent.height - 14
                anchors.verticalCenter: parent.verticalCenter
                color: Theme.separator
                opacity: (index === seg.index || index + 1 === seg.index) ? 0 : 1
                Behavior on opacity { NumberAnimation { duration: Theme.fast } }
            }
        }
        Rectangle {                         // hover: a faint pill under the segment the pointer is over
            readonly property int hi: segHover.hovered ? Math.max(0, Math.min(seg.count - 1, Math.floor((segHover.point.position.x - 2) / seg.segW))) : -1
            x: 2 + Math.max(0, hi) * seg.segW + 2
            width: seg.segW - 4; height: parent.height - 8
            anchors.verticalCenter: parent.verticalCenter
            radius: height / 2
            color: Theme.controlHover
            opacity: hi >= 0 && hi !== seg.index && !ma.pressed ? 1 : 0
            Behavior on x { NumberAnimation { duration: Theme.dur(160); easing.type: Easing.OutCubic } }
            Behavior on opacity { NumberAnimation { duration: Theme.fast } }
        }
        Repeater {
            model: seg.options
            Label {
                x: 2 + index * seg.segW
                width: seg.segW
                height: parent.height
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                text: modelData.label
                textStyle: "subhead"
                font.weight: index === seg.index ? Font.DemiBold : Font.Medium
                color: index === seg.index ? Theme.label : Theme.label2
                elide: Text.ElideRight
            }
        }
    }
    ShaderEffectSource { id: tex; sourceItem: layer; live: true; visible: false }

    Glass {
        id: thumb
        width: seg.segW + 10 + 8 * seg.lift
        height: seg.height - 4 + 10 + 6 * seg.lift
        x: seg.thumbX - 5 - 4 * seg.lift
        y: (seg.height - height) / 2
        inset: 5
        radius: height
        bezel: 6 + 6 * seg.lift
        refraction: 3 + 5 * seg.lift
        zoom: 1 + 0.12 * seg.lift
        dispersion: 0.12 * seg.lift
        base: Theme.panelBase
        backdrop: tex
        backdropItem: layer
        tint: Theme.dark ? Qt.rgba(0.42, 0.42, 0.46, Math.max(0.05, 0.62 - 0.6 * seg.lift))
                         : Qt.rgba(1, 1, 1, Math.max(0.05, 0.96 - 0.9 * seg.lift))
        specular: 0.5 + 0.6 * seg.lift
        shadow: Theme.dark ? 0.30 : 0.14
        shadowSize: 4 + 3 * seg.lift
        lift: seg.lift
        Behavior on x { enabled: seg.dragX < 0; SpringAnimation { spring: 4.2; damping: 0.42; epsilon: 0.05 } }
    }
    Label {                                 // the selected label stays crisp above the resting glass
        x: thumb.x + 5 + 4 * seg.lift
        width: seg.segW
        height: seg.height
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        text: seg.options.length ? seg.options[seg.index].label : ""
        textStyle: "subhead"
        font.weight: Font.DemiBold
        color: Theme.label
        opacity: seg.dragX < 0 ? 1 - seg.lift : 0
    }

    HoverHandler { id: segHover }
    MouseArea {
        id: ma
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        property bool moved: false
        property real px: 0
        onPressed: (m) => { px = m.x; moved = false; seg.forceActiveFocus() }
        onPositionChanged: (m) => {
            if (!pressed) return
            if (Math.abs(m.x - px) > 4) moved = true
            if (moved) { seg.dragX = m.x; seg.pick(Math.floor((m.x - 2) / seg.segW)) }
        }
        onReleased: (m) => { seg.pick(Math.floor((m.x - 2) / seg.segW)); seg.dragX = -1 }
        onCanceled: seg.dragX = -1
    }
    Keys.onLeftPressed: pick(index - 1)
    Keys.onRightPressed: pick(index + 1)
}
