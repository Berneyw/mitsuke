import QtQuick

// The body of an alert, macOS style: app icon, bold title, message, buttons (the first is the default
// action and sits on the right; the last cancels). Enter / Escape answer it.
Column {
    id: ac
    property string title: ""
    property string message: ""
    property var buttons: []           // [{label, value}]
    property bool destructive: false
    signal answered(var value)
    width: 300
    spacing: 0
    focus: true

    AppIcon { size: 56; anchors.horizontalCenter: parent.horizontalCenter }
    Item { width: 1; height: 14 }
    Label {
        width: parent.width
        text: ac.title
        textStyle: "headline"
        font.pointSize: 0.75 * (14.5)
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
    }
    Item { width: 1; height: 6 }
    Label {
        width: parent.width
        text: ac.message
        textStyle: "footnote"
        font.pointSize: 0.75 * (12)
        color: Theme.label2
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        lineHeight: 1.18
    }
    Item { width: 1; height: 20 }
    Row {
        id: btns
        width: parent.width
        spacing: 8
        layoutDirection: Qt.RightToLeft
        Repeater {
            model: ac.buttons
            GlassButton {
                width: (btns.width - btns.spacing * (ac.buttons.length - 1)) / ac.buttons.length
                text: modelData.label
                kind: index === 0 ? (ac.destructive ? "destructive" : "primary") : "secondary"
                onClicked: ac.answered(modelData.value)
            }
        }
    }
    Keys.onReturnPressed: if (buttons.length) answered(buttons[0].value)
    Keys.onEnterPressed: if (buttons.length) answered(buttons[0].value)
    Keys.onEscapePressed: if (buttons.length) answered(buttons[buttons.length - 1].value)
}
