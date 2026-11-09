import QtQuick
import QtQuick.Window

// A standalone alert (used when Mitsuke asks something while its window is hidden, e.g. at first start).
// The window material behind it is native Acrylic.
Window {
    id: aw
    property alias title: content.title
    property alias message: content.message
    property alias buttons: content.buttons
    property alias destructive: content.destructive
    property point pointer: hh.hovered ? hh.point.position : Qt.point(-300, -500)
    signal answered(var value)
    flags: Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    color: "transparent"
    title: "Mitsuke"
    width: 344
    height: content.implicitHeight + 48
    modality: Qt.ApplicationModal

    Rectangle {
        anchors.fill: parent
        color: Theme.windowTint
        radius: 0
    }
    HoverHandler { id: hh }
    MouseArea { anchors.fill: parent; onPressed: aw.startSystemMove() }
    AlertContent {
        id: content
        x: 22; y: 26
        width: parent.width - 44
        onAnswered: (v) => aw.answered(v)
    }
    Component.onCompleted: content.forceActiveFocus()
}
