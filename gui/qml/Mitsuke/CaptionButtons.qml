import QtQuick
import QtQuick.Window

// Minimize / maximize / close for the frameless window, Windows 11 placement with quieter glyphs.
Row {
    id: cap
    property var window: null
    spacing: 2
    Repeater {
        model: [
            { name: "minimize", tip: "Minimize" },
            { name: cap.window && cap.window.visibility === Window.Maximized ? "restore" : "maximize", tip: "Maximize" },
            { name: "xmark", tip: "Close" }
        ]
        delegate: Item {
            width: 40; height: 30
            readonly property bool isClose: modelData.name === "xmark"
            Rectangle {
                anchors.fill: parent
                radius: 8
                color: parent.isClose ? "#e81123" : Theme.controlHover
                opacity: ma.containsMouse ? (ma.pressed ? 0.8 : 1) : 0
                Behavior on opacity { NumberAnimation { duration: 90 } }
            }
            Icon {
                anchors.centerIn: parent
                name: modelData.name
                size: 14
                weight: 1.2
                color: parent.isClose && ma.containsMouse ? "#ffffff" : Theme.label2
            }
            MouseArea {
                id: ma
                anchors.fill: parent
                hoverEnabled: true
                onClicked: {
                    if (index === 0) cap.window.showMinimized()
                    else if (index === 1) cap.window.visibility === Window.Maximized ? cap.window.showNormal() : cap.window.showMaximized()
                    else App.hideWindow()
                }
            }
        }
    }
}
