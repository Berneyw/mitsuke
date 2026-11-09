import QtQuick

// The Mitsuke app icon (assets/icon.png): the name on a deep-blue glass squircle.
Item {
    id: ic
    property real size: 36
    width: size; height: size
    Image {
        anchors.fill: parent
        source: Qt.resolvedUrl("../../../assets/icon.png")
        sourceSize: Qt.size(ic.size * 2, ic.size * 2)       // sharp on high-DPI screens
        smooth: true
        mipmap: true
        fillMode: Image.PreserveAspectFit
    }
}
