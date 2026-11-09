import QtQuick
import QtQuick.Window
import QtQuick.Shapes

// Marks what is being read, like a text selection: the word under the cursor gets a marker fill, linked
// words (a separable particle, the rest of a phrase) an outline and underline, the read strip (optional) a
// dashed frame. Click-through and invisible to screen capture.
Window {
    id: hw
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput
    color: "transparent"
    property var primary: []        // [{x, y, w, h}] in window coordinates
    property var secondary: []
    property var area: null
    readonly property color marker: "#ffd60a"

    Item {
        id: layer
        anchors.fill: parent
        opacity: hw.primary.length + hw.secondary.length > 0 || hw.area ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.fast } }

        Shape {
            visible: hw.area !== null
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: "#5ac8fa"
                strokeWidth: 2
                fillColor: Qt.rgba(90 / 255, 200 / 255, 250 / 255, 0.05)
                strokeStyle: ShapePath.DashLine
                dashPattern: [4, 3]
                PathRectangle {
                    x: hw.area ? hw.area.x + 1 : 0; y: hw.area ? hw.area.y + 1 : 0
                    width: hw.area ? hw.area.w - 2 : 0; height: hw.area ? hw.area.h - 2 : 0
                    radius: 6
                }
            }
        }
        Repeater {
            model: hw.secondary
            Item {
                x: modelData.x - 3; y: modelData.y - 2
                width: modelData.w + 6; height: modelData.h + 4
                Rectangle {
                    anchors.fill: parent
                    radius: 5
                    color: Qt.rgba(1, 0.84, 0.04, 0.10)
                    border.width: 2
                    border.color: Qt.rgba(1, 0.84, 0.04, 0.85)
                }
                Rectangle {
                    width: parent.width; height: 2.5; radius: 1.25
                    y: parent.height + 2
                    color: hw.marker
                }
            }
        }
        Repeater {
            model: hw.primary
            Rectangle {
                x: modelData.x - 3; y: modelData.y - 2
                width: modelData.w + 6; height: modelData.h + 4
                radius: 5
                color: Qt.rgba(1, 0.84, 0.04, 0.40)
                border.width: 1
                border.color: Qt.rgba(1, 0.84, 0.04, 0.9)
                scale: 1
                NumberAnimation on scale { from: Theme.reduceMotion ? 1 : 0.92; to: 1; duration: 160; easing.type: Easing.OutBack }
            }
        }
    }
}
