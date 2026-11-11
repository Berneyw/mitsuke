import QtQuick
import QtQuick.Window

// History: every word looked up in the game or in Lookup, with how often it came up and the sentence it
// was in. One click saves it to My Words; words that keep coming back are pointed out.
Page {
    id: hp
    key: "history"
    title: "History"
    property string period: "week"
    property string order: "recent"
    property var rows: []
    property int frequentUnsaved: 0

    function reload() {
        rows = App.history(period, filter.text, order)
        let n = 0
        for (let i = 0; i < rows.length; ++i) if (rows[i].count >= 3 && !rows[i].saved) n++
        frequentUnsaved = n
    }
    Connections {
        target: App
        function onHistoryChanged() { if (hp.current) hp.reload() }
        function onWordsChanged() { if (hp.current) hp.reload() }
    }
    onCurrentChanged: if (current) reload()
    onPeriodChanged: reload()
    onOrderChanged: reload()

    actions: [
        TextBox {
            id: filter
            search: true
            width: 190
            placeholder: "Search history"
            backdrop: hp.stageTex; backdropItem: hp.stage
            onEdited: hp.reload()
        },
        GlassSegmented {
            width: 210
            options: [{ label: "Today", value: "today" }, { label: "Week", value: "week" }, { label: "All", value: "all" }]
            value: hp.period
            onSelected: (v) => hp.period = v
        }
    ]

    body: Scroller {
        id: scroller
        objectName: "historyScroll"

        Row {
            width: parent.width
            visible: hp.rows.length > 0
            Label {
                width: parent.width - sortBox.width - clearBtn.width - 8
                anchors.verticalCenter: parent.verticalCenter
                leftPadding: 4
                text: hp.rows.length + " word" + (hp.rows.length !== 1 ? "s" : "")
                      + (hp.period === "today" ? " today" : hp.period === "week" ? " this week" : "")
                textStyle: "footnote"; color: Theme.label3
            }
            GlassButton {
                id: clearBtn
                anchors.verticalCenter: parent.verticalCenter
                text: "Clear History…"; kind: "plain"; small: true
                onClicked: hp.Window.window.ask("Clear the history?",
                               "Every looked-up word is removed from History. Your saved words in My Words stay.",
                               [{ label: "Clear", value: "clear" }, { label: "Cancel", value: "no" }],
                               (v) => { if (v === "clear") App.clearHistory() }, true)
            }
            Item { width: 8; height: 1 }
            PopupButton {
                id: sortBox
                minWidth: 130
                options: [{ label: "Most recent", value: "recent" }, { label: "Most seen", value: "frequent" }]
                value: hp.order
                onSelected: (v) => hp.order = v
            }
        }

        // words that keep coming back: worth learning
        Item {
            visible: hp.frequentUnsaved > 0 && hp.order === "recent"
            width: parent.width
            height: visible ? tipRow.implicitHeight + 24 : 0
            Glass {
                anchors.fill: parent; anchors.margins: -10; inset: 10
                radius: 14; refraction: 0
                tint: Qt.rgba(Theme.accentFill.r, Theme.accentFill.g, Theme.accentFill.b, Theme.dark ? 0.14 : 0.10)
                shadow: Theme.dark ? 0.15 : 0.05; shadowSize: 8
            }
            Row {
                id: tipRow
                x: 14; y: 12
                width: parent.width - 28
                spacing: 12
                Icon { name: "sparkles"; size: 18; color: Theme.accent; anchors.verticalCenter: parent.verticalCenter }
                Label {
                    width: parent.width - 150
                    anchors.verticalCenter: parent.verticalCenter
                    text: hp.frequentUnsaved + (hp.frequentUnsaved === 1 ? " word keeps" : " words keep")
                          + " coming up — worth saving to learn."
                    textStyle: "callout"; wrapMode: Text.WordWrap
                }
                GlassButton { text: "Show"; small: true; kind: "primary"; anchors.verticalCenter: parent.verticalCenter; onClicked: hp.order = "frequent" }
            }
        }

        // empty
        Column {
            visible: hp.rows.length === 0
            width: parent.width
            spacing: 6
            Item { width: 1; height: 48 }
            Item {
                width: parent.width; height: 64
                Rectangle {
                    anchors.centerIn: parent
                    width: 64; height: 64; radius: 20
                    color: Theme.controlFill
                    Icon { anchors.centerIn: parent; name: "clock"; size: 32; weight: 1.6; color: Theme.label3 }
                }
            }
            Item { width: 1; height: 8 }
            Label {
                width: parent.width; horizontalAlignment: Text.AlignHCenter
                text: filter.text ? "Nothing matches “" + filter.text + "”"
                      : hp.period === "today" ? "No words looked up today" : "No words looked up yet"
                textStyle: "title2"
            }
            Label {
                width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
                textStyle: "callout"; color: Theme.label3; lineHeight: 1.2
                text: "Every word you hover in the game or search in Lookup appears here, with the sentence it was in\nand how often it came up."
            }
        }

        // the list
        Item {
            visible: hp.rows.length > 0
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
                    model: hp.rows
                    delegate: Item {
                        id: rowItem
                        width: list.width
                        height: rowCol.implicitHeight + 22
                        readonly property bool frequent: modelData.count >= 3 && !modelData.saved
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
                            width: parent.width - 170
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
                                Label { text: modelData.word; textStyle: "headline"; font.pointSize: 0.75 * 14.5 }
                                Label { anchors.verticalCenter: parent.verticalCenter; text: modelData.pos; textStyle: "footnote"; color: Theme.label3 }
                            }
                            Label { width: parent.width; text: modelData.gloss; textStyle: "callout"; color: Theme.label2; wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight }
                            Label {
                                visible: modelData.context !== ""
                                width: parent.width
                                text: "“" + modelData.context + "”"
                                textStyle: "footnote"; color: Theme.label3; wrapMode: Text.WordWrap; font.italic: true
                                maximumLineCount: 2; elide: Text.ElideRight
                            }
                        }
                        Row {                      // right side: how often, when, save
                            anchors.right: parent.right; anchors.rightMargin: 10
                            y: 8
                            spacing: 8
                            Rectangle {
                                visible: modelData.count > 1
                                anchors.verticalCenter: parent.verticalCenter
                                height: 20; width: cnt.implicitWidth + 14; radius: 10
                                color: rowItem.frequent ? Theme.accentFill : Theme.controlFill
                                Label {
                                    id: cnt
                                    anchors.centerIn: parent
                                    text: "×" + modelData.count
                                    textStyle: "caption"; font.weight: Font.Bold
                                    color: rowItem.frequent ? "#ffffff" : Theme.label2
                                    font.features: { "tnum": 1 }
                                }
                                ToolTipLite { text: "Came up " + modelData.count + " times"; shown: cntHov.hovered }
                                HoverHandler { id: cntHov }
                            }
                            Label { anchors.verticalCenter: parent.verticalCenter; text: modelData.when; textStyle: "footnote"; color: Theme.label4 }
                            GlassButton {
                                anchors.verticalCenter: parent.verticalCenter
                                icon: "star"; kind: "plain"; small: true
                                iconColor: modelData.saved ? Theme.yellow : Theme.label3
                                tip: modelData.saved ? "In My Words" : "Save to My Words"
                                enabled: !modelData.saved
                                opacity: modelData.saved ? 1 : (rowHov.hovered ? 1 : 0.55)
                                onClicked: App.saveFromHistory(modelData.id)
                                Icon {
                                    anchors.centerIn: parent
                                    visible: modelData.saved
                                    name: "star"; size: 14; filled: true; color: Theme.yellow
                                }
                            }
                        }
                        HoverHandler { id: rowHov }
                        TapHandler {
                            acceptedButtons: Qt.LeftButton
                            onDoubleTapped: App.lookupRequested(modelData.word)
                        }
                        MouseArea {
                            anchors.fill: parent
                            acceptedButtons: Qt.RightButton
                            onClicked: (m) => {
                                rowMenu.row = modelData
                                rowMenu.items = [
                                    { label: "Look Up", value: "look", icon: "search" },
                                    { label: modelData.saved ? "In My Words" : "Save to My Words", value: "save", icon: "star", enabled: !modelData.saved },
                                    { label: "Copy “" + modelData.word + "”", value: "copy", icon: "copy" },
                                    { separator: true },
                                    { label: "Remove from History", value: "forget", icon: "trash", destructive: true }
                                ]
                                const p = mapToItem(list, m.x, m.y)
                                rowMenu.x = p.x; rowMenu.y = p.y
                                rowMenu.open()
                            }
                        }
                    }
                }
            }
            GlassMenu {
                id: rowMenu
                property var row: null
                onTriggered: (it) => {
                    if (it.value === "look") App.lookupRequested(row.word)
                    else if (it.value === "save") App.saveFromHistory(row.id)
                    else if (it.value === "copy") App.copyText(row.word)
                    else App.forgetHistory(row.id)
                }
            }
        }
    }
}
