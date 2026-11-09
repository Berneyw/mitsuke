import QtQuick

// Text in the Mitsuke type scale. Display sizes (≥ 19 px) use SF Pro Display, the rest SF Pro Text.
Text {
    property string textStyle: "body"
    readonly property var _s: ({
        "largeTitle": [Theme.largeTitle, Font.Bold, true, -0.4],
        "title1": [Theme.title1, Font.Bold, true, -0.3],
        "title2": [Theme.title2, Font.DemiBold, true, -0.2],
        "title3": [Theme.title3, Font.DemiBold, false, -0.1],
        "headline": [Theme.headline, Font.DemiBold, false, -0.05],
        "body": [Theme.body, Font.Normal, false, -0.05],
        "callout": [Theme.callout, Font.Normal, false, 0],
        "subhead": [Theme.subhead, Font.Normal, false, 0],
        "footnote": [Theme.footnote, Font.Normal, false, 0.05],
        "caption": [Theme.caption, Font.Medium, false, 0.1]
    })
    readonly property var _v: _s[textStyle] || _s.body
    font.family: _v[2] ? Theme.displayFamily : Theme.textFamily
    font.pointSize: 0.75 * (_v[0])
    font.weight: _v[1]
    font.letterSpacing: _v[3]
    font.hintingPreference: Font.PreferNoHinting
    color: Theme.label
    renderType: Text.QtRendering
    textFormat: Text.PlainText
    lineHeight: 1.08
    wrapMode: Text.NoWrap
}
