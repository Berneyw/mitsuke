pragma Singleton
import QtQuick

// Design tokens: colour (dark / light, with Increase Contrast), type, spacing, radii, motion.
// Colours follow Apple's system palette; materials are expressed as tints laid over live glass.
QtObject {
    id: t
    property var settings: ({})
    property bool systemDark: Qt.styleHints.colorScheme !== Qt.ColorScheme.Light
    readonly property string appearance: settings.appearance || "system"
    readonly property bool dark: appearance === "dark" || (appearance === "system" && systemDark)
    readonly property bool reduceMotion: !!settings.reduce_motion
    readonly property bool reduceTransparency: !!settings.reduce_transparency
    readonly property bool highContrast: !!settings.increase_contrast

    // ---- type
    readonly property string textFamily: hasSF ? "SF Pro Text" : "Segoe UI Variable Text"
    readonly property string displayFamily: hasSF ? "SF Pro Display" : "Segoe UI Variable Display"
    property bool hasSF: true
    readonly property real largeTitle: 26
    readonly property real title1: 22
    readonly property real title2: 19
    readonly property real title3: 16
    readonly property real headline: 13.5
    readonly property real body: 13.5
    readonly property real callout: 12.5
    readonly property real subhead: 12
    readonly property real footnote: 11.5
    readonly property real caption: 10.5

    // ---- spacing / radii
    readonly property int xs: 4
    readonly property int s: 8
    readonly property int m: 12
    readonly property int l: 16
    readonly property int xl: 24
    readonly property int xxl: 32
    readonly property int rCard: 18
    readonly property int rGroup: 14
    readonly property int rControl: 9
    readonly property int sidebarWidth: 232
    readonly property int toolbarHeight: 60
    readonly property int contentMax: 720

    // ---- motion (springs feel physical; Reduce Motion turns them into instant changes)
    function dur(ms) { return reduceMotion ? 0 : ms }
    readonly property int fast: reduceMotion ? 0 : 140
    readonly property int normal: reduceMotion ? 0 : 240
    readonly property int slow: reduceMotion ? 0 : 380

    // ---- colour
    readonly property color accent: dark ? "#0a84ff" : "#007aff"
    readonly property color accentFill: dark ? "#0a84ff" : "#0071e3"
    readonly property color accentText: dark ? "#64b0ff" : "#0066cc"
    readonly property color green: dark ? "#30d158" : "#28a745"
    readonly property color yellow: dark ? "#ffd60a" : "#c78a00"
    readonly property color orange: dark ? "#ff9f0a" : "#e07800"
    readonly property color red: dark ? "#ff453a" : "#e0352b"
    readonly property color label: dark ? "#f5f5f7" : "#1d1d1f"
    readonly property color label2: dark ? Qt.rgba(235/255, 235/255, 245/255, highContrast ? 0.86 : 0.74)
                                         : Qt.rgba(60/255, 60/255, 67/255, highContrast ? 0.92 : 0.82)
    readonly property color label3: dark ? Qt.rgba(235/255, 235/255, 245/255, highContrast ? 0.72 : 0.56)
                                         : Qt.rgba(60/255, 60/255, 67/255, highContrast ? 0.80 : 0.62)
    readonly property color label4: dark ? Qt.rgba(235/255, 235/255, 245/255, highContrast ? 0.48 : 0.30)
                                         : Qt.rgba(60/255, 60/255, 67/255, highContrast ? 0.52 : 0.32)
    readonly property color separator: dark ? Qt.rgba(1, 1, 1, highContrast ? 0.22 : 0.10)
                                            : Qt.rgba(0, 0, 0, highContrast ? 0.24 : 0.10)
    readonly property color match: dark ? "#7fc3ff" : "#0b62a8"
    readonly property color german: dark ? "#cbbcff" : "#5b3fb8"
    readonly property var gender: ({ "der": "#3d7fe0", "die": "#e0517d", "das": "#2fa463" })

    // window material: the tint over Acrylic. Reduce Transparency makes it opaque.
    readonly property color windowTint: reduceTransparency ? (dark ? "#1c1c1e" : "#f2f2f4")
                                        : (dark ? Qt.rgba(0.085, 0.085, 0.095, 0.72) : Qt.rgba(0.965, 0.965, 0.975, 0.84))
    readonly property color contentTint: reduceTransparency ? (dark ? "#1c1c1e" : "#f5f5f7")
                                         : (dark ? Qt.rgba(0.10, 0.10, 0.11, 0.55) : Qt.rgba(1, 1, 1, 0.48))
    // glass surfaces
    readonly property color glassTint: dark ? Qt.rgba(0.16, 0.16, 0.18, reduceTransparency ? 0.98 : 0.42)
                                            : Qt.rgba(0.98, 0.98, 1.0, reduceTransparency ? 0.98 : 0.55)
    readonly property color groupTint: dark ? Qt.rgba(1, 1, 1, reduceTransparency ? 0.07 : 0.055)
                                            : Qt.rgba(1, 1, 1, reduceTransparency ? 1.0 : 0.74)
    readonly property color menuTint: dark ? Qt.rgba(0.13, 0.13, 0.15, reduceTransparency ? 0.99 : 0.62)
                                           : Qt.rgba(0.985, 0.985, 0.99, reduceTransparency ? 0.99 : 0.72)
    readonly property color controlFill: dark ? Qt.rgba(1, 1, 1, 0.10) : Qt.rgba(0, 0, 0, 0.055)
    readonly property color controlHover: dark ? Qt.rgba(1, 1, 1, 0.15) : Qt.rgba(0, 0, 0, 0.085)
    readonly property color controlPressed: dark ? Qt.rgba(1, 1, 1, 0.20) : Qt.rgba(0, 0, 0, 0.12)
    readonly property color trackOff: dark ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(0, 0, 0, 0.10)
    readonly property color fieldFill: dark ? Qt.rgba(1, 1, 1, 0.075) : Qt.rgba(1, 1, 1, 0.78)
    readonly property color edge: dark ? Qt.rgba(1, 1, 1, highContrast ? 0.40 : 0.13) : Qt.rgba(0, 0, 0, highContrast ? 0.35 : 0.08)
    readonly property real specular: reduceTransparency ? 0.25 : (dark ? 0.75 : 0.9)
    readonly property real glassEdge: highContrast ? 0.85 : (dark ? 0.30 : 0.55)
    readonly property color selection: dark ? Qt.rgba(10/255, 132/255, 1, 0.30) : Qt.rgba(0, 122/255, 1, 0.16)
    // what a local glass lens sees through a control's transparent parts: the group panel
    readonly property color panelBase: dark ? "#262629" : "#f8f8fa"
    readonly property color shadowColor: Qt.rgba(0, 0, 0, dark ? 0.55 : 0.18)
}
