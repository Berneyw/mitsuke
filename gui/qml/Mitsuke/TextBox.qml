import QtQuick

// Text input on glass: capsule (search) or rounded field. Optional magnifier, clear button, unit suffix,
// edit menu on right-click, focus ring.
Item {
    id: tb
    property alias text: input.text
    property string placeholder: ""
    property bool search: false
    property string suffix: ""
    property bool numeric: false
    property Item backdrop: null
    property Item backdropItem: null
    property alias input: input
    signal edited(string text)
    signal submitted(string text)
    signal escaped()
    implicitHeight: search ? 32 : 28
    implicitWidth: 220
    opacity: enabled ? 1 : 0.42

    function focusField(selectAll) { input.forceActiveFocus(); if (selectAll) input.selectAll() }

    Rectangle {
        anchors.fill: parent; anchors.margins: -3.5
        radius: tb.search ? height / 2 : 11
        color: "transparent"
        border.width: 3; border.color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.5)
        opacity: input.activeFocus ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.fast } }
    }
    Glass {
        anchors.fill: parent
        anchors.margins: -6
        inset: 6
        radius: tb.search ? height : 9
        bezel: 8
        refraction: tb.backdrop ? 6 : 0
        blur: tb.backdrop ? 10 : 0
        backdrop: tb.backdrop
        backdropItem: tb.backdropItem
        tint: Theme.dark ? Qt.rgba(1, 1, 1, input.activeFocus ? 0.12 : hov.hovered ? 0.10 : 0.08)
                         : Qt.rgba(1, 1, 1, input.activeFocus ? 0.96 : 0.82)
        shadow: Theme.dark ? 0.22 : 0.08
        shadowSize: 5
        edge: Theme.glassEdge * 0.8
    }
    HoverHandler { id: hov; cursorShape: Qt.IBeamCursor }

    Icon {
        id: mag
        visible: tb.search
        x: 11
        anchors.verticalCenter: parent.verticalCenter
        name: "search"
        size: 15
        weight: 1.8
        color: Theme.label3
    }
    TextInput {
        id: input
        anchors.left: tb.search ? mag.right : parent.left
        anchors.leftMargin: tb.search ? 7 : 10
        anchors.right: clear.visible ? clear.left : (unit.visible ? unit.left : parent.right)
        anchors.rightMargin: unit.visible ? 3 : 8
        anchors.verticalCenter: parent.verticalCenter
        font.family: Theme.textFamily
        font.pointSize: 0.75 * (tb.search ? Theme.body : Theme.body)
        font.hintingPreference: Font.PreferNoHinting
        color: Theme.label
        selectionColor: Theme.selection
        selectedTextColor: Theme.label
        selectByMouse: true
        clip: true
        renderType: Text.QtRendering
        horizontalAlignment: tb.numeric ? Text.AlignRight : Text.AlignLeft
        validator: tb.numeric ? intVal : null
        onTextEdited: tb.edited(text)
        onAccepted: tb.submitted(text)
        Keys.onEscapePressed: (e) => { if (text && tb.search) { text = ""; tb.edited("") } else tb.escaped(); e.accepted = true }
        Label {
            anchors.fill: parent
            verticalAlignment: Text.AlignVCenter
            horizontalAlignment: input.horizontalAlignment
            text: tb.placeholder
            color: Theme.label3
            visible: !input.text && !input.preeditText
            elide: Text.ElideRight
        }
    }
    IntValidator { id: intVal }
    Label {
        id: unit
        visible: tb.suffix !== ""
        anchors.right: parent.right; anchors.rightMargin: 9
        anchors.verticalCenter: parent.verticalCenter
        text: tb.suffix
        textStyle: "callout"
        color: Theme.label3
    }
    Item {
        id: clear
        visible: tb.search && input.text !== ""
        width: 26; height: parent.height
        anchors.right: parent.right; anchors.rightMargin: 4
        Rectangle {
            anchors.centerIn: parent
            width: 15; height: 15; radius: 7.5
            color: clearMa.containsMouse ? Theme.label3 : Theme.label4
            Icon { anchors.centerIn: parent; name: "xmark"; size: 9; weight: 1.7; color: Theme.dark ? "#1c1c1e" : "#ffffff" }
        }
        MouseArea {
            id: clearMa
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.ArrowCursor
            onClicked: { input.text = ""; tb.edited(""); input.forceActiveFocus() }
        }
    }
    MouseArea {      // edit menu
        anchors.fill: parent
        acceptedButtons: Qt.RightButton
        cursorShape: Qt.IBeamCursor
        onClicked: (m) => {
            input.forceActiveFocus()
            editMenu.items = [
                { label: "Cut", value: "cut", shortcut: "Ctrl+X", enabled: input.selectedText !== "" },
                { label: "Copy", value: "copy", shortcut: "Ctrl+C", enabled: input.selectedText !== "" },
                { label: "Paste", value: "paste", shortcut: "Ctrl+V", enabled: input.canPaste },
                { separator: true },
                { label: "Select All", value: "all", shortcut: "Ctrl+A", enabled: input.text !== "" }
            ]
            editMenu.x = m.x; editMenu.y = m.y
            editMenu.open()
        }
    }
    GlassMenu {
        id: editMenu
        onTriggered: (it) => {
            if (it.value === "cut") { input.cut(); tb.edited(input.text) }
            else if (it.value === "copy") input.copy()
            else if (it.value === "paste") { input.paste(); tb.edited(input.text) }
            else input.selectAll()
            input.forceActiveFocus()
        }
    }
}
