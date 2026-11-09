import QtQuick

// On/off switch. At rest the knob is a white pill; touched, it lifts into a clear glass lens that magnifies
// and refracts the track under it, and follows the pointer. Dragging past the middle flips the value
// immediately (live), a click toggles.
Item {
    id: sw
    property bool checked: false
    signal toggled(bool value)
    activeFocusOnTab: true
    implicitWidth: 44
    implicitHeight: 26
    opacity: enabled ? 1 : 0.42

    property real lift: ma.pressed ? 1 : 0
    HoverHandler { id: swHover }
    property real hover: swHover.hovered && enabled ? 1 : 0
    Behavior on hover { NumberAnimation { duration: Theme.dur(160); easing.type: Easing.OutCubic } }
    Behavior on lift { SpringAnimation { spring: 4.2; damping: 0.38; epsilon: 0.004 } }
    property real dragX: -1                      // knob centre while dragging, -1 = follow the value
    readonly property real knobW: 22 + 9 * lift
    readonly property real knobH: 22
    readonly property real restX: checked ? width - 2 - knobW / 2 : 2 + knobW / 2
    readonly property real knobX: dragX >= 0 ? Math.max(2 + knobW / 2, Math.min(width - 2 - knobW / 2, dragX)) : restX

    // the owner binds `checked` to its model and writes the model in onToggled, so bindings survive
    function set(v) { if (v !== checked) toggled(v) }

    Rectangle {    // focus ring
        anchors.fill: parent; anchors.margins: -3.5
        radius: height / 2; color: "transparent"
        border.width: 2.5; border.color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.55)
        visible: sw.activeFocus
    }

    Item {
        id: trackLayer
        anchors.fill: parent
        Rectangle {
            anchors.fill: parent
            radius: height / 2
            color: sw.checked ? Theme.accentFill : Theme.trackOff
            Behavior on color { ColorAnimation { duration: Theme.normal; easing.type: Easing.OutCubic } }
            border.width: Theme.highContrast ? 1 : 0
            border.color: Theme.edge
        }
        Rectangle {   // a soft inner shade so the track reads as recessed
            anchors.fill: parent
            radius: height / 2
            gradient: Gradient {
                GradientStop { position: 0; color: Qt.rgba(0, 0, 0, Theme.dark ? 0.16 : 0.07) }
                GradientStop { position: 0.5; color: "transparent" }
            }
        }
    }
    ShaderEffectSource { id: trackTex; sourceItem: trackLayer; live: true; visible: false; hideSource: false }

    Glass {
        id: knob
        width: sw.knobW * (1 + 0.16 * sw.lift) + 12
        height: sw.knobH * (1 + 0.16 * sw.lift) + 12
        x: sw.knobX - width / 2
        y: (sw.height - height) / 2
        inset: 6
        radius: height
        bezel: 7 + 4 * sw.lift
        refraction: 5 + 7 * sw.lift
        zoom: 1 + 0.16 * sw.lift
        dispersion: 0.2 * sw.lift
        base: Theme.panelBase
        backdrop: trackTex
        backdropItem: trackLayer
        tint: Qt.rgba(1, 1, 1, Math.max(0.03, 1 - 1.15 * sw.lift))
        specular: 0.6 + 0.25 * sw.hover + 0.6 * sw.lift
        shadow: Theme.dark ? 0.38 : 0.22
        shadowSize: 5 + 3 * sw.lift
        edge: 0.25 + 0.5 * sw.lift
        lift: sw.lift
        scale: Theme.reduceMotion ? 1 : 1 + 0.05 * sw.hover * (1 - sw.lift)
        Behavior on x { enabled: sw.dragX < 0; SpringAnimation { spring: 4.5; damping: 0.45; epsilon: 0.05 } }
    }

    MouseArea {
        id: ma
        anchors.fill: parent
        anchors.margins: -4
        cursorShape: Qt.PointingHandCursor
        property real pressX: 0
        property bool moved: false
        onPressed: (m) => { pressX = m.x; moved = false; sw.forceActiveFocus() }
        onPositionChanged: (m) => {
            if (!pressed) return
            if (Math.abs(m.x - pressX) > 3) moved = true
            if (moved) {
                sw.dragX = m.x - 4
                sw.set(sw.dragX > sw.width / 2)        // live: flips the moment the knob crosses the middle
            }
        }
        onReleased: { if (!moved) sw.set(!sw.checked); sw.dragX = -1 }
        onCanceled: sw.dragX = -1
    }
    Keys.onSpacePressed: set(!checked)
}
