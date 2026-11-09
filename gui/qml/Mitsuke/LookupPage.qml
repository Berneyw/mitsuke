import QtQuick
import QtQuick.Window

// Lookup: a glass search field in the toolbar, results on a glass card, recent searches as chips,
// and a banner when text recognition needs attention.
Page {
    id: lp
    key: "lookup"
    title: "Lookup"
    readonly property var res: App.result

    function lookup(q) { search.text = q; App.search(q, true); search.focusField(false) }
    function focusSearch() { search.focusField(true) }

    actions: [
        GlassButton {
            icon: "copy"; tip: "Copy result (Ctrl+C)"
            enabled: lp.res.has
            backdrop: lp.stageTex; backdropItem: lp.stage
            onClicked: App.copyResult()
        },
        GlassButton {
            icon: "star"
            iconColor: lp.res.saved ? Theme.yellow : Theme.label
            tip: lp.res.saved ? "Remove from My Words (Ctrl+S)" : "Save to My Words (Ctrl+S)"
            enabled: lp.res.has
            backdrop: lp.stageTex; backdropItem: lp.stage
            onClicked: App.toggleSave()
            Icon {   // filled star when saved
                anchors.centerIn: parent
                visible: lp.res.saved
                name: "star"; size: 16; filled: true; color: Theme.yellow
            }
        },
        TextBox {
            id: search
            search: true
            width: Math.min(420, Math.max(220, lp.width - 420))
            placeholder: "Search German words or phrases"
            backdrop: lp.stageTex; backdropItem: lp.stage
            onEdited: (t) => { debounce.restart(); if (!t) App.search("", false) }
            onSubmitted: (t) => { debounce.stop(); App.search(t, true) }
        }
    ]
    Timer { id: debounce; interval: 280; onTriggered: if (search.text.trim().length >= 2) App.search(search.text, false) }

    Shortcut {
        sequence: "Ctrl+C"
        enabled: lp.current && lp.res.has && !search.input.selectedText
        onActivated: App.copyResult()
    }

    body: Scroller {
        id: scroller
        Connections { target: App; function onResultChanged() { scroller.toTop() } }

        // ---- OCR banner
        Item {
            visible: !!App.state.ocrError
            width: parent.width
            height: visible ? bannerRow.implicitHeight + 28 : 0
            Glass {
                anchors.fill: parent; anchors.margins: -10; inset: 10
                radius: 14; refraction: 0
                tint: Theme.dark ? Qt.rgba(1, 0.84, 0.04, 0.10) : Qt.rgba(1, 0.97, 0.85, 0.85)
                shadow: Theme.dark ? 0.15 : 0.06; shadowSize: 8
            }
            Row {
                id: bannerRow
                x: 14; y: 14
                width: parent.width - 28
                spacing: 12
                Icon { name: "warning"; size: 20; color: Theme.yellow; y: 1 }
                Column {
                    width: parent.width - 140
                    spacing: 2
                    Label { text: "Text recognition isn’t available"; textStyle: "headline" }
                    Label { width: parent.width; text: App.state.ocrHelp || ""; textStyle: "footnote"; color: Theme.label3; wrapMode: Text.WordWrap }
                }
                GlassButton { text: "Try Again"; small: true; onClicked: App.retryOcr() }
            }
        }

        // ---- result
        Item {
            id: resultCard
            visible: lp.res.has
            width: parent.width
            height: visible ? wc.implicitHeight + 44 : 0
            transform: Translate { id: rise; y: 0 }
            ParallelAnimation {
                id: appear
                NumberAnimation { target: resultCard; property: "opacity"; from: 0; to: 1; duration: Theme.dur(200); easing.type: Easing.OutCubic }
                SpringAnimation { target: rise; property: "y"; from: 10; to: 0; spring: 4; damping: 0.5; epsilon: 0.05 }
            }
            Connections {
                target: App
                function onResultChanged() { if (lp.res.has && !Theme.reduceMotion) appear.restart() }
            }
            Glass {
                anchors.fill: parent; anchors.margins: -12; inset: 12
                radius: Theme.rCard; refraction: 0
                tint: Theme.groupTint
                specular: Theme.specular * 0.5
                shadow: Theme.dark ? 0.2 : 0.07; shadowSize: 12
            }
            WordCard {
                id: wc
                x: 22; y: 22
                width: parent.width - 44
                lines: lp.res.lines || []
                basePt: App.settings.font_size || 11
            }
            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.RightButton
                onClicked: (m) => {
                    const w = lp.res.word || lp.res.query
                    resMenu.items = [
                        { label: "Copy Result", value: "copy", shortcut: "Ctrl+C" },
                        { label: "Copy “" + w + "”", value: "word" },
                        { separator: true },
                        { label: lp.res.saved ? "Remove from My Words" : "Save to My Words", value: "save", shortcut: "Ctrl+S" },
                        { label: "Open in Wiktionary", value: "wiki", icon: "open" }
                    ]
                    resMenu.x = m.x; resMenu.y = m.y
                    resMenu.open()
                }
            }
            GlassMenu {
                id: resMenu
                onTriggered: (it) => {
                    const w = lp.res.word || lp.res.query
                    if (it.value === "copy") App.copyResult()
                    else if (it.value === "word") { App.copyText(w); App.flash("Copied “" + w + "”.") }
                    else if (it.value === "save") App.toggleSave()
                    else App.openWiktionary(w)
                }
            }
        }
        Label {
            visible: lp.res.has || (lp.res.footer || "") !== ""
            width: parent.width
            leftPadding: 4
            text: lp.res.footer || ""
            textStyle: "footnote"
            color: Theme.label3
        }

        // ---- empty states
        Column {
            visible: !lp.res.has
            width: parent.width
            spacing: 6
            Item { width: 1; height: 48 }
            Item {
                width: parent.width; height: 64
                Rectangle {
                    anchors.centerIn: parent
                    width: 64; height: 64; radius: 20
                    color: Theme.controlFill
                    Icon { anchors.centerIn: parent; name: "text.magnifyingglass"; size: 34; weight: 1.6; color: Theme.label3 }
                }
            }
            Item { width: 1; height: 8 }
            Label {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: lp.res.empty === "none" ? "No results for “" + lp.res.query + "”" : "Look up any German word"
                textStyle: "title2"
            }
            Label {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                textStyle: "callout"
                color: Theme.label3
                lineHeight: 1.2
                text: lp.res.empty === "none"
                      ? "Check the spelling, or try the dictionary form — for example “gehen” instead of “ging”."
                        + (App.state.hasOffline ? "" : "\nThe offline dictionary isn’t installed yet, so only online results are available.")
                      : "Type in the search field, or hold " + (App.state.keyName || "Shift") + " over a word in the game.\nPhrases and separable verbs work too."
            }
            Item { width: 1; height: 12 }
            GlassButton {
                visible: lp.res.empty === "none" && !App.state.hasOffline
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Download Offline Dictionary"
                kind: "primary"
                onClicked: lp.Window.window.page = "dictionary"
            }
            // recent searches
            Item {
                visible: lp.res.empty !== "none"
                width: parent.width
                height: recentCol.implicitHeight
                Column {
                    id: recentCol
                    width: parent.width
                    spacing: 10
                    readonly property var recent: App.state.recent && App.state.recent.length ? App.state.recent
                                                  : ["räumt auf", "auf jeden Fall", "warten auf", "Kühlschrank"]
                    Row {
                        anchors.horizontalCenter: parent.horizontalCenter
                        spacing: 6
                        Label {
                            anchors.verticalCenter: parent.verticalCenter
                            text: App.state.recent && App.state.recent.length ? "RECENT" : "TRY"
                            textStyle: "caption"
                            color: Theme.label3
                            font.letterSpacing: 0.6
                        }
                        GlassButton {
                            visible: App.state.recent && App.state.recent.length > 0
                            text: "Clear"; kind: "plain"; small: true
                            onClicked: App.clearRecent()
                        }
                    }
                    Row {
                        anchors.horizontalCenter: parent.horizontalCenter
                        spacing: 8
                        Repeater {
                            model: recentCol.recent.slice(0, 6)
                            GlassButton {
                                text: modelData
                                small: true
                                onClicked: lp.lookup(modelData)
                            }
                        }
                    }
                }
            }
        }
    }
}
