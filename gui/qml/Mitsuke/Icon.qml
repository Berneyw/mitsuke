import QtQuick
import QtQuick.Shapes

// A vector icon from Icons.paths: crisp at any size and DPI, recoloured by `color`.
Item {
    id: root
    property string name: ""
    property color color: Theme.label
    property real size: 16
    property real weight: 1.6           // stroke width in screen pixels
    property bool filled: false
    implicitWidth: size
    implicitHeight: size

    Shape {
        width: 24; height: 24
        scale: root.size / 24
        transformOrigin: Item.TopLeft
        preferredRendererType: Shape.CurveRenderer
        antialiasing: true
        ShapePath {
            strokeColor: root.filled ? "transparent" : root.color
            fillColor: root.filled ? root.color : "transparent"
            strokeWidth: root.weight * 24 / root.size
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            fillRule: ShapePath.OddEvenFill
            PathSvg { path: Icons.paths[root.name] || "" }
        }
    }
}
