import QtQuick

// A small game-like scene with the word card floating over it, rendered with exactly the in-game card's
// glass. Every Word Card and Liquid Glass setting shows here instantly, including while sliders move.
Item {
    id: cp
    width: 520
    height: Math.max(200, card.y + card.height * cardScale + 22)
    clip: true
    readonly property real cardScale: Math.min(1, (width - 40) / Math.max(1, App.settings.card_width || 440))

    Item {
        id: scene
        anchors.fill: parent
        Rectangle {
            anchors.fill: parent
            radius: 12
            gradient: Gradient {
                GradientStop { position: 0.0; color: "#2a6f97" }
                GradientStop { position: 0.55; color: "#61a5c2" }
                GradientStop { position: 1.0; color: "#f4a259" }
            }
        }
        Rectangle { x: parent.width * 0.62; y: -30; width: 180; height: 180; radius: 90; color: "#ffd166"; opacity: 0.85 }
        Rectangle { x: 30; y: parent.height - 70; width: parent.width * 0.5; height: 90; radius: 40; color: "#3a7d44" }
        Rectangle { x: parent.width * 0.45; y: parent.height - 52; width: parent.width * 0.6; height: 80; radius: 36; color: "#2d6a4f" }
        Rectangle {   // a dialogue bubble like the game's
            x: 18; y: 16
            width: bubble.implicitWidth + 28; height: bubble.implicitHeight + 18
            radius: 12
            color: Qt.rgba(1, 1, 1, 0.9)
            Text {
                id: bubble
                anchors.centerIn: parent
                text: "Ich räume heute mein Zimmer auf."
                font.family: Theme.textFamily
                font.pointSize: 0.75 * (14)
                color: "#1d3557"
            }
        }
        TextMetrics { id: pre; font: bubble.font; text: "Ich " }
        TextMetrics { id: word; font: bubble.font; text: "räume" }
        Rectangle {   // the word being read, marked like in the game
            x: 18 + (bubble.parent.width - bubble.width) / 2 + pre.advanceWidth - 3
            y: 16 + (bubble.parent.height - bubble.height) / 2 - 1
            width: word.advanceWidth + 6; height: bubble.height + 2; radius: 4
            color: Qt.rgba(1, 0.84, 0.04, 0.42)
            border.width: 1; border.color: Qt.rgba(1, 0.84, 0.04, 0.9)
            opacity: App.settings.highlight ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Theme.fast } }
        }
    }
    ShaderEffectSource { id: tex; sourceItem: scene; live: true; mipmap: true; visible: false }

    GameCard {
        id: card
        x: 26
        y: 58
        width: (App.settings.card_width || 440)
        scale: cp.cardScale
        transformOrigin: Item.TopLeft
        backdrop: tex
        backdropItem: scene
        readonly property var all: [
            { kind: "title", items: [{ kind: "text", text: "aufräumen", style: "word" }, { kind: "pill", text: "verb", fill: "neutral", fg: "" },
                                     { kind: "pill", text: "separable", fill: "neutral", fg: "" }] },
            { kind: "para", text: "Found in text as “räume … auf”", style: "match", prefix: "", indent: false },
            { kind: "para", text: "räumt auf · räumte auf · hat aufgeräumt", style: "meta", prefix: "", indent: false },
            { kind: "para", text: "to tidy up, to clean up", style: "gloss", prefix: "1", indent: true },
            { kind: "para", text: "Räum bitte dein Zimmer auf! — Please tidy your room!", style: "example", prefix: "", indent: true },
            { kind: "para", text: "to clear away", style: "gloss", prefix: "2", indent: true }
        ]
        lines: all.filter((l) => l.style !== "example" || App.settings.card_examples)
                  .filter((l) => l.prefix !== "2" || (App.settings.card_senses || 3) > 1)
    }
}
