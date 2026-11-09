import QtQuick

// Pronunciation button: a small glass circle with a speaker. While the word sounds, the waves pulse; the
// tooltip says whether it's a native-speaker recording (and where it's from) or the Windows voice.
Item {
    id: sb
    property string word: ""
    property var audio: []
    property color tint: Theme.label2
    property bool onGlass: false                      // on the game card: lighter fill, white glyphs
    readonly property string key: word
    readonly property bool playing: App.playingKey === key && key !== ""
    readonly property bool hasRecording: audio && audio.length > 0
    width: 26; height: 26

    readonly property string tip: {
        if (hasRecording) {
            const r = audio[0].r || ""
            return "Listen — native speaker" + (r ? " (" + r + ")" : "")
        }
        return App.state.voiceAvailable ? "Listen — Windows voice" : "No recording for this word"
    }
    opacity: hasRecording || App.state.voiceAvailable ? 1 : 0.4

    property real hv: ma.containsMouse ? 1 : 0
    Behavior on hv { NumberAnimation { duration: Theme.dur(160); easing.type: Easing.OutCubic } }

    Item {
        anchors.fill: parent
        scale: Theme.reduceMotion ? 1 : (ma.pressed ? 0.9 : 1 + 0.08 * sb.hv)
        Behavior on scale { SpringAnimation { spring: 6; damping: 0.38; epsilon: 0.0015 } }
        Glass {
            anchors.fill: parent
            anchors.margins: -5
            inset: 5
            radius: height
            bezel: 6
            refraction: 0
            tint: sb.playing ? Qt.rgba(Theme.accentFill.r, Theme.accentFill.g, Theme.accentFill.b, 0.9)
                  : sb.onGlass ? Qt.rgba(1, 1, 1, 0.14 + 0.1 * sb.hv)
                  : (Theme.dark ? Qt.rgba(1, 1, 1, 0.09 + 0.07 * sb.hv) : Qt.rgba(1, 1, 1, 0.75 + 0.2 * sb.hv))
            specular: Theme.specular * (0.6 + 0.6 * sb.hv)
            shadow: Theme.dark ? 0.22 : 0.08
            shadowSize: 4 + 2 * sb.hv
            Behavior on tint { ColorAnimation { duration: Theme.fast } }
        }
        readonly property color glyph: sb.playing ? "#ffffff" : (sb.onGlass ? "#ffffff" : sb.tint)
        Icon { anchors.centerIn: parent; anchors.horizontalCenterOffset: -1; name: "speaker"; size: 15; weight: 1.5; color: parent.glyph }
        Icon {
            id: w1
            anchors.centerIn: parent; anchors.horizontalCenterOffset: -1
            name: "speaker.wave1"; size: 15; weight: 1.5; color: parent.glyph
            opacity: sb.playing ? 1 : 0.85
        }
        Icon {
            id: w2
            anchors.centerIn: parent; anchors.horizontalCenterOffset: -1
            name: "speaker.wave2"; size: 15; weight: 1.5; color: parent.glyph
            opacity: sb.playing ? 1 : 0.55
        }
        SequentialAnimation {                          // the waves ripple while it plays
            running: sb.playing && !Theme.reduceMotion
            loops: Animation.Infinite
            onStopped: { w1.opacity = Qt.binding(() => sb.playing ? 1 : 0.85); w2.opacity = Qt.binding(() => sb.playing ? 1 : 0.55) }
            ParallelAnimation {
                NumberAnimation { target: w1; property: "opacity"; to: 1; duration: 220; easing.type: Easing.OutQuad }
                NumberAnimation { target: w2; property: "opacity"; to: 0.25; duration: 220 }
            }
            ParallelAnimation {
                NumberAnimation { target: w1; property: "opacity"; to: 0.45; duration: 260 }
                NumberAnimation { target: w2; property: "opacity"; to: 1; duration: 260; easing.type: Easing.OutQuad }
            }
        }
    }
    MouseArea {
        id: ma
        anchors.fill: parent
        anchors.margins: -3
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: sb.playing ? App.stopSpeaking() : App.speak(sb.key, sb.word, sb.audio)
    }
    ToolTipLite { text: sb.tip; shown: ma.containsMouse }
}
