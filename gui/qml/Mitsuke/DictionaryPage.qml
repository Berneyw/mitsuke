import QtQuick
import QtQuick.Window

// Dictionary: install / update the offline Wiktionary data with live progress, and its sources.
Page {
    id: dp
    key: "dictionary"
    title: "Dictionary"
    readonly property var st: App.state
    readonly property var prog: st.progress || ({ active: false })

    function action() {
        const verb = st.hasOffline ? "Update" : "Download"
        dp.Window.window.ask(verb + " the offline dictionary?",
            "Mitsuke downloads Wiktionary (about 4.3 GB) and builds a compact dictionary (about 110 MB). "
            + "This takes 5–15 minutes and runs in the background — you can keep playing.",
            [{ label: verb, value: "go" }, { label: "Cancel", value: "no" }],
            (v) => { if (v === "go") App.startDictionary() })
    }

    actions: [
        GlassButton {
            text: dp.st.dictButton || "Update"
            kind: dp.st.dictPrimary ? "primary" : "secondary"
            small: true
            enabled: !!dp.st.dictEnabled
            backdrop: dp.stageTex; backdropItem: dp.stage
            onClicked: dp.action()
        }
    ]

    body: Scroller {
        Label {
            width: parent.width
            leftPadding: 4
            text: "Offline Wiktionary data: gender, plural, inflections and examples. Lookups are instant and work without internet."
            textStyle: "callout"; color: Theme.label3
            wrapMode: Text.WordWrap
        }
        Item {
            width: parent.width
            height: dcol.implicitHeight + 40
            Glass {
                anchors.fill: parent; anchors.margins: -12; inset: 12
                radius: Theme.rCard; refraction: 0
                tint: Theme.groupTint
                specular: Theme.specular * 0.5
                shadow: Theme.dark ? 0.2 : 0.07; shadowSize: 12
            }
            Column {
                id: dcol
                x: 20; y: 20
                width: parent.width - 40
                spacing: 14
                Row {
                    width: parent.width
                    spacing: 14
                    Rectangle {
                        width: 46; height: 46; radius: 12
                        gradient: Gradient {
                            GradientStop { position: 0; color: "#ffb340" }
                            GradientStop { position: 1; color: "#ff8a00" }
                        }
                        Icon { anchors.centerIn: parent; name: "book"; size: 26; weight: 1.7; color: "#ffffff" }
                    }
                    Column {
                        width: parent.width - 60
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 2
                        Label { text: "Offline dictionary"; textStyle: "headline"; font.pointSize: 0.75 * (14.5) }
                        Label { width: parent.width; text: dp.st.dictStatus || ""; textStyle: "footnote"; color: Theme.label3; wrapMode: Text.WordWrap }
                    }
                }
                Column {
                    visible: !!dp.prog.active
                    width: parent.width
                    spacing: 7
                    Item {      // progress: capsule track with a glassy fill and a moving sheen
                        width: parent.width; height: 8
                        Rectangle { anchors.fill: parent; radius: 4; color: Theme.trackOff }
                        Rectangle {
                            id: fill
                            width: Math.max(8, parent.width * (dp.prog.frac || 0))
                            height: parent.height; radius: 4
                            color: Theme.accentFill
                            Behavior on width { NumberAnimation { duration: Theme.slow; easing.type: Easing.OutCubic } }
                            clip: true
                            Rectangle {
                                width: 60; height: parent.height
                                gradient: Gradient {
                                    orientation: Gradient.Horizontal
                                    GradientStop { position: 0; color: "transparent" }
                                    GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, 0.45) }
                                    GradientStop { position: 1; color: "transparent" }
                                }
                                NumberAnimation on x { from: -60; to: fill.width + 60; duration: 1600; loops: Animation.Infinite; running: dp.prog.active && !Theme.reduceMotion }
                            }
                        }
                    }
                    Label {
                        text: ((dp.prog.text || "") + "  " + (dp.prog.sub || "")).trim()
                        textStyle: "footnote"; color: Theme.label3
                    }
                }
            }
        }

        SettingsGroup {
            title: "Sources"
            icon: "book"
            iconColor: "#8e8e93"
            footer: "Dictionary data © Wiktionary contributors, CC BY-SA 4.0."
            SettingRow {
                title: "German definitions"
                desc: "Definitions from the German Wiktionary. Applies after the next update."
                GlassSwitch { checked: !!App.settings.german_definitions; onToggled: (v) => App.set("german_definitions", v) }
            }
            SettingRow {
                title: "Search online when a word is missing"
                desc: "Looks words up on en.wiktionary.org. Needs internet."
                GlassSwitch { checked: !!App.settings.online_fallback; onToggled: (v) => App.set("online_fallback", v) }
            }
        }
    }
}
