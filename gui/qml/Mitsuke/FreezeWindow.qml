import QtQuick
import QtQuick.Window

// The paused screen: while the sentence key is held, a still picture of the monitor covers the game, so a
// tooltip that would vanish when the mouse moves stays put and can be read word by word.
Window {
    id: fw
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus
    color: "black"
    property string source: ""
    property string keyName: "Ctrl"
    property bool shown: false

    Image {
        anchors.fill: parent
        source: fw.source
        cache: false
        smooth: true
        fillMode: Image.Stretch
    }

    // a quiet edge so it's clear the picture is paused
    Rectangle {
        anchors.fill: parent
        color: "transparent"
        border.width: 2
        border.color: Qt.rgba(1, 1, 1, 0.22)
    }

    Rectangle {
        id: pill
        anchors.horizontalCenter: parent.horizontalCenter
        y: fw.shown ? 14 : -height - 4
        Behavior on y { NumberAnimation { duration: Theme.reduceMotion ? 0 : 220; easing.type: Easing.OutCubic } }
        height: 30; radius: 15
        width: row.implicitWidth + 28
        color: Qt.rgba(0.08, 0.09, 0.12, 0.82)
        border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.16)
        Row {
            id: row
            anchors.centerIn: parent
            spacing: 8
            Icon { name: "pause"; size: 13; color: "#ffffff"; anchors.verticalCenter: parent.verticalCenter }
            Label {
                anchors.verticalCenter: parent.verticalCenter
                text: "Paused — point at a sentence · release " + fw.keyName + " to continue"
                textStyle: "footnote"; font.weight: Font.DemiBold; color: "#ffffff"
            }
        }
    }
}
