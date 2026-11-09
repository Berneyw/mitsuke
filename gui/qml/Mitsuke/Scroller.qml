import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic as C

// Vertical scroll area with a centred content column (max width) and an overlay scrollbar that fades in
// while scrolling and widens under the pointer. Content starts below the toolbar and scrolls beneath it.
Flickable {
    id: f
    property real columnWidth: Math.min(width - 56, Theme.contentMax)
    property real topInset: Theme.toolbarHeight + 8
    default property alias column: col.data
    property alias columnItem: col
    property alias spacing: col.spacing
    anchors.fill: parent
    contentWidth: width
    contentHeight: col.implicitHeight + topInset + 36
    boundsBehavior: Flickable.StopAtBounds
    flickDeceleration: 4200
    maximumFlickVelocity: 3200
    clip: false
    pixelAligned: true

    // tell the window how far the visible page is scrolled: the toolbar's scroll-edge blur follows it
    function reportScroll() { if (visible && Window.window && Window.window.scrolled !== undefined) Window.window.scrolled = contentY }
    onContentYChanged: reportScroll()
    onVisibleChanged: reportScroll()

    function toTop() { glide.stop(); contentY = 0; target = 0 }

    // Smooth scrolling: wheel notches glide to their target with a decelerating curve, and notches that arrive
    // mid-glide extend it (so fast wheel spins accelerate naturally). Touchpads with fine deltas track directly.
    property real target: 0
    readonly property real maxY: Math.max(0, contentHeight - height)
    function clampY(y) { return Math.max(0, Math.min(maxY, y)) }
    NumberAnimation {
        id: glide
        target: f; property: "contentY"
        duration: Theme.reduceMotion ? 0 : 340
        easing.type: Easing.OutQuint
    }
    WheelHandler {
        target: null
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
        onWheel: (ev) => {
            const fine = ev.pixelDelta.y !== 0 || Math.abs(ev.angleDelta.y) < 120
            if (fine) {
                glide.stop()
                const d = ev.pixelDelta.y !== 0 ? ev.pixelDelta.y : ev.angleDelta.y * 0.8
                f.contentY = f.clampY(f.contentY - d)
                f.target = f.contentY
            } else {
                const from = glide.running ? f.target : f.contentY
                const speed = glide.running ? 1.35 : 1.0              // consecutive notches accelerate
                f.target = f.clampY(from - ev.angleDelta.y / 120 * 96 * speed)
                glide.stop()
                glide.to = f.target
                glide.start()
            }
        }
    }

    Column {
        id: col
        x: Math.round((f.width - f.columnWidth) / 2)
        y: f.topInset
        width: f.columnWidth
        spacing: 16
    }

    C.ScrollBar.vertical: C.ScrollBar {
        id: bar
        policy: C.ScrollBar.AsNeeded
        topPadding: Theme.toolbarHeight + 4
        bottomPadding: 6
        rightPadding: 3
        minimumSize: 0.08
        contentItem: Rectangle {
            implicitWidth: bar.hovered || bar.pressed ? 8 : 5
            radius: width / 2
            color: Theme.dark ? Qt.rgba(1, 1, 1, bar.pressed ? 0.5 : 0.32) : Qt.rgba(0, 0, 0, bar.pressed ? 0.45 : 0.3)
            opacity: bar.active || bar.hovered ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 260 } }
            Behavior on implicitWidth { NumberAnimation { duration: 120 } }
        }
        background: Item {}
    }
}
