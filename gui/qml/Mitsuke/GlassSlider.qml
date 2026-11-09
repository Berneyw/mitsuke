import QtQuick

// Slider with a translucent track and a dimensional glass knob. Grabbed, the knob swells into a clear lens
// that magnifies and bends the track beneath it and follows the pointer exactly; the value (and everything
// bound to it) updates continuously while dragging, then the knob settles on the nearest step with a spring.
Item {
    id: s
    property real from: 0
    property real to: 100
    property real stepSize: 1
    property real value: 0
    property string unit: ""
    readonly property real frac: (Math.max(from, Math.min(to, value)) - from) / Math.max(1e-6, to - from)
    signal moved(real value)          // continuously while dragging / on clicks and keys
    signal committed(real value)      // when the interaction ends
    activeFocusOnTab: true
    implicitWidth: 200
    implicitHeight: 30
    opacity: enabled ? 1 : 0.42

    readonly property bool dragging: ma.pressed
    property real lift: dragging ? 1 : (ma.containsMouse ? 0.12 : 0)
    Behavior on lift { SpringAnimation { spring: 3.8; damping: 0.36; epsilon: 0.004 } }

    readonly property real knobRestW: 30 + 2 * lift
    readonly property real knobRestH: 20
    readonly property real pad: 15                  // fixed: the track must not shift while the thumb swells
    readonly property real span: Math.max(1, width - 2 * pad)
    property real dragPos: -1                       // knob centre while dragging
    readonly property real valuePos: pad + span * (Math.max(from, Math.min(to, value)) - from) / Math.max(1e-6, to - from)
    property real shownPos: dragPos >= 0 ? dragPos : valuePos
    Behavior on shownPos { enabled: s.dragPos < 0 && !s._jump; SpringAnimation { spring: 5; damping: 0.5; epsilon: 0.1 } }
    property bool _jump: false

    readonly property int steps: Math.round((to - from) / Math.max(1e-6, stepSize))

    function snap(v) {
        const k = Math.round((v - from) / stepSize)
        return Math.max(from, Math.min(to, from + k * stepSize))
    }
    function valueAt(px) { return snap(from + (px - pad) / span * (to - from)) }
    function emitValue(v) { if (Math.abs(v - value) > 1e-9) { moved(v) } }

    Rectangle {     // focus ring around the knob track
        anchors.fill: parent; anchors.margins: -2
        radius: 10; color: "transparent"
        border.width: 2.5; border.color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.45)
        visible: s.activeFocus && !s.dragging
    }

    Item {
        id: trackLayer
        anchors.fill: parent
        Rectangle {          // track
            id: track
            x: s.pad - 3; width: s.span + 6
            height: 6; radius: 3
            anchors.verticalCenter: parent.verticalCenter
            color: Theme.trackOff
        }
        Rectangle {          // glow under the fill: grows with the value and while dragging
            x: track.x - 2
            width: Math.max(10, s.shownPos - track.x + 4)
            height: 12; radius: 6
            anchors.verticalCenter: parent.verticalCenter
            color: Theme.accentFill
            opacity: (0.10 + 0.22 * s.frac) * (0.5 + 0.5 * s.lift)
        }
        Rectangle {          // fill: deeper at the start, brighter toward the thumb
            x: track.x
            width: Math.max(6, s.shownPos - track.x)
            height: 6; radius: 3
            anchors.verticalCenter: parent.verticalCenter
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Qt.darker(Theme.accentFill, 1.18 - 0.12 * s.frac) }
                GradientStop { position: 1; color: Qt.lighter(Theme.accentFill, 1.0 + 0.22 * s.frac + 0.12 * s.lift) }
            }
        }
        Repeater {           // ticks for short ranges; the ones already passed light up
            model: s.steps > 0 && s.steps <= 12 ? s.steps + 1 : 0
            Rectangle {
                readonly property real px: s.pad + s.span * index / s.steps
                readonly property bool passed: px <= s.shownPos + 0.5
                width: 3; height: 3; radius: 1.5
                x: px - 1.5
                y: parent.height / 2 + 7
                color: passed ? Theme.accent : Theme.label4
                scale: passed ? 1.15 : 1
                Behavior on color { ColorAnimation { duration: Theme.fast } }
                Behavior on scale { NumberAnimation { duration: Theme.fast } }
            }
        }
    }
    ShaderEffectSource { id: tex; sourceItem: trackLayer; live: true; visible: false }

    Glass {
        id: knob
        readonly property real kw: s.knobRestW + 18 * s.lift
        readonly property real kh: s.knobRestH + 10 * s.lift
        width: kw + 14; height: kh + 14
        x: s.shownPos - width / 2
        y: (s.height - height) / 2
        inset: 7
        radius: height
        bezel: 7 + 7 * s.lift
        refraction: 4 + 10 * s.lift
        zoom: 1 + 0.22 * s.lift
        dispersion: 0.22 * s.lift
        base: Theme.panelBase
        backdrop: tex
        backdropItem: trackLayer
        tint: Qt.rgba(1, 1, 1, Math.max(0.02, 1 - 1.2 * s.lift))
        specular: 0.55 + 0.7 * s.lift
        shadow: Theme.dark ? 0.40 : 0.22
        shadowSize: 5 + 4 * s.lift
        edge: 0.22 + 0.55 * s.lift
        lift: s.lift
    }

    Item {                   // the value floats above the thumb while you drag (and on hover)
        id: bubble
        readonly property bool on: s.dragging || (ma.containsMouse && s.lift > 0.05)
        x: s.shownPos - width / 2
        y: -height - 2
        width: valText.implicitWidth + 18; height: 22
        opacity: on ? 1 : 0
        scale: on ? 1 : (Theme.reduceMotion ? 1 : 0.8)
        transformOrigin: Item.Bottom
        Behavior on opacity { NumberAnimation { duration: Theme.fast } }
        Behavior on scale { SpringAnimation { spring: 5; damping: 0.45; epsilon: 0.002 } }
        visible: opacity > 0.01
        Glass {
            anchors.fill: parent; anchors.margins: -6; inset: 6
            radius: height; bezel: 6; refraction: 0
            tint: Theme.menuTint
            shadow: Theme.dark ? 0.4 : 0.16; shadowSize: 6
        }
        Label {
            id: valText
            anchors.centerIn: parent
            text: Math.round(s.dragging ? s.valueAt(s.dragPos) : s.value) + (s.unit ? " " + s.unit : "")
            textStyle: "subhead"
            font.weight: Font.DemiBold
            font.features: { "tnum": 1 }
        }
    }

    MouseArea {
        id: ma
        anchors.fill: parent
        anchors.topMargin: -6; anchors.bottomMargin: -6
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        property real grabOffset: 0
        onPressed: (m) => {
            s.forceActiveFocus()
            const onKnob = Math.abs(m.x - s.valuePos) <= s.knobRestW / 2 + 4
            grabOffset = onKnob ? s.valuePos - m.x : 0
            s.dragPos = Math.max(s.pad, Math.min(s.pad + s.span, m.x + grabOffset))
            s.emitValue(s.valueAt(s.dragPos))
        }
        onPositionChanged: (m) => {
            if (!pressed) return
            s.dragPos = Math.max(s.pad, Math.min(s.pad + s.span, m.x + grabOffset))
            s.emitValue(s.valueAt(s.dragPos))
        }
        onReleased: { s.dragPos = -1; s.committed(s.value) }
        onCanceled: { s.dragPos = -1; s.committed(s.value) }
        onWheel: (w) => {
            const v = s.snap(s.value + (w.angleDelta.y > 0 ? s.stepSize : -s.stepSize))
            s.emitValue(v); s.committed(v)
        }
    }
    Keys.onLeftPressed: { const v = snap(value - stepSize); emitValue(v); committed(v) }
    Keys.onRightPressed: { const v = snap(value + stepSize); emitValue(v); committed(v) }
}
