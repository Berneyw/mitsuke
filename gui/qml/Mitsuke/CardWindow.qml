import QtQuick
import QtQuick.Window

// The word card next to the cursor in the game: on top, never focused, click-through, excluded from
// capture. Python feeds a live picture of what's behind it (`frame` bumps ~15 times a second) so the glass
// refracts the moving game, and moves the light with the cursor.
Window {
    id: cw
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput
    color: "transparent"
    property var lines: []
    property real cardWidth: 440
    property int frame: 0
    property real minTint: 0
    property point pointer: Qt.point(-200, -300)
    property bool shown: false
    property real maxCardHeight: 2000
    readonly property real margin: 26
    readonly property real cardHeight: Math.min(card.implicitHeight, maxCardHeight)
    readonly property real naturalHeight: card.implicitHeight
    width: cardWidth + 2 * margin
    height: cardHeight + 2 * margin

    Image {
        id: bg
        anchors.fill: parent
        source: cw.frame > 0 ? "image://backdrop/card/" + cw.frame : ""
        cache: false
        asynchronous: false
        mipmap: true
        visible: false
    }
    Item {
        id: holder
        x: cw.margin; y: cw.margin
        width: cw.cardWidth; height: cw.cardHeight
        opacity: cw.shown ? 1 : 0
        scale: cw.shown ? 1 : (Theme.reduceMotion ? 1 : 0.965)
        Behavior on opacity { NumberAnimation { duration: Theme.fast; easing.type: Easing.OutCubic } }
        Behavior on scale { SpringAnimation { spring: 5; damping: 0.5; epsilon: 0.001 } }
        clip: false
        GameCard {
            id: card
            width: parent.width
            height: parent.height
            backdrop: cw.frame > 0 ? bg : null
            backdropItem: bg
            minTint: cw.minTint
            lines: cw.lines
        }
    }
}
