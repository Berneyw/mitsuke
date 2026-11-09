import QtQuick

// A setting with a slider and a typed value. Dragging applies the value live everywhere (cards, previews);
// it is saved when the slider settles. Typing a number applies it on Enter or when the field loses focus.
Row {
    id: ss
    property string key
    property real from: 0
    property real to: 100
    property real stepSize: 1
    property string unit: ""
    property real sliderWidth: 170
    readonly property real value: App.settings[key] !== undefined ? App.settings[key] : from
    spacing: 10

    GlassSlider {
        anchors.verticalCenter: parent.verticalCenter
        width: ss.sliderWidth
        from: ss.from; to: ss.to; stepSize: ss.stepSize
        value: ss.value
        unit: ss.unit
        onMoved: (v) => App.setLive(ss.key, v)
        onCommitted: (v) => App.set(ss.key, v)
    }
    TextBox {
        id: num
        anchors.verticalCenter: parent.verticalCenter
        width: 76
        numeric: true
        suffix: ss.unit
        text: String(Math.round(ss.value))
        function apply() {
            const v = Math.max(ss.from, Math.min(ss.to, parseInt(input.text)))
            if (!isNaN(v)) App.set(ss.key, Math.round(v / ss.stepSize) * ss.stepSize)
            input.text = Qt.binding(() => String(Math.round(ss.value)))
        }
        onSubmitted: apply()
        Connections {
            target: num.input
            function onActiveFocusChanged() { if (!num.input.activeFocus) num.apply() }
        }
    }
}
