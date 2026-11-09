import QtQuick

// A dictionary result drawn from render.build() lines: headword row with gender / part-of-speech pills,
// numbered meanings, examples, German definitions, separators. Used in Lookup, the in-game card and the
// pinned card; `palette` lets the game card keep its own contrast-checked colours.
Column {
    id: card
    property var lines: []
    property real basePt: 11
    property var colors: ({})
    readonly property real px: basePt * 96 / 72
    readonly property color cLabel: colors.label || Theme.label
    readonly property color cLabel3: colors.label3 || Theme.label3
    readonly property color cMatch: colors.match || Theme.match
    readonly property color cGerman: colors.german || Theme.german
    readonly property color cSep: colors.separator || Theme.separator
    readonly property color cPill: colors.pill || Theme.controlFill
    readonly property color cPillFg: colors.pillFg || Theme.label2
    spacing: 0

    readonly property var sizes: ({ word: px + 8, word2: px + 3, meta: px - 1.5, match: px - 1, gloss: px,
                                    example: px - 1.5, german: px, num: px - 1 })
    readonly property var gaps: ({ meta: 3, match: 3, gloss: 7, example: 3, german: 9 })

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
                    sourceComponent: it.kind === "text" ? wordC : pillC
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
            height: Math.max(implicitHeight, 22)
            verticalAlignment: Text.AlignVCenter
        }
    }
    Component {
        id: pillC
        Rectangle {
            readonly property bool art: it.text === "der" || it.text === "die" || it.text === "das"
            height: Math.round(card.px + 9)
            width: pl.implicitWidth + 14
            radius: height / 2
            y: 2
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
                lineHeight: 1.12
                color: d.style === "meta" || d.style === "example" ? card.cLabel3
                     : d.style === "match" ? card.cMatch
                     : d.style === "german" ? card.cGerman : card.cLabel
            }
        }
    }
}
