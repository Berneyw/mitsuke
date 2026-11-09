import QtQuick
import QtQuick.Window

// A card kept open after the scan key is released (double-tap): drag it by its top bar, scroll it, save the
// word, copy it, open it in Mitsuke. It never takes focus from the game; its glass stays live.
Window {
    id: pw
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus
    color: "transparent"
    property var lines: []
    property real cardWidth: 440
    property real maxBodyHeight: 600
    property int frame: 0
    property real minTint: 0
    property point pointer: hh.hovered ? hh.point.position : Qt.point(-200, -300)
    property bool saved: false
    property bool canSave: true
    property string note: ""
    readonly property real margin: 26
    readonly property real headH: 40
    readonly property real bodyH: Math.min(body.implicitHeight + 22, maxBodyHeight)
    signal action(string name)
    signal moved()
    width: cardWidth + 2 * margin
    height: headH + bodyH + 2 * margin

    Image {
        id: bg
        anchors.fill: parent
        source: pw.frame > 0 ? "image://backdrop/pin/" + pw.frame : ""
        cache: false; asynchronous: false; mipmap: true; visible: false
    }
    HoverHandler { id: hh }
    Timer { id: noteTimer; interval: 1600; onTriggered: pw.note = "" }
    onNoteChanged: if (note) noteTimer.restart()

    Item {
        id: holder
        x: pw.margin; y: pw.margin
        width: pw.cardWidth; height: pw.headH + pw.bodyH
        opacity: 0
        scale: Theme.reduceMotion ? 1 : 0.96
        Component.onCompleted: { opacity = 1; scale = 1 }
        Behavior on opacity { NumberAnimation { duration: Theme.normal } }
        Behavior on scale { SpringAnimation { spring: 4.5; damping: 0.45; epsilon: 0.001 } }

        GameCard {
            id: card
            anchors.fill: parent
            backdrop: pw.frame > 0 ? bg : null
            backdropItem: bg
            minTint: pw.minTint
            pinned: true
            topPad: pw.headH + 2
            lines: []                    // the text lives in the scrolling body below
        }
        // header
        Item {
            width: parent.width; height: pw.headH
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.SizeAllCursor
                property point grab
                onPressed: (m) => grab = Qt.point(m.x, m.y)
                onPositionChanged: (m) => { if (pressed) { pw.x += m.x - grab.x; pw.y += m.y - grab.y } }
                onReleased: pw.moved()
            }
            Row {
                x: 16
                anchors.verticalCenter: parent.verticalCenter
                spacing: 6
                Icon { name: "pin"; size: 14; color: card.dark ? "#d1d1d6" : "#3a3a3c"; anchors.verticalCenter: parent.verticalCenter }
                Label {
                    text: pw.note || "Pinned"
                    textStyle: "footnote"
                    font.weight: pw.note ? Font.DemiBold : Font.Normal
                    color: card.dark ? (pw.note ? "#ffffff" : "#d1d1d6") : (pw.note ? "#1d1d1f" : "#3a3a3c")
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
            Row {
                anchors.right: parent.right; anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2
                Repeater {
                    model: [
                        { name: "save", icon: "star", tip: pw.saved ? "Remove from My Words" : "Save to My Words", show: pw.canSave },
                        { name: "copy", icon: "copy", tip: "Copy", show: true },
                        { name: "open", icon: "open", tip: "Open in Mitsuke", show: true },
                        { name: "close", icon: "xmark", tip: "Close", show: true }
                    ]
                    Item {
                        visible: modelData.show
                        width: 30; height: 30
                        Rectangle {
                            anchors.fill: parent; radius: 15
                            color: card.dark ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(0, 0, 0, 0.08)
                            opacity: bma.containsMouse ? 1 : 0
                            scale: bma.pressed ? 0.9 : 1
                            Behavior on opacity { NumberAnimation { duration: 90 } }
                            Behavior on scale { SpringAnimation { spring: 5; damping: 0.45 } }
                        }
                        Icon {
                            anchors.centerIn: parent
                            name: modelData.icon
                            size: 15
                            filled: modelData.name === "save" && pw.saved
                            color: modelData.name === "save" && pw.saved ? "#ffd60a" : (card.dark ? "#ffffff" : "#1d1d1f")
                        }
                        MouseArea { id: bma; anchors.fill: parent; hoverEnabled: true; onClicked: pw.action(modelData.name) }
                        ToolTipLite { text: modelData.tip; shown: bma.containsMouse }
                    }
                }
            }
            Rectangle { y: parent.height - 1; x: 12; width: parent.width - 24; height: 1; color: card.dark ? Qt.rgba(1, 1, 1, 0.14) : Qt.rgba(0, 0, 0, 0.1) }
        }
        // body
        Flickable {
            id: flick
            x: 0; y: pw.headH
            width: parent.width; height: pw.bodyH
            clip: true
            contentHeight: body.implicitHeight + 16
            boundsBehavior: Flickable.StopAtBounds
            WordCard {
                id: body
                x: 16; y: 6
                width: flick.width - 32
                lines: pw.lines
                basePt: App.settings.font_size || 11
                colors: card.card.colors
                onGlass: card.dark
            }
        }
    }
}
