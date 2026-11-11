import QtQuick

// A dictionary result drawn from render.build() lines: headword row with gender / part-of-speech pills,
// numbered meanings, examples, German definitions, separators. Used in Lookup, the in-game card and the
// pinned card; `palette` lets the game card keep its own contrast-checked colours.
Column {
    id: card
    property var lines: []
    property real basePt: 11
    property var colors: ({})
    property bool interactive: true                   // the hover card in the game can't be clicked
    property bool onGlass: false
    property bool showIpa: App.settings.pron_ipa !== false
    readonly property real px: basePt * 96 / 72
    readonly property real titleH: Math.round((px + 8) * 1.32)     // one line height for everything in the title row
    readonly property color cLabel: colors.label || Theme.label
    readonly property color cLabel3: colors.label3 || Theme.label3
    readonly property color cMatch: colors.match || Theme.match
    readonly property color cGerman: colors.german || Theme.german
    readonly property color cSep: colors.separator || Theme.separator
    readonly property color cPill: colors.pill || Theme.controlFill
    readonly property color cPillFg: colors.pillFg || Theme.label2
    spacing: 0

    readonly property var sizes: ({ word: px + 8, word2: px + 3, meta: px - 1.5, match: px - 1, gloss: px,
                                    example: px - 1.5, german: px, num: px - 1, translation: px + 2 })
    readonly property var gaps: ({ meta: 3, match: 3, gloss: 7, example: 3, german: 9, translation: 8 })

    Repeater {
        model: card.lines
        delegate: Loader {
            width: card.width
            property var d: modelData
            sourceComponent: d.kind === "sep" ? sepC : d.kind === "title" ? titleC : paraC
        }
    }

    Component {
        id: sepC
        Item {
            height: 25
            Rectangle { width: parent.width; height: 1; anchors.verticalCenter: parent.verticalCenter; color: card.cSep }
        }
    }
    Component {
        id: titleC
        Flow {
            spacing: 7
            bottomPadding: 4
            Repeater {
                model: d.items
                delegate: Loader {
                    property var it: modelData
                    sourceComponent: it.kind === "text" ? wordC : it.kind === "ipa" ? ipaC
                                   : it.kind === "speak" ? speakC : pillC
                }
            }
        }
    }
    Component {
        id: wordC
        Label {
            text: it.text
            font.family: Theme.displayFamily
            font.pointSize: 0.75 * (card.sizes[it.style] || card.px + 8)
            font.weight: it.style === "word" ? Font.Bold : Font.DemiBold
            font.letterSpacing: -0.3
            color: card.cLabel
            height: Math.max(implicitHeight, card.titleH)
            verticalAlignment: Text.AlignVCenter
        }
    }
    Component {
        id: ipaC
        Label {
            visible: card.showIpa                       // invisible items take no place in the Flow
            text: it.text
            font.pointSize: 0.75 * (card.px - 0.5)
            color: card.cLabel3
            height: card.titleH
            verticalAlignment: Text.AlignVCenter
        }
    }
    Component {
        id: speakC
        Item {
            visible: card.interactive
            width: 26
            height: card.titleH
            SpeakButton {
                anchors.verticalCenter: parent.verticalCenter
                word: it.text
                audio: it.audio || []
                onGlass: card.onGlass
            }
        }
    }
    Component {
        id: pillC
        Item {                                          // centred on the title line, like the word itself
            width: pill.width
            height: card.titleH
            Rectangle {
                id: pill
                readonly property bool art: it.text === "der" || it.text === "die" || it.text === "das"
                anchors.verticalCenter: parent.verticalCenter
                height: Math.round(card.px + 9)
                width: pl.implicitWidth + 14
                radius: height / 2
                color: art ? Theme.gender[it.text] : card.cPill
                Label {
                    id: pl
                    anchors.centerIn: parent
                    text: it.text
                    font.pointSize: 0.75 * (card.px - 1.5)
                    font.weight: parent.art ? Font.Bold : Font.Medium
                    color: parent.art ? "#ffffff" : card.cPillFg
                }
            }
        }
    }
    Component {
        id: paraC
        Item {
            height: txt.implicitHeight + (card.gaps[d.style] || 0)
            Label {
                visible: d.prefix !== ""
                y: card.gaps[d.style] || 0
                text: d.prefix
                font.pointSize: 0.75 * (card.sizes.num)
                font.weight: Font.DemiBold
                color: card.cLabel3
                font.features: { "tnum": 1 }
            }
            Label {
                id: txt
                x: d.indent ? 18 : 0
                y: card.gaps[d.style] || 0
                width: parent.width - x
                text: d.text
                wrapMode: Text.Wrap
                font.pointSize: 0.75 * (card.sizes[d.style] || card.px)
                font.italic: d.style === "example"
                font.weight: d.style === "translation" ? Font.Medium : Font.Normal
                lineHeight: 1.12
                color: d.style === "meta" || d.style === "example" ? card.cLabel3
                     : d.style === "match" ? card.cMatch
                     : d.style === "german" ? card.cGerman : card.cLabel
            }
        }
    }
}
