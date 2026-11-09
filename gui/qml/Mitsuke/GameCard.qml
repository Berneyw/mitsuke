import QtQuick

// The in-game word card on Liquid Glass. `backdrop` is the live picture of what is behind the card (the
// game, captured while the card is excluded from capture). Style, transparency, thickness and highlights
// come from the settings; `minTint` is the opacity floor that keeps text at 4.5:1 over bright scenes.
Item {
    id: gcard
    property var lines: []
    property var s: App.settings
    property Item backdrop: null
    property Item backdropItem: null
    property real minTint: 0
    property bool pinned: false
    property real pad: 16
    property real topPad: pad
    property alias card: wc
    readonly property bool dark: Theme.dark
    readonly property bool glassOn: !!s.glass && !s.reduce_transparency && backdrop !== null
    readonly property string style: s.glass_style || "glass"
    readonly property real thick: s.glass_thickness === "thin" ? 0.6 : s.glass_thickness === "thick" ? 1.6 : 1.0
    // Glass: frosted and neutral. Clear: barely frosted, a dimming layer, strong lensing and rim light.
    // Tinted: the glass takes the accent colour.
    readonly property real tintAlpha: {
        if (!glassOn) return 1
        let a = 0.95 - 0.9 * (s.glass_transparency !== undefined ? s.glass_transparency : 55) / 100
        if (style === "tinted") a = Math.min(0.97, 0.35 + a * 0.7)
        else if (style === "clear") a *= 0.6
        return Math.max(a, minTint)
    }
    readonly property color base: style === "tinted" ? (dark ? "#0b3a86" : "#cfe0ff")
                                  : style === "clear" ? (dark ? "#000000" : "#ffffff")
                                  : (dark ? "#1c1c1f" : "#f6f6f8")
    implicitHeight: wc.implicitHeight + topPad + pad

    Glass {
        anchors.fill: parent
        anchors.margins: -22
        inset: 22
        radius: 18
        bezel: 12 + 8 * gcard.thick
        refraction: gcard.glassOn ? (gcard.style === "clear" ? 12 + 12 * gcard.thick : 7 + 9 * gcard.thick) : 0
        blur: gcard.glassOn ? (gcard.style === "clear" ? 1.5 : 16) * gcard.thick : 0
        dispersion: gcard.glassOn ? (gcard.style === "clear" ? 0.5 : 0.28) : 0
        saturation: gcard.style === "tinted" ? 1.1 : gcard.style === "clear" ? 1.2 : 1.7
        backdrop: gcard.glassOn ? gcard.backdrop : null
        backdropItem: gcard.backdropItem
        tint: Qt.rgba(gcard.base.r, gcard.base.g, gcard.base.b, gcard.glassOn ? gcard.tintAlpha : 0.97)
        specular: s.glass_highlight ? (gcard.style === "clear" ? 1.3 : gcard.dark ? 0.85 : 1.0) : 0.15
        shadow: gcard.dark ? 0.5 : 0.25
        shadowSize: 18
        edge: s.increase_contrast ? 0.95 : (gcard.dark ? 0.32 : 0.6)
        Behavior on tint { ColorAnimation { duration: Theme.dur(240); easing.type: Easing.OutCubic } }
        Behavior on blur { NumberAnimation { duration: Theme.dur(240); easing.type: Easing.OutCubic } }
        Behavior on refraction { NumberAnimation { duration: Theme.dur(240); easing.type: Easing.OutCubic } }
    }
    Item {                       // text clips to the card when it has to be shorter than its content
        x: 0; y: 0
        width: parent.width; height: parent.height
        clip: true
        WordCard {
            id: wc
            x: gcard.pad; y: gcard.topPad
            width: parent.width - 2 * gcard.pad
            lines: gcard.lines
            basePt: gcard.s.font_size || 11
            colors: gcard.dark
                     ? { label: "#ffffff", label3: "#d1d1d6", match: "#9ccaff", german: "#d9cfff", separator: Qt.rgba(1, 1, 1, 0.22),
                         pill: Qt.rgba(1, 1, 1, 0.18), pillFg: "#ffffff" }
                     : { label: "#1d1d1f", label3: "#3a3a3c", match: "#0b5aa0", german: "#4a2fa8", separator: Qt.rgba(0, 0, 0, 0.14),
                         pill: Qt.rgba(0, 0, 0, 0.08), pillFg: "#1d1d1f" }
        }
    }
}
