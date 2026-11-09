import QtQuick

// Push button on Liquid Glass. kind: primary (tinted accent glass) | secondary (clear glass) |
// destructive | plain (text only). Icon-only buttons become circles. Presses squash with a spring and
// brighten the rim; keyboard focus shows a ring.
Item {
    id: b
    property string text: ""
    property string icon: ""
    property string kind: "secondary"
    property bool small: false
    property color iconColor: kind === "plain" ? Theme.accentText : _fg
    property string tip: ""
    property Item backdrop: null
    property Item backdropItem: null
    property real minWidth: 0
    readonly property bool pressed: ma.pressed
    readonly property bool hovered: ma.containsMouse
    signal clicked()

    activeFocusOnTab: true
    opacity: enabled ? 1 : 0.42
    implicitHeight: small ? 26 : 32
    implicitWidth: text ? Math.max(minWidth, row.implicitWidth + (small ? 22 : 30)) : implicitHeight

    readonly property color _fg: kind === "primary" || kind === "destructive" ? "#ffffff"
                                 : kind === "plain" ? Theme.accentText : Theme.label
    readonly property color _tint: {
        if (kind === "primary") return Qt.rgba(Theme.accentFill.r, Theme.accentFill.g, Theme.accentFill.b, hovered ? 0.98 : 0.9)
        if (kind === "destructive") return Qt.rgba(Theme.red.r, Theme.red.g, Theme.red.b, hovered ? 0.98 : 0.9)
        if (Theme.dark) return Qt.rgba(1, 1, 1, pressed ? 0.20 : hovered ? 0.16 : 0.11)
        return Qt.rgba(1, 1, 1, pressed ? 0.62 : hovered ? 0.92 : 0.80)
    }

    Rectangle {      // focus ring
        anchors.fill: parent
        anchors.margins: -3.5
        radius: height / 2
        color: "transparent"
        border.width: 2.5
        border.color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.55)
        visible: b.activeFocus && !ma.pressed
    }

    // interaction state, eased: hover lifts and lights the glass, press compresses it, release springs back
    property real hv: hovered && enabled ? 1 : 0
    property real pr: ma.pressed ? 1 : 0
    Behavior on hv { NumberAnimation { duration: Theme.dur(180); easing.type: Easing.OutCubic } }
    Behavior on pr { NumberAnimation { duration: Theme.dur(90); easing.type: Easing.OutQuad } }
    // magnetic pull: the button leans a little toward the pointer (at most 1.5 px)
    readonly property real magX: hovered && !Theme.reduceMotion ? Math.max(-1.5, Math.min(1.5, (ma.mouseX - width / 2) / width * 4)) : 0
    readonly property real magY: hovered && !Theme.reduceMotion ? Math.max(-1.5, Math.min(1.5, (ma.mouseY - height / 2) / height * 3)) : 0

    Item {
        id: body
        anchors.fill: parent
        scale: Theme.reduceMotion ? 1 : (ma.pressed ? 0.97 : b.hovered && b.enabled ? 1.03 : 1)
        Behavior on scale { SpringAnimation { spring: 6; damping: 0.38; epsilon: 0.0015 } }
        transform: Translate {
            x: b.magX; y: b.magY
            Behavior on x { SpringAnimation { spring: 4; damping: 0.5; epsilon: 0.02 } }
            Behavior on y { SpringAnimation { spring: 4; damping: 0.5; epsilon: 0.02 } }
        }

        Glass {
            visible: b.kind !== "plain"
            anchors.fill: parent
            anchors.margins: -6
            inset: 6
            radius: b.text ? (b.small ? 13 : 16) : height
            bezel: 9
            refraction: b.backdrop ? 6 + 4 * b.pr : 0
            blur: b.backdrop ? 7 : 0
            zoom: 1 + 0.03 * b.pr
            dispersion: 0.15 + 0.15 * b.pr
            specular: Theme.specular * (1 + 0.35 * b.hv + 0.25 * b.pr)
            backdrop: b.backdrop
            backdropItem: b.backdropItem
            tint: b._tint
            shadow: (b.kind === "primary" || b.kind === "destructive" ? 0.22 : (Theme.dark ? 0.28 : 0.10)) * (1 + 0.45 * b.hv - 0.35 * b.pr)
            shadowSize: 6 + 4 * b.hv - 3 * b.pr        // pressing presses the glass toward the surface
            lift: Math.max(b.pr, 0.35 * b.hv)
            Behavior on tint { ColorAnimation { duration: Theme.fast } }
        }
        Rectangle {      // plain buttons: a soft highlight on hover
            visible: b.kind === "plain"
            anchors.fill: parent
            radius: height / 2
            color: ma.pressed ? Theme.controlPressed : Theme.controlHover
            opacity: b.hovered || ma.pressed ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Theme.fast } }
        }
        Row {
            id: row
            anchors.centerIn: parent
            spacing: 6
            Icon {
                visible: b.icon !== ""
                name: b.icon
                size: b.text ? (b.small ? 13 : 15) : (b.small ? 14 : 16)
                color: b.iconColor
                anchors.verticalCenter: parent.verticalCenter
            }
            Label {
                visible: b.text !== ""
                text: b.text
                textStyle: b.small ? "subhead" : "body"
                font.weight: Font.Medium
                color: b._fg
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }

    MouseArea {
        id: ma
        anchors.fill: parent
        hoverEnabled: true
        enabled: b.enabled
        cursorShape: Qt.PointingHandCursor
        onClicked: { b.forceActiveFocus(); b.clicked() }
    }
    Keys.onSpacePressed: b.clicked()
    Keys.onReturnPressed: b.clicked()
    Keys.onEnterPressed: b.clicked()

    ToolTipLite { text: b.tip; shown: b.tip !== "" && b.hovered && !ma.pressed }
}
