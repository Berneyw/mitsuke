import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic as C

// Modal alert inside the main window: the window dims, the alert floats in on thick glass.
C.Popup {
    id: ap
    property alias title: content.title
    property alias message: content.message
    property alias buttons: content.buttons
    property alias destructive: content.destructive
    property var onAnswer: null
    readonly property var hostWindow: parent ? parent.Window.window : null

    function ask(t, m, b, cb, destr) {
        title = t; message = m; buttons = b; onAnswer = cb; destructive = !!destr
        open()
    }

    modal: true
    focus: true
    closePolicy: C.Popup.CloseOnEscape
    anchors.centerIn: C.Overlay.overlay
    padding: 22
    topPadding: 26
    C.Overlay.modal: Rectangle {
        color: Qt.rgba(0, 0, 0, Theme.dark ? 0.32 : 0.16)
        Behavior on opacity { NumberAnimation { duration: Theme.fast } }
    }
    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast }
            NumberAnimation { property: "scale"; from: Theme.reduceMotion ? 1 : 1.08; to: 1; duration: Theme.normal; easing.type: Easing.OutCubic }
        }
    }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.fast } }
    onClosed: { if (onAnswer) { const f = onAnswer; onAnswer = null; f(buttons.length ? buttons[buttons.length - 1].value : null) } }

    background: Item {
        Glass {
            anchors.fill: parent
            anchors.margins: -24
            inset: 24
            radius: 18
            bezel: 14
            refraction: 10
            blur: Theme.reduceTransparency ? 0 : 24
            saturation: 1.6
            backdrop: ap.hostWindow && ap.hostWindow.sceneTex ? ap.hostWindow.sceneTex : null
            backdropItem: ap.hostWindow && ap.hostWindow.sceneItem ? ap.hostWindow.sceneItem : null
            tint: Theme.menuTint
            shadow: Theme.dark ? 0.6 : 0.25
            shadowSize: 26
        }
    }
    contentItem: AlertContent {
        id: content
        onAnswered: (v) => { const f = ap.onAnswer; ap.onAnswer = null; ap.close(); if (f) f(v) }
    }
    onOpened: content.forceActiveFocus()
}
