import QtQuick
import QtQuick.Window

// Liquid Glass surface (shaders/glass.frag). With a `backdrop` texture it refracts, blurs and tints what is
// under it, live; without one it is a translucent tinted pane over the window material. The rim lights up on
// the side facing the pointer, with a softer inner reflection opposite. `inset` leaves room for the shadow.
ShaderEffect {
    id: g
    property Item backdrop: null          // texture provider: ShaderEffectSource or Image (mipmap: true)
    property Item backdropItem: null      // coordinate space the texture covers; null = exactly this item
    property real inset: 0
    property real radius: 12
    property real bezel: Math.min(radius, 14)
    property real refraction: 8
    property real zoom: 1.0
    property real dispersion: 0.25
    property real blur: 0
    property color tint: Theme.glassTint
    property real specular: Theme.specular
    property real shadow: 0
    property real shadowSize: 10
    property real saturation: 1.35
    property real lift: 0
    property real edge: Theme.glassEdge
    property real fadeBottom: 0
    property real passAlpha: 0
    property color base: Theme.dark ? "#1d1d21" : "#ececf0"
    property point lightScene: (Window.window && Window.window.pointer !== undefined) ? Window.window.pointer
                                                                                     : Qt.point(-400, -600)

    // ---- shader inputs
    property var source: backdrop ? backdrop : fallbackTex
    readonly property size itemSize: Qt.size(Math.max(1, width), Math.max(1, height))
    readonly property rect shape: Qt.rect(inset, inset, Math.max(1, width - 2 * inset), Math.max(1, height - 2 * inset))
    property rect srcRect: Qt.rect(0, 0, 1, 1)
    readonly property real hasSource: backdrop ? 1 : 0
    readonly property real darkMode: Theme.dark ? 1 : 0
    readonly property point light: {
        lightScene; x; y; width; height
        return g.mapFromItem(null, lightScene.x, lightScene.y)
    }
    fragmentShader: Qt.resolvedUrl("shaders/glass.frag.qsb")

    function syncSrc() {
        if (!backdropItem || backdropItem.width <= 0 || backdropItem.height <= 0) {
            if (srcRect.x !== 0 || srcRect.width !== 1) srcRect = Qt.rect(0, 0, 1, 1)
            return
        }
        const p = g.mapToItem(backdropItem, 0, 0)          // two corners: scaled ancestors map correctly
        const q = g.mapToItem(backdropItem, width, height)
        const r = Qt.rect(p.x / backdropItem.width, p.y / backdropItem.height,
                          (q.x - p.x) / backdropItem.width, (q.y - p.y) / backdropItem.height)
        if (Math.abs(r.x - srcRect.x) > 1e-6 || Math.abs(r.y - srcRect.y) > 1e-6
                || Math.abs(r.width - srcRect.width) > 1e-6 || Math.abs(r.height - srcRect.height) > 1e-6)
            srcRect = r
    }
    onXChanged: syncSrc()
    onYChanged: syncSrc()
    onWidthChanged: syncSrc()
    onHeightChanged: syncSrc()
    onBackdropItemChanged: syncSrc()
    Component.onCompleted: syncSrc()
    Connections {   // ancestors move too (layouts, scrolling, popups): follow every frame that animates
        target: g.backdropItem && g.Window.window ? g.Window.window : null
        function onAfterAnimating() { g.syncSrc() }
    }

    // a 1×1 stand-in so the sampler is always bound
    ShaderEffectSource {
        id: fallbackTex
        visible: false
        width: 1; height: 1
        sourceItem: Item { width: 1; height: 1 }
    }
}
