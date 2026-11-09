import QtQuick
import QtQuick.Controls.Basic as C

// A small glass tooltip under its parent, after a short hover delay.
Item {
    id: tt
    property string text: ""
    property bool shown: false
    anchors.fill: parent

    Timer { id: delay; interval: 650; onTriggered: pop.open() }
    onShownChanged: { if (shown) delay.restart(); else { delay.stop(); pop.close() } }

    C.Popup {
        id: pop
        y: tt.height + 8
        x: Math.round((tt.width - width) / 2)
        padding: 0
        margins: 6
        closePolicy: C.Popup.NoAutoClose
        enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast } }
        exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.fast } }
        background: Glass {
            anchors.fill: parent
            anchors.margins: -6
            inset: 6
            radius: 8
            bezel: 5
            refraction: 0
            tint: Theme.menuTint
            shadow: Theme.dark ? 0.35 : 0.14
            shadowSize: 8
        }
        contentItem: Label {
            text: tt.text
            textStyle: "footnote"
            color: Theme.label2
            leftPadding: 9; rightPadding: 9; topPadding: 5; bottomPadding: 5
        }
    }
}
