import QtQuick

// Inset-grouped settings section on a glass panel: an icon tile, title and subtitle above; rows inside,
// separated by inset hairlines; a footnote below. Rows filter by the page's search query.
Column {
    id: grp
    property string title: ""
    property string subtitle: ""
    property string footer: ""
    property string icon: ""
    property color iconColor: Theme.accentFill
    property string query: ""
    default property alias rows: body.data
    spacing: 8
    width: parent ? parent.width : 400

    property int shown: 0
    function relayout() {
        let n = 0
        for (let i = 0; i < body.children.length; ++i) {
            const r = body.children[i]
            if (r.matches === undefined) continue
            r.first = n === 0
            if (r.matches) n++        // not `visible`: that is false while the group itself is hidden
        }
        shown = n
    }
    onQueryChanged: relayout()
    Component.onCompleted: relayout()
    visible: shown > 0

    Row {
        spacing: 10
        leftPadding: 4
        Rectangle {
            visible: grp.icon !== ""
            width: 24; height: 24; radius: 6.5
            anchors.verticalCenter: parent.verticalCenter
            gradient: Gradient {
                GradientStop { position: 0; color: Qt.lighter(grp.iconColor, 1.18) }
                GradientStop { position: 1; color: grp.iconColor }
            }
            Icon { anchors.centerIn: parent; name: grp.icon; size: 15; weight: 1.7; color: "#ffffff" }
        }
        Column {
            anchors.verticalCenter: parent.verticalCenter
            Label { text: grp.title; textStyle: "title3" }
            Label {
                visible: grp.subtitle !== ""
                text: grp.subtitle
                textStyle: "footnote"
                color: Theme.label3
            }
        }
    }

    Item {
        width: grp.width
        height: body.height
        Glass {
            anchors.fill: parent
            anchors.margins: -10
            inset: 10
            radius: Theme.rGroup
            bezel: 10
            refraction: 0
            tint: Theme.groupTint
            specular: Theme.specular * 0.45
            shadow: Theme.dark ? 0.18 : 0.07
            shadowSize: 10
            edge: Theme.glassEdge * 0.7
        }
        Column {
            id: body
            width: parent.width
            onChildrenChanged: grp.relayout()
        }
    }

    Label {
        visible: grp.footer !== ""
        width: grp.width
        leftPadding: 4; rightPadding: 4
        text: grp.footer
        textStyle: "footnote"
        color: Theme.label3
        wrapMode: Text.WordWrap
    }
    Item { width: 1; height: 14 }
}
