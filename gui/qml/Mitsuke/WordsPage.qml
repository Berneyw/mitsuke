import QtQuick
import QtQuick.Dialogs

// My Words: saved words on a glass list, search, Anki export, and spaced-repetition review
// (Space reveals, 1–4 grade).
Page {
    id: wp
    key: "words"
    title: reviewing ? "Review" : "My Words"
    property bool reviewing: false
    property var cards: []
    property int idx: 0
    property bool revealed: false
    property int done: 0
    property var rows: []
    property int rev: 0
    readonly property int total: App.state.total || 0
    readonly property int due: App.state.due || 0

    function reload() { rows = App.words(filter.text); rev++ }
    Connections { target: App; function onWordsChanged() { if (!wp.reviewing) wp.reload() } }
    onCurrentChanged: if (current && !reviewing) reload()
    Component.onCompleted: reload()

    function startReview() {
        cards = App.dueCards()
        if (!cards.length) return
        idx = 0; revealed = false; done = 0; reviewing = true
        reviewFocus.forceActiveFocus()
    }
    function endReview() { reviewing = false; App.reviewEnded(); reload() }
    function grade(g) {
        if (!reviewing || !revealed || idx >= cards.length) return
        App.grade(cards[idx].id, g)
        done++; idx++; revealed = false
    }

    actions: [
        GlassButton {
            text: wp.due ? "Review " + wp.due : "Review"
            kind: "primary"; small: true
            enabled: wp.due > 0 && !wp.reviewing
            backdrop: wp.stageTex; backdropItem: wp.stage
            onClicked: wp.startReview()
        },
        GlassButton {
            text: "Export for Anki…"; icon: "export"; small: true
            enabled: wp.total > 0 && !wp.reviewing
            backdrop: wp.stageTex; backdropItem: wp.stage
            onClicked: saveDlg.open()
        },
        TextBox {
            id: filter
            search: true
            visible: !wp.reviewing
            width: 220
            placeholder: "Search my words"
            backdrop: wp.stageTex; backdropItem: wp.stage
            onEdited: wp.reload()
        }
    ]

    FileDialog {
        id: saveDlg
        title: "Export for Anki"
        fileMode: FileDialog.SaveFile
        defaultSuffix: "txt"
        nameFilters: ["Anki text (*.txt)"]
        onAccepted: App.flash(App.exportAnki(selectedFile))
    }

    body: [
        Scroller {
            id: listScroll
            visible: !wp.reviewing
            Label {
                visible: wp.total > 0
                leftPadding: 4
                text: wp.total + " word" + (wp.total !== 1 ? "s" : "") + (wp.due ? " · " + wp.due + " due for review" : " · all reviewed")
                textStyle: "footnote"; color: Theme.label3
            }
            // empty
            Column {
                visible: wp.total === 0
                width: parent.width
                spacing: 6
                Item { width: 1; height: 48 }
                Item {
                    width: parent.width; height: 64
                    Rectangle {
                        anchors.centerIn: parent
                        width: 64; height: 64; radius: 20
                        color: Theme.controlFill
                        Icon { anchors.centerIn: parent; name: "star"; size: 32; weight: 1.6; color: Theme.label3 }
                    }
                }
                Item { width: 1; height: 8 }
                Label { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: "No saved words yet"; textStyle: "title2" }
                Label {
                    width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
                    textStyle: "callout"; color: Theme.label3; lineHeight: 1.2
                    text: "In the game, double-tap " + (App.state.keyName || "Shift") + " on a word to pin its card, then click ☆.\n"
                          + "In Lookup, click ☆ or press Ctrl+S. Saved words come back for review just before you’d forget them."
                }
            }
            Label {
                visible: wp.total > 0 && wp.rows.length === 0
                width: parent.width; horizontalAlignment: Text.AlignHCenter
                topPadding: 30
                text: "No saved words match “" + filter.text + "”."
                textStyle: "callout"; color: Theme.label3
            }
            Item {
                visible: wp.rows.length > 0
                width: parent.width
                height: list.height
                Glass {
                    anchors.fill: parent; anchors.margins: -10; inset: 10
                    radius: Theme.rGroup; refraction: 0
                    tint: Theme.groupTint
                    specular: Theme.specular * 0.45
                    shadow: Theme.dark ? 0.18 : 0.07; shadowSize: 10
                }
                Column {
                    id: list
                    width: parent.width
                    Repeater {
                        model: wp.rows
                        delegate: Item {
                            id: rowItem
                            width: list.width
                            height: rowCol.implicitHeight + 22
                            Rectangle { visible: index > 0; x: 14; width: parent.width - 14; height: 1; color: Theme.separator }
                            Rectangle {
                                anchors.fill: parent; anchors.margins: 3
                                radius: 10
                                color: Theme.controlFill
                                opacity: rowHov.hovered ? 0.7 : 0
                                Behavior on opacity { NumberAnimation { duration: 100 } }
                            }
                            Column {
                                id: rowCol
                                x: 14; y: 11
                                width: parent.width - 120
                                spacing: 2
                                Row {
                                    spacing: 7
                                    Rectangle {
                                        visible: modelData.article !== ""
                                        anchors.verticalCenter: parent.verticalCenter
                                        height: 19; width: art.implicitWidth + 12; radius: 9.5
                                        color: Theme.gender[modelData.article] || Theme.accentFill
                                        Label { id: art; anchors.centerIn: parent; text: modelData.article; textStyle: "caption"; font.weight: Font.Bold; color: "#ffffff" }
                                    }
                                    Label { text: modelData.word; textStyle: "headline"; font.pointSize: 0.75 * (14.5) }
                                    Label { anchors.verticalCenter: parent.verticalCenter; text: modelData.pos; textStyle: "footnote"; color: Theme.label3 }
                                }
                                Label { width: parent.width; text: modelData.gloss; textStyle: "callout"; color: Theme.label2; wrapMode: Text.WordWrap }
                                Label {
                                    visible: modelData.context !== ""
                                    width: parent.width
                                    text: "“" + modelData.context + "”"
                                    textStyle: "footnote"; color: Theme.label3; wrapMode: Text.WordWrap
                                    font.italic: true
                                }
                            }
                            Label {
                                anchors.right: del.left; anchors.rightMargin: 8
                                y: 13
                                text: modelData.added
                                textStyle: "footnote"; color: Theme.label4
                            }
                            GlassButton {
                                id: del
                                anchors.right: parent.right; anchors.rightMargin: 10
                                y: 7
                                icon: "trash"; kind: "plain"; small: true
                                iconColor: Theme.label3
                                tip: "Remove"
                                opacity: rowHov.hovered ? 1 : 0.0
                                Behavior on opacity { NumberAnimation { duration: 120 } }
                                onClicked: App.removeWord(modelData.id)
                            }
                            HoverHandler { id: rowHov }
                            MouseArea {
                                anchors.fill: parent
                                acceptedButtons: Qt.RightButton
                                onClicked: (m) => {
                                    wordMenu.row = modelData
                                    wordMenu.items = [
                                        { label: "Look Up", value: "look", icon: "search" },
                                        { label: "Copy “" + modelData.word + "”", value: "copy", icon: "copy" },
                                        { separator: true },
                                        { label: "Remove", value: "remove", icon: "trash", destructive: true }
                                    ]
                                    const p = mapToItem(list, m.x, m.y)
                                    wordMenu.x = p.x; wordMenu.y = p.y
                                    wordMenu.open()
                                }
                            }
                        }
                    }
                }
                GlassMenu {
                    id: wordMenu
                    property var row: null
                    onTriggered: (it) => {
                        if (it.value === "look") App.lookupRequested(row.word)
                        else if (it.value === "copy") App.copyText(row.word)
                        else App.removeWord(row.id)
                    }
                }
            }
            Label {
                visible: wp.rows.length >= 300
                text: "Showing the 300 newest. Search to find older words."
                textStyle: "footnote"; color: Theme.label3
            }
        },

        // ---------------------------------------------------------------- review
        Item {
            id: reviewFocus
            anchors.fill: parent
            visible: wp.reviewing
            focus: wp.reviewing
            Keys.onSpacePressed: { if (!wp.revealed && wp.idx < wp.cards.length) wp.revealed = true }
            Keys.onPressed: (e) => {
                if (wp.revealed && e.text >= "1" && e.text <= "4") { wp.grade(["again", "hard", "good", "easy"][parseInt(e.text) - 1]); e.accepted = true }
            }
            readonly property var card: wp.idx < wp.cards.length ? wp.cards[wp.idx] : null

            Column {
                width: Math.min(parent.width - 80, 600)
                anchors.horizontalCenter: parent.horizontalCenter
                y: Theme.toolbarHeight + 30
                spacing: 14
                visible: reviewFocus.card !== null

                Label {
                    width: parent.width; horizontalAlignment: Text.AlignHCenter
                    text: (wp.idx + 1) + " of " + wp.cards.length
                    textStyle: "footnote"; color: Theme.label3
                }
                Item {     // the card: flips in with a spring when the answer is revealed
                    id: flash
                    width: parent.width
                    height: cardCol.implicitHeight + 64
                    Glass {
                        anchors.fill: parent; anchors.margins: -16; inset: 16
                        radius: 22; refraction: 0
                        tint: Theme.groupTint
                        specular: Theme.specular * 0.7
                        shadow: Theme.dark ? 0.3 : 0.1; shadowSize: 18
                    }
                    Column {
                        id: cardCol
                        x: 32; y: 32
                        width: parent.width - 64
                        spacing: 8
                        Label {
                            width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
                            text: reviewFocus.card ? ((reviewFocus.card.article ? reviewFocus.card.article + " " : "") + reviewFocus.card.word) : ""
                            textStyle: "largeTitle"; font.pointSize: 0.75 * (30)
                            color: reviewFocus.card && reviewFocus.card.article ? Theme.gender[reviewFocus.card.article] : Theme.label
                        }
                        Label {
                            visible: reviewFocus.card && reviewFocus.card.context !== ""
                            width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
                            text: reviewFocus.card ? "“" + reviewFocus.card.context + "”" : ""
                            textStyle: "callout"; color: Theme.label3; font.italic: true
                        }
                        Item {
                            width: parent.width
                            height: wp.revealed ? answer.implicitHeight + 28 : 0
                            clip: true
                            Behavior on height { NumberAnimation { duration: Theme.normal; easing.type: Easing.OutCubic } }
                            Column {
                                id: answer
                                y: 14
                                width: parent.width
                                spacing: 6
                                opacity: wp.revealed ? 1 : 0
                                Behavior on opacity { NumberAnimation { duration: Theme.normal } }
                                Rectangle { width: parent.width; height: 1; color: Theme.separator }
                                Item { width: 1; height: 8 }
                                Label {
                                    width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
                                    text: reviewFocus.card ? reviewFocus.card.gloss : ""
                                    textStyle: "title3"; font.weight: Font.Normal
                                }
                                Label {
                                    visible: reviewFocus.card && reviewFocus.card.forms !== ""
                                    width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
                                    text: reviewFocus.card ? reviewFocus.card.forms : ""
                                    textStyle: "footnote"; color: Theme.label3
                                }
                            }
                        }
                    }
                }
                Column {
                    visible: !wp.revealed
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: 6
                    GlassButton { text: "Show Answer"; kind: "primary"; minWidth: 160; onClicked: wp.revealed = true; anchors.horizontalCenter: parent.horizontalCenter }
                    Label { text: "Space"; textStyle: "footnote"; color: Theme.label4; anchors.horizontalCenter: parent.horizontalCenter }
                }
                Row {
                    visible: wp.revealed
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: 10
                    Repeater {
                        model: [["again", "Again"], ["hard", "Hard"], ["good", "Good"], ["easy", "Easy"]]
                        Column {
                            spacing: 5
                            GlassButton {
                                width: 104
                                text: modelData[1]
                                kind: modelData[0] === "good" ? "primary" : modelData[0] === "again" ? "destructive" : "secondary"
                                onClicked: wp.grade(modelData[0])
                            }
                            Label {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: (reviewFocus.card ? reviewFocus.card.intervals[index] : "") + " · " + (index + 1)
                                textStyle: "footnote"; color: Theme.label4
                            }
                        }
                    }
                }
                GlassButton {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "End Review"; kind: "plain"; small: true
                    onClicked: wp.endReview()
                }
            }

            // finished
            Column {
                visible: reviewFocus.card === null
                width: parent.width
                y: Theme.toolbarHeight + 60
                spacing: 6
                Item {
                    width: parent.width; height: 64
                    Rectangle {
                        anchors.centerIn: parent
                        width: 64; height: 64; radius: 32
                        color: Qt.rgba(Theme.green.r, Theme.green.g, Theme.green.b, 0.16)
                        Icon { anchors.centerIn: parent; name: "checkmark"; size: 30; weight: 2.4; color: Theme.green }
                    }
                }
                Item { width: 1; height: 8 }
                Label { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: "All caught up"; textStyle: "title2" }
                Label {
                    width: parent.width; horizontalAlignment: Text.AlignHCenter
                    text: "You reviewed " + wp.done + " word" + (wp.done !== 1 ? "s" : "") + ". They’ll come back when it’s time."
                    textStyle: "callout"; color: Theme.label3
                }
                Item { width: 1; height: 12 }
                GlassButton { text: "Done"; kind: "primary"; minWidth: 120; anchors.horizontalCenter: parent.horizontalCenter; onClicked: wp.endReview() }
            }
        }
    ]
}
