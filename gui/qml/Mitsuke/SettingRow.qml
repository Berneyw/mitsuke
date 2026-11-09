import QtQuick

// One settings row: title and description on the left, the control on the right. Hidden when the
// settings search doesn't match its words; dimmed (and inert) when disabled.
Item {
    id: row
    property string title: ""
    property string desc: ""
    property string keywords: ""
    property bool first: false
    property bool active: true
    property string query: parent && parent.parent && parent.parent.parent ? (parent.parent.parent.query || "") : ""
    default property alias control: holder.data
    readonly property bool matches: {
        const q = query.trim().toLowerCase()
        if (!q) return true
        return (title + " " + desc + " " + keywords).toLowerCase().indexOf(q) >= 0
    }
    visible: matches
    onMatchesChanged: if (parent && parent.parent && parent.parent.parent && parent.parent.parent.relayout) parent.parent.parent.relayout()
    property bool wide: false                     // the control goes under the title, full width
    width: parent ? parent.width : 400
    height: wide ? texts.implicitHeight + holder.childrenRect.height + 36
                 : Math.max(46, texts.implicitHeight + 22, holder.childrenRect.height + 18)

    Rectangle {
        visible: !row.first
        x: 14; width: parent.width - 14
        height: 1
        color: Theme.separator
    }
    Column {
        id: texts
        x: 14
        y: row.wide ? 12 : (row.height - implicitHeight) / 2
        width: row.wide ? parent.width - 28 : parent.width - holder.width - 42
        spacing: 2
        opacity: row.active ? 1 : 0.42
        Label { width: parent.width; text: row.title; textStyle: "body"; wrapMode: Text.WordWrap }
        Label {
            visible: row.desc !== ""
            width: parent.width
            text: row.desc
            textStyle: "footnote"
            color: Theme.label3
            wrapMode: Text.WordWrap
        }
    }
    Item {
        id: holder
        width: childrenRect.width
        height: childrenRect.height
        x: row.wide ? (row.width - width) / 2 : row.width - width - 14
        y: row.wide ? texts.y + texts.implicitHeight + 12 : (row.height - height) / 2
        enabled: row.active
        opacity: row.active ? 1 : 0.6
    }
}
