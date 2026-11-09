import QtQuick

// A page in two layers: its toolbar (title + glass actions) sits in the window chrome, and its content is
// reparented into the stage underneath, so the toolbar glass refracts the content scrolling under it.
Item {
    id: page
    property string key: ""
    property string title: ""
    property bool current: false
    property Item stage: null
    property Item stageTex: null
    property real trailing: 0                     // room kept for the caption buttons
    property alias actions: actionsRow.data
    property alias body: holder.data
    property alias titleItem: titleLabel
    anchors.fill: parent

    opacity: current ? 1 : 0
    visible: opacity > 0.001
    Behavior on opacity { NumberAnimation { duration: Theme.normal; easing.type: Easing.OutCubic } }
    property real shift: current ? 0 : 10
    Behavior on shift { NumberAnimation { duration: Theme.normal; easing.type: Easing.OutCubic } }

    Item {
        id: holder
        parent: page.stage
        anchors.fill: parent
        visible: page.visible
        opacity: page.opacity
        transform: Translate { y: page.shift }
    }

    Label {
        id: titleLabel
        x: 28
        y: (Theme.toolbarHeight - height) / 2 + 2
        text: page.title
        textStyle: "title1"
        transform: Translate { y: page.shift * 0.5 }
    }
    Row {
        id: actionsRow
        anchors.right: parent.right
        anchors.rightMargin: page.trailing + 14
        y: (Theme.toolbarHeight - height) / 2 + 2
        spacing: 8
        layoutDirection: Qt.RightToLeft
    }
}
